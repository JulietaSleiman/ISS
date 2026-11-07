from contextlib import closing
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import uuid

from src.core import app_config, supabase_client
from src.core.auth_manager import AuthManager
from src.core.caja_manager import CajaManager
from src.core.entity_sync_store import EntitySyncStore
from src.core.sync_manager import SyncManager
from src.core.supabase_client import NetworkError, SupabaseError
from src.db import database


class MultibranchSyncTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(temp.cleanup)
        self.user=SimpleNamespace(user_id='11111111-1111-4111-8111-111111111111',username='caja1',
            branch_id=app_config.BRANCH_ID,branch_name=app_config.BRANCH_NAME,role='cajero')
        for target,value in (('src.db.database.DB_PATH',Path(temp.name)/'test.sqlite'),
                             ('src.db.database.auto_backup_db',lambda:None)):
            p=patch(target,value);p.start();self.addCleanup(p.stop)
        self.current=patch.object(AuthManager,'current_user',side_effect=lambda:self.user).start()
        self.require=patch.object(AuthManager,'require_user',side_effect=lambda:self.user).start()
        self.token=patch.object(AuthManager,'ensure_auth_token',return_value='token').start()
        self.remote=patch.object(supabase_client,'request',side_effect=self.server).start()
        self.addCleanup(patch.stopall)
        database.init_db()
        self.entities={};self.events={};self.commands=[];self.receipts={};self.batches=[]
        self.fail_after_receive=False

    def sql(self,query,args=()):
        with closing(database.get_connection()) as conn:
            with conn:
                return [dict(row) for row in conn.execute(query,args).fetchall()]

    def product(self,stock=20):
        with closing(database.get_connection()) as conn:
            with conn:
                product=conn.execute("INSERT INTO productos(nombre,stock_actual,precio_contado,precio_tarjeta) VALUES('Producto',?,100,120)",(stock,)).lastrowid
                return product

    def server(self,method,path,payload=None,**kwargs):
        if method=='GET': return list(self.commands)
        if path.endswith('/sincronizar_entidades'):
            incoming=payload['p_eventos'];self.batches.append(incoming)
            for event in incoming:
                if event['id'] in self.events:
                    self.assertEqual(self.events[event['id']],event)
                else:
                    self.events[event['id']]=event
                key=(event['payload']['sucursal_id'],event['tipo'],event['entidad_id'])
                if key not in self.entities or event['revision']>self.entities[key]['revision']:
                    self.entities[key]=event['payload']
            if self.fail_after_receive:
                self.fail_after_receive=False
                raise NetworkError('ACK perdido')
            return {'acknowledged':[event['id'] for event in incoming]}
        if path.endswith('/confirmar_comandos_precios'):
            for receipt in payload['p_resultados']:
                self.receipts[receipt['command_id']]=receipt
            return {'acknowledged':[receipt['command_id'] for receipt in payload['p_resultados']]}
        if '/cierres_caja?' in path: return None
        raise AssertionError(path)

    def test_stock_snapshot_retry_is_idempotent_and_not_a_second_decrement(self):
        product=self.product(20)
        self.fail_after_receive=True
        first=SyncManager.sync_pending()
        self.assertEqual((first['sent'],first['pending']),(0,1))
        self.assertEqual(next(iter(self.entities.values()))['stock_actual'],20)
        second=SyncManager.sync_pending()
        self.assertEqual((second['sent'],second['pending']),(1,0))
        self.assertEqual(len(self.events),1)
        self.assertEqual(next(iter(self.entities.values()))['stock_actual'],20)
        self.assertEqual(self.sql('SELECT stock_actual FROM productos WHERE id=?',(product,))[0]['stock_actual'],20)

    def test_partial_ack_only_marks_confirmed_rows_and_unknown_ack_marks_none(self):
        self.product();self.product()
        EntitySyncStore.prepare_initial_sync(self.user)
        rows=self.sql('SELECT id FROM sync_entidades ORDER BY creado_en,id')
        original=self.server
        def partial(method,path,payload=None,**kwargs):
            if path.endswith('/sincronizar_entidades'): return {'acknowledged':[rows[0]['id']]}
            return original(method,path,payload,**kwargs)
        self.remote.side_effect=partial
        first=SyncManager.sync_pending()
        self.assertEqual((first['sent'],first['pending']),(1,1))
        def unknown(method,path,payload=None,**kwargs):
            if path.endswith('/sincronizar_entidades'): return {'acknowledged':[str(uuid.uuid4())]}
            return original(method,path,payload,**kwargs)
        self.remote.side_effect=unknown
        second=SyncManager.sync_pending()
        self.assertEqual((second['sent'],second['pending']),(0,1))
        self.assertIn('inesperados',second['error'])

    def test_no_ack_never_marks_pending_events_as_sent(self):
        self.product()
        self.remote.side_effect=lambda method,path,payload=None,**kwargs: [] if method=='GET' else {}
        result=SyncManager.sync_pending()
        self.assertEqual((result['sent'],result['pending']),(0,1))

    def test_backfill_and_upload_are_bounded_and_count_uncaptured_entities(self):
        for _ in range(205): self.product()
        self.assertEqual(SyncManager.pending_count(),205)
        first=SyncManager.sync_pending()
        self.assertEqual((first['sent'],first['pending']),(50,155))
        self.assertTrue(first['has_more_own'])
        self.assertEqual(len(self.batches[0]),50)
        self.assertEqual(self.sql('SELECT COUNT(*) AS n FROM productos WHERE sync_revision=0')[0]['n'],5)

    def test_cashier_does_not_upload_another_actors_entity_but_admin_same_branch_can(self):
        self.product();EntitySyncStore.prepare_initial_sync(self.user)
        original=self.user.user_id
        self.user.user_id='22222222-2222-4222-8222-222222222222'
        first=SyncManager.sync_pending()
        self.assertEqual((first['sent'],first['pending']),(0,1))
        self.assertFalse(first['has_more_own'])
        self.user.role='admin'
        self.assertEqual(SyncManager.sync_pending()['sent'],1)
        self.assertEqual(next(iter(self.events.values()))['usuario_id'],original)

    def test_wrong_branch_binding_fails_before_any_remote_request(self):
        EntitySyncStore.prepare_initial_sync(self.user)
        self.user.branch_id='33333333-3333-4333-8333-333333333333'
        result=SyncManager.sync_pending()
        self.assertIn('otra sucursal',result['error'])
        self.remote.assert_not_called()

    def test_duplicate_command_ack_does_not_reapply_prices_or_overwrite_stock(self):
        product=self.product(20);SyncManager.sync_pending()
        row=self.sql('SELECT sync_id,catalog_revision FROM productos WHERE id=?',(product,))[0]
        command={'id':str(uuid.uuid4()),'sucursal_id':self.user.branch_id,'producto_id':row['sync_id'],
            'expected_catalog_revision':row['catalog_revision'],'precio_contado':150,'precio_tarjeta':180}
        self.commands=[command]
        first=SyncManager.sync_pending()
        second=SyncManager.sync_pending()  # Fake server repeats an already acknowledged command.
        updated=self.sql('SELECT precio_contado,stock_actual,catalog_revision FROM productos WHERE id=?',(product,))[0]
        self.assertEqual((updated['precio_contado'],updated['stock_actual'],updated['catalog_revision']),(150,20,row['catalog_revision']+1))
        self.assertEqual(len(self.receipts),1)
        self.assertEqual(self.receipts[command['id']]['status'],'APLICADO')
        self.assertEqual(second['sent'],0)

    def test_missing_new_cloud_migration_does_not_prevent_old_cash_close_upload(self):
        CajaManager.abrir_caja(100);CajaManager.cerrar_caja(100)
        def old_server(method,path,payload=None,**kwargs):
            if '/cierres_caja?' in path: return None
            raise SupabaseError('Migration 004 pendiente')
        self.remote.side_effect=old_server
        result=SyncManager.sync_pending()
        self.assertEqual((result['sent'],result['pending']),(1,0))
        self.assertTrue(result['error'])

    def test_heartbeat_even_without_operations_reports_zero_pending(self):
        result=SyncManager.sync_pending()
        calls=[call for call in self.remote.call_args_list if call.args[1].endswith('/sincronizar_entidades')]
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0].args[2],{'p_eventos':[],'p_pendientes':0})
        self.assertEqual(result['pending'],0)

    def test_invalid_legacy_backfill_keeps_valid_close_upload_available(self):
        CajaManager.abrir_caja(100);CajaManager.cerrar_caja(100)
        with patch.object(EntitySyncStore,'prepare_initial_sync',side_effect=ValueError('Producto histórico inválido')):
            result=SyncManager.sync_pending()
        self.assertEqual((result['sent'],result['pending']),(1,0))
        self.assertIn('histórico inválido',result['error'])

    def test_wrong_branch_remote_command_is_rejected_without_changing_prices(self):
        product=self.product();SyncManager.sync_pending()
        identity=self.sql('SELECT sync_id FROM productos WHERE id=?',(product,))[0]['sync_id']
        self.commands=[{'id':str(uuid.uuid4()),'sucursal_id':'33333333-3333-4333-8333-333333333333',
            'producto_id':identity,'expected_catalog_revision':1,'precio_contado':1,'precio_tarjeta':1}]
        result=SyncManager.sync_pending()
        self.assertIn('otra sucursal',result['error'])
        self.assertEqual(self.sql('SELECT precio_contado FROM productos WHERE id=?',(product,))[0]['precio_contado'],100)


if __name__=='__main__': unittest.main()
