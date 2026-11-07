"""Onboarding tests use isolated databases and fake protected credential storage."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.core import app_config, credential_store, installation_store, supabase_client
from src.core.auth_manager import AuthManager, UserSession, _derive, technical_email, normalize_branch_code
from src.core.supabase_client import AuthError, ConfigError, NetworkError
from src.db import database

NORTH_ID='22222222-2222-4222-8222-222222222222'
SOUTH_ID='33333333-3333-4333-8333-333333333333'
USER_ID='11111111-1111-4111-8111-111111111111'


class InstallationLinkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        for target,value in (('src.db.database.DB_PATH',Path(self.temp.name)/'test.sqlite'),
                             ('src.db.database.DB_DIR',Path(self.temp.name)),
                             ('src.db.database.auto_backup_db',lambda:None)):
            p=patch(target,value);p.start();self.addCleanup(p.stop)
        database.init_db()
        AuthManager.logout();self.addCleanup(AuthManager.logout)
        self.cache={}
        for name,action in (
            ('save',lambda user,data:self.cache.update({(data['branch'],user):copy.deepcopy(data)})),
            ('load',lambda user,branch_id=None:copy.deepcopy(self.cache.get((branch_id,user)))),
            ('delete',lambda user,branch_id=None:self.cache.pop((branch_id,user),None))):
            p=patch.object(credential_store,name,side_effect=action);p.start();self.addCleanup(p.stop)
        transport=patch.object(supabase_client,'request')
        self.remote=transport.start();self.addCleanup(transport.stop)

    def sql(self,query,args=()):
        with closing(database.get_connection()) as conn:
            with conn:
                return [dict(row) for row in conn.execute(query,args).fetchall()]

    def responses(self,branch_id=NORTH_ID,code='norte',name='Sucursal Norte',include_code=True):
        branch={'id':branch_id,'nombre':name,'activa':True}
        if include_code:branch['codigo']=code
        return [{'access_token':'token','refresh_token':'refresh','expires_in':3600,'user':{'id':USER_ID}},
            [{'id':USER_ID,'username':'caja1','sucursal_id':branch_id,'nombre':'Caja 1','rol':'cajero','activo':True}],
            [branch]]

    def login(self,branch_id=NORTH_ID,code='norte'):
        self.remote.side_effect=self.responses(branch_id,code)
        return AuthManager.login('caja1','valid-password',code)

    def test_fresh_database_has_no_default_branch_and_requires_a_code(self):
        self.assertIsNone(installation_store.get_installation())
        with self.assertRaises(ConfigError):technical_email('caja1')
        with self.assertRaises(ConfigError):AuthManager.login('caja1','valid-password')
        self.remote.assert_not_called()

    def test_successful_first_login_uses_server_branch_uuid_then_persists_binding(self):
        session=self.login()
        self.assertEqual(session.branch_id,NORTH_ID)
        self.assertEqual(self.remote.call_args_list[0].args[2]['email'],'caja1.norte@usuarios.invalid')
        self.assertEqual(installation_store.get_installation(),{'branch_id':NORTH_ID,'branch_code':'norte',
            'branch_name':'Sucursal Norte','project_url':app_config.SUPABASE_URL,'legacy':False})
        self.assertEqual(self.cache[(NORTH_ID,'caja1')]['branch_code'],'norte')

    def test_restarted_installation_ignores_compile_time_branch_defaults(self):
        self.login();AuthManager.logout()
        with patch.object(app_config,'BRANCH_ID',SOUTH_ID),patch.object(app_config,'BRANCH_CODE','otro'):
            self.assertEqual(technical_email('caja1'),'caja1.norte@usuarios.invalid')
            self.remote.side_effect=NetworkError('offline')
            self.assertEqual(AuthManager.login('caja1','valid-password').branch_id,NORTH_ID)
            self.assertEqual(app_config.BRANCH_ID,SOUTH_ID)  # No global mutation.

    def test_wrong_code_and_bad_password_do_not_assign_a_fresh_database(self):
        self.remote.side_effect=self.responses(code='sur')
        with self.assertRaises(AuthError):AuthManager.login('caja1','valid-password','norte')
        self.assertIsNone(installation_store.get_installation())
        self.remote.side_effect=AuthError('bad password')
        with self.assertRaises(AuthError):AuthManager.login('caja1','wrong','norte')
        self.assertIsNone(installation_store.get_installation())
        self.assertIsNone(AuthManager.current_user())
        self.assertFalse(self.cache)

    def test_fresh_offline_cannot_link_even_with_a_branch_code(self):
        self.remote.side_effect=NetworkError('offline')
        with self.assertRaisesRegex(AuthError,'primer ingreso'):AuthManager.login('caja1','valid-password','norte')
        self.assertIsNone(installation_store.get_installation())

    def test_linked_installation_rejects_another_code_before_network_without_erasing_cache(self):
        self.login();self.remote.reset_mock()
        with self.assertRaises(AuthError):AuthManager.login('caja1','valid-password','sur')
        self.remote.assert_not_called()
        self.assertIn((NORTH_ID,'caja1'),self.cache)

    def test_partial_or_corrupt_metadata_never_falls_back_to_default_branch(self):
        self.sql("INSERT INTO sync_configuracion(key,value) VALUES('sucursal_id',?)",(app_config.BRANCH_ID,))
        self.sql("INSERT INTO sync_configuracion(key,value) VALUES('codigo_sucursal','norte')")
        with self.assertRaises(ConfigError):installation_store.get_installation()
        self.sql("INSERT INTO sync_configuracion(key,value) VALUES('nombre_sucursal','Norte'),('supabase_url',?)",(app_config.SUPABASE_URL,))
        self.sql("UPDATE sync_configuracion SET value='norte!!!' WHERE key='codigo_sucursal'")
        with self.assertRaises(ConfigError):installation_store.get_installation()

    def test_project_mismatch_rejected_before_sending_password(self):
        self.login();self.remote.reset_mock()
        with patch.object(app_config,'SUPABASE_URL','https://another.supabase.co'):
            with self.assertRaises(ConfigError):AuthManager.login('caja1','valid-password')
        self.remote.assert_not_called()

    def test_existing_foreign_cash_history_cannot_be_rebound(self):
        self.sql("INSERT INTO caja_sesiones(monto_inicial,estado,sucursal_id) VALUES(0,'CERRADA',?)",(SOUTH_ID,))
        self.remote.side_effect=self.responses()
        with self.assertRaises(ConfigError):AuthManager.login('caja1','valid-password','norte')
        self.assertEqual(self.sql('SELECT * FROM sync_configuracion'),[])
        self.assertIsNone(AuthManager.current_user())

    def test_failed_binding_rolls_back_all_metadata_and_never_publishes_session(self):
        self.sql("CREATE TRIGGER deny_binding BEFORE INSERT ON sync_configuracion WHEN NEW.key='nombre_sucursal' BEGIN SELECT RAISE(ABORT,'disk failure'); END")
        self.remote.side_effect=self.responses()
        with self.assertRaises(Exception):AuthManager.login('caja1','valid-password','norte')
        self.assertEqual(self.sql('SELECT * FROM sync_configuracion'),[])
        self.assertIsNone(AuthManager.current_user())
        self.assertFalse(self.cache)

    def test_missing_server_code_is_configuration_error_and_does_not_revoke_cache(self):
        self.login()
        self.remote.side_effect=self.responses(include_code=False)
        with self.assertRaisesRegex(ConfigError,'007'):AuthManager.login('caja1','valid-password')
        self.assertIn((NORTH_ID,'caja1'),self.cache)

    def test_legacy_simoca_cache_remains_usable_offline_and_is_migrated(self):
        self.sql("INSERT INTO sync_configuracion(key,value) VALUES('sucursal_id',?)",(installation_store.LEGACY_SIMOCA_ID,))
        salt='00'*16
        old=UserSession(USER_ID,'caja1',installation_store.LEGACY_SIMOCA_ID,'Estación de Simoca','cajero',refresh_token='refresh')
        import time
        from dataclasses import asdict
        self.cache[(old.branch_id,'caja1')]={'project':app_config.SUPABASE_URL,'branch':old.branch_id,
            'session':asdict(old),'verified_at':time.time(),'salt':salt,'verifier':_derive('valid-password',salt)}
        self.remote.side_effect=NetworkError('offline')
        self.assertTrue(AuthManager.login('caja1','valid-password').offline)
        self.assertFalse(installation_store.get_installation()['legacy'])
        AuthManager.logout()
        self.assertTrue(AuthManager.login('caja1','valid-password').offline)  # Second offline restart.

    def test_refresh_validates_dynamic_branch_not_simoca_default(self):
        self.login();AuthManager._expires_at=0
        self.remote.side_effect=self.responses()
        self.assertEqual(AuthManager.ensure_auth_token(),'token')
        self.assertEqual(AuthManager.current_user().branch_id,NORTH_ID)
        self.remote.side_effect=self.responses(branch_id=SOUTH_ID,code='sur')
        AuthManager._expires_at=0
        with self.assertRaises(AuthError):AuthManager.ensure_auth_token()
        self.assertIsNone(AuthManager.current_user())

    def test_offline_legacy_upgrade_never_revokes_old_cache_if_dpapi_save_is_unavailable(self):
        from dataclasses import asdict
        import time
        branch=installation_store.LEGACY_SIMOCA_ID
        self.sql("INSERT INTO sync_configuracion(key,value) VALUES('sucursal_id',?)",(branch,))
        salt='00'*16
        old=UserSession(USER_ID,'caja1',branch,'Estación de Simoca','cajero',refresh_token='refresh')
        self.cache[(branch,'caja1')]={'project':app_config.SUPABASE_URL,'branch':branch,
            'session':asdict(old),'verified_at':time.time(),'salt':salt,'verifier':_derive('valid-password',salt)}
        self.remote.side_effect=NetworkError('offline')
        with patch.object(credential_store,'save',side_effect=credential_store.CredentialStoreError('blocked')) as save:
            self.assertTrue(AuthManager.login('caja1','valid-password').offline)
            AuthManager.logout()
            self.assertTrue(AuthManager.login('caja1','valid-password').offline)
            save.assert_not_called()
        self.assertIn((branch,'caja1'),self.cache)
        self.assertNotIn('branch_code',self.cache[(branch,'caja1')])

    def test_two_installations_same_codebase_keep_different_branch_uuid(self):
        self.login()
        first=installation_store.get_installation()
        with patch.object(database,'DB_PATH',Path(self.temp.name)/'second.sqlite'):
            database.init_db();AuthManager.logout()
            self.login(SOUTH_ID,'sur')
            self.assertEqual(installation_store.get_installation()['branch_id'],SOUTH_ID)
        self.assertEqual(installation_store.get_installation(),first)

    def test_concurrent_initial_binding_has_one_winner_without_partial_keys(self):
        def bind(branch,code):
            try:
                installation_store.bind_verified(branch,code,code,app_config.SUPABASE_URL)
                return True
            except ConfigError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            result=list(pool.map(lambda args:bind(*args),[(NORTH_ID,'norte'),(SOUTH_ID,'sur')]))
        self.assertEqual(sorted(result),[False,True])
        self.assertEqual(len(self.sql('SELECT * FROM sync_configuracion')),4)

    def test_cache_file_identity_uses_actual_branch_uuid(self):
        self.assertNotEqual(credential_store._path('caja1',NORTH_ID),credential_store._path('caja1',SOUTH_ID))

    def test_branch_code_normalization_is_ascii_and_bounded(self):
        self.assertEqual(normalize_branch_code(' NORTE-2 '),'norte-2')
        for invalid in ('estación','norte_2','-norte','norte--2','a'*49,''):
            with self.assertRaises(ConfigError):normalize_branch_code(invalid)


if __name__=='__main__':unittest.main()
