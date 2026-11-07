from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.core.central_manager import CentralManager
from src.core.auth_manager import AuthManager
from src.core.supabase_client import AuthError, NetworkError, SupabaseError
from src.core import app_config, supabase_client


class CentralManagerTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(role='admin')
        self.current = patch.object(AuthManager,'require_user',return_value=self.user).start()
        self.token = patch.object(AuthManager,'ensure_auth_token',return_value='token').start()
        self.remote = patch.object(supabase_client,'request').start()
        self.addCleanup(patch.stopall)

    def test_cashier_cannot_query_central_or_request_prices(self):
        self.user.role='cajero'
        for operation in (CentralManager.fetch_dashboard,lambda: CentralManager.fetch_page('ventas'),
                          lambda: CentralManager.request_price_change(app_config.BRANCH_ID,app_config.BRANCH_ID,1,1,2)):
            with self.assertRaises(AuthError): operation()
        self.remote.assert_not_called()

    def test_dashboard_uses_server_totals_not_first_page_or_cached_data(self):
        result={'branches':[], 'totals':{'ventas_count':2001,'total_vendido':100001}, 'fetched_at':'2026-11-06T12:00:00Z'}
        self.remote.return_value=result
        self.assertEqual(CentralManager.fetch_dashboard(fecha_desde='2026-11-01',fecha_hasta='2026-11-30'),result)
        self.assertEqual(self.remote.call_args.args[1],'/rest/v1/rpc/resumen_central')
        self.assertEqual(self.remote.call_args.args[2]['p_fecha_hasta'],'2026-11-30')
        self.remote.side_effect=NetworkError('offline')
        with self.assertRaises(NetworkError): CentralManager.fetch_dashboard()

    def test_page_requests_explicit_bounds_and_keeps_pagination(self):
        self.remote.return_value={'rows':[{'id':app_config.BRANCH_ID,'nombre':'Producto',
            'payload':{'costo_final':12},'sucursal_nombre':'Simoca'}], 'has_more':True}
        result=CentralManager.fetch_page('productos',page=3,page_size=20)
        self.assertTrue(result['has_more'])
        self.assertEqual(result['rows'][0]['costo_final'],12)
        params=self.remote.call_args.args[2]
        self.assertEqual((params['p_page'],params['p_page_size']),(3,20))

    def test_invalid_dates_and_page_arguments_fail_before_network(self):
        for kwargs in ({'page':-1},{'page_size':101},{'page':True},{'fecha_desde':'no-date'},
                       {'fecha_desde':'2026-11-02','fecha_hasta':'2026-11-01'}, {'branch_id':'invalid'}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError): CentralManager.fetch_page('ventas',**kwargs)
        self.remote.assert_not_called()

    def test_command_is_pending_and_preserves_expected_revision(self):
        self.remote.return_value={'id':app_config.BRANCH_ID,'estado':'PENDIENTE'}
        result=CentralManager.request_price_change(app_config.BRANCH_ID,app_config.BRANCH_ID,4,'100.005',120)
        self.assertEqual(result['estado'],'PENDIENTE')
        params=self.remote.call_args.args[2]
        self.assertEqual((params['p_expected_catalog_revision'],params['p_precio_contado']),(4,100.01))
        self.assertNotIn('stock_actual',params)

    def test_nonfinite_prices_and_invalid_revision_never_leave_client(self):
        for value in (float('nan'),float('inf'),-1,'invalid',1e14):
            with self.assertRaises(ValueError):
                CentralManager.request_price_change(app_config.BRANCH_ID,app_config.BRANCH_ID,1,value,100)
        self.remote.assert_not_called()

    def test_oversized_server_page_is_not_silently_accepted(self):
        self.remote.return_value={'rows':[{},{}],'has_more':False}
        with self.assertRaises(SupabaseError): CentralManager.fetch_page('ventas',page_size=1)

    def test_command_fields_are_normalized_for_interface(self):
        self.remote.return_value={'rows':[{'created_at':'now','detail':'pending'}],'has_more':False}
        row=CentralManager.fetch_page('comandos')['rows'][0]
        self.assertEqual((row['creado_en'],row['detalle']),('now','pending'))


if __name__=='__main__': unittest.main()
