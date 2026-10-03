import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from inventory_monitor import stock_state, should_alert, scan_inventory
import ads_service

class InventoryTests(unittest.TestCase):
    def test_threshold_and_rearm(self):
        prev = None
        emitted = []
        for n in [70,50,49,0,0,5,80,50]:
            state = stock_state({'status':'ACTIVE','totalInventory':n})
            if should_alert(prev,state): emitted.append(n)
            prev = state
        self.assertEqual(emitted,[50,0,5,50])

    def test_unknown_and_inactive_do_not_mean_zero(self):
        for product in [{'status':'ACTIVE'}, {'status':'ACTIVE','totalInventory':None},
            {'status':'ACTIVE','totalInventory':True},{'status':'DRAFT','totalInventory':0}]:
            self.assertEqual(stock_state(product),'ignored')

    def test_failed_complete_fetch_does_not_update_checkpoint(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (None,)
        with patch('inventory_monitor._connect') as db, patch('inventory_monitor.get_products',side_effect=RuntimeError('incomplete')):
            db.return_value.__enter__.return_value = conn
            with patch.dict(os.environ,{'SHOPIFY_STORE_DOMAIN':'test.myshopify.com'}):
                with self.assertRaises(RuntimeError): scan_inventory()
        sql = [call.args[0] for call in conn.execute.call_args_list]
        self.assertFalse(any('UPDATE inventory_monitor' in q for q in sql))
        self.assertFalse(any('INSERT INTO inventory_alerts(' in q for q in sql))

    def test_duplicate_workers_respect_checkpoint(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (datetime.now(timezone.utc),)
        with patch('inventory_monitor._connect') as db, patch('inventory_monitor.get_products') as fetch:
            db.return_value.__enter__.return_value = conn
            with patch.dict(os.environ,{'SHOPIFY_STORE_DOMAIN':'test.myshopify.com'}):
                self.assertFalse(scan_inventory())
            fetch.assert_not_called()

class AdReportsTests(unittest.TestCase):
    def test_configuration_exposes_no_credentials(self):
        with patch.dict(os.environ,{'META_ACCESS_TOKEN':'PRIVATE','META_AD_ACCOUNT_ID':'123','META_API_VERSION':'v25.0'}):
            self.assertTrue(ads_service.configuration()['meta']['configured'])
            self.assertNotIn('PRIVATE',str(ads_service.configuration()))
            self.assertFalse(ads_service.configuration()['meta']['verified'])

    def test_meta_pagination_and_separate_placements(self):
        pages = [{'data':[{'campaign_id':'1','publisher_platform':'facebook','spend':'2','account_currency':'USD'}],
            'paging':{'next':'https://malicious.example','cursors':{'after':'next'}}},
            {'data':[{'campaign_id':'1','publisher_platform':'instagram','spend':'3','account_currency':'USD'}]}]
        with patch.dict(os.environ,{'META_ACCESS_TOKEN':'PRIVATE','META_AD_ACCOUNT_ID':'123','META_API_VERSION':'v25.0'}),patch('ads_service._json_get',side_effect=pages) as fetch:
            result=ads_service.meta_report('2026-09-01','2026-09-07')
            self.assertEqual([r['placement'] for r in result['rows']],['facebook','instagram'])
            self.assertTrue(all(c.args[0].startswith('https://graph.facebook.com/') for c in fetch.call_args_list))
            self.assertEqual(result['rows'][0]['spend'],2)
            self.assertIsNone(result['rows'][0]['clicks'])

    def test_tiktok_failure_never_becomes_zero_results(self):
        with patch.dict(os.environ,{'TIKTOK_ACCESS_TOKEN':'PRIVATE','TIKTOK_ADVERTISER_ID':'123'}),patch('ads_service._json_get',return_value={'code':40000,'message':'PRIVATE'}):
            with self.assertRaises(ads_service.AdsError) as error:
                ads_service.tiktok_report('2026-09-01','2026-09-07')
            self.assertNotIn('PRIVATE',str(error.exception))

    def test_dates_and_nonfinite_metrics(self):
        with self.assertRaises(ValueError):ads_service._dates('2026-09-30','2026-09-01')
        with self.assertRaises(ValueError):ads_service._dates('2026-01-01','2026-09-01')
        self.assertIsNone(ads_service._number('NaN'))
        self.assertIsNone(ads_service._number(None))

    def test_private_endpoints(self):
        from app import app
        client=app.test_client()
        for path in ['/ai/marketing/status','/ai/marketing/report','/ai/inventory/alerts']:
            self.assertEqual(client.get(path).status_code,401)
        with client.session_transaction() as session:
            session['owner']=True
            session['csrf']='test'
        self.assertEqual(client.post('/ai/inventory/alerts/1/acknowledge').status_code,403)
        with patch('ads_service.get_ads_context',return_value={'meta':{'configured':False}}):
            self.assertEqual(client.get('/ai/marketing/report').status_code,200)
        self.assertEqual(client.get('/ai/marketing/report?start=invalid').status_code,400)

if __name__ == '__main__':
    unittest.main()

