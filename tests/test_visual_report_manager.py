from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.core import supabase_client
from src.core.auth_manager import AuthManager
from src.core.central_manager import CentralManager
from src.core.supabase_client import AuthError, SupabaseError


def dashboard():
    return {'branches':[],'totals':{'total_vendido':3000,'ventas_count':3001},'fetched_at':'2026-11-06T12:00:00Z',
        'charts':{'sales_trend':{'granularity':'day','points':[
            {'date':'2026-11-01','total':3000,'count':3001},
            {'date':'2026-11-02','total':0,'count':0}]},
            'payment_methods':[{'label':'Mixto','total':3000,'count':3001}],
            'cash_closures':{'balanced_count':2,'shortage_count':1,'surplus_count':1,
                'shortage_total':50,'surplus_total':50},
            'stock_health':{'healthy_count':10,'low_count':3,'out_count':2}}}


class VisualReportManagerTests(unittest.TestCase):
    def setUp(self):
        patcher=patch.object(AuthManager,'require_user',return_value=SimpleNamespace(role='admin'))
        self.user=patcher.start();self.addCleanup(patcher.stop)
        patcher=patch.object(AuthManager,'ensure_auth_token',return_value='token')
        patcher.start();self.addCleanup(patcher.stop)
        patcher=patch.object(supabase_client,'request',return_value=dashboard())
        self.remote=patcher.start();self.addCleanup(patcher.stop)

    def fetch(self,value):
        self.remote.return_value=value
        return CentralManager.fetch_dashboard(fecha_desde='2026-11-01',fecha_hasta='2026-11-02')

    def test_valid_charts_are_passed_through_from_single_server_aggregate(self):
        value=dashboard()
        result=self.fetch(value)
        self.assertIs(result,value)
        self.remote.assert_called_once()
        self.assertEqual(self.remote.call_args.args[1],'/rest/v1/rpc/resumen_central')
        self.assertEqual(result['charts']['sales_trend']['points'][0]['count'],3001)
        self.assertEqual(result['charts']['payment_methods'][0]['label'],'Mixto')
        self.assertEqual(result['charts']['cash_closures']['shortage_total'],50)
        self.assertEqual(result['charts']['cash_closures']['surplus_total'],50)

    def test_previous_rpc_without_charts_remains_compatible_and_does_not_invent_data(self):
        value=dashboard();del value['charts']
        self.assertNotIn('charts',self.fetch(value))

    def test_unknown_granularity_and_invalid_point_dates_are_rejected(self):
        for grain,point_date in (('quarter','2026-11-01'),('week','2026-11-01'),
                ('month','2026-11-02'),('year','2026-11-01'),('day','not-date')):
            with self.subTest(grain=grain,point_date=point_date):
                value=dashboard();value['charts']['sales_trend']={'granularity':grain,
                    'points':[{'date':point_date,'total':1,'count':1}]}
                with self.assertRaises(SupabaseError):self.fetch(value)

    def test_all_supported_bucket_shapes_are_accepted(self):
        for grain,point_date in (('day','2026-11-01'),('week','2026-11-02'),
                                ('month','2026-11-01'),('year','2026-01-01')):
            value=dashboard();value['charts']['sales_trend']={'granularity':grain,
                'points':[{'date':point_date,'total':0,'count':0}]}
            self.assertIs(self.fetch(value),value)

    def test_nonfinite_negative_and_boolean_values_are_rejected(self):
        for invalid in (float('nan'),float('inf'),-1,True,'12',None,10**1000):
            with self.subTest(value=invalid):
                value=dashboard();value['charts']['payment_methods'][0]['total']=invalid
                with self.assertRaises(SupabaseError):self.fetch(value)
        for invalid in (-1,True,1.5,'1',None,2**64):
            value=dashboard();value['charts']['stock_health']['out_count']=invalid
            with self.assertRaises(SupabaseError):self.fetch(value)

    def test_missing_chart_sections_or_fields_are_rejected(self):
        for section in ('sales_trend','payment_methods','cash_closures','stock_health'):
            value=dashboard();del value['charts'][section]
            with self.assertRaises(SupabaseError):self.fetch(value)
        value=dashboard();del value['charts']['cash_closures']['shortage_total']
        with self.assertRaises(SupabaseError):self.fetch(value)

    def test_unsorted_or_duplicate_dates_and_unbounded_series_are_rejected(self):
        value=dashboard();value['charts']['sales_trend']['points'].reverse()
        with self.assertRaises(SupabaseError):self.fetch(value)
        value=dashboard();value['charts']['sales_trend']['points']*=251
        with self.assertRaises(SupabaseError):self.fetch(value)

    def test_payment_labels_are_plain_valid_unique_strings(self):
        for invalid in ('','\nunsafe',None,5):
            value=dashboard();value['charts']['payment_methods'][0]['label']=invalid
            with self.assertRaises(SupabaseError):self.fetch(value)
        value=dashboard();value['charts']['payment_methods']*=2
        with self.assertRaises(SupabaseError):self.fetch(value)

    def test_pathological_explicit_range_is_rejected_before_network(self):
        with self.assertRaisesRegex(ValueError,'500 años'):
            CentralManager.fetch_dashboard(fecha_desde='0001-01-01',fecha_hasta='9999-12-31')
        self.remote.assert_not_called()

    def test_cashier_never_requests_visual_report(self):
        self.user.return_value=SimpleNamespace(role='cajero')
        with self.assertRaises(AuthError):CentralManager.fetch_dashboard()
        self.remote.assert_not_called()


if __name__=='__main__':unittest.main()
