import copy
import json
import os
import unittest
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
import advertising_store as store
import advertising_sync as sync
import ads_service as ads

ACCOUNT={'id':'123','name':'Luree Ads','currency':'USD','timezone':'Asia/Seoul'}
ROW={'campaign_id':'10','entity_id':'10','campaign_name':'Dress','placement':'instagram',
     'currency':'USD','spend':'10.25','impressions':'1000','clicks':'20',
     'actions':[{'action_type':'purchase','value':'2','7d_click':'2'},
                {'action_type':'omni_purchase','value':'2'}],
     'action_values':[{'action_type':'purchase','value':'80.50'}]}
DAY='2026-10-01'
NOW=datetime(2026,10,10,tzinfo=timezone.utc)

def report(rows=None, level='campaign'):
    return {'platform':'meta','level':level,'verified':True,'start_date':DAY,'end_date':DAY,
            'account':ACCOUNT,'rows':copy.deepcopy([ROW] if rows is None else rows)}

class ArchiveValidation(unittest.TestCase):
    def test_money_and_missing_values(self):
        self.assertEqual(store.number('1234567890.123456789'),Decimal('1234567890.123456789'))
        self.assertIsNone(store.number(None))
        for v in ['NaN','Infinity','-1',True,'bad']:
            with self.subTest(value=v), self.assertRaises(ValueError):store.number(v)

    @patch.dict(os.environ,{'SHOPIFY_STORE_DOMAIN':'store.test'})
    def test_rejects_bad_grains_before_any_write(self):
        bad=[report([ROW,ROW]),{**report(),'verified':False},{**report(),'start_date':'2026-09-01'},
             {**report(),'platform':'tiktok'},report([None]),report([{**ROW,'currency':'KRW'}]),
             report([{**ROW,'clicks':'NaN'}]),report([{**ROW,'actions':[None]}])]
        for data in bad:
            with self.subTest(data=data),patch('advertising_store._connect') as db:
                with self.assertRaises((ValueError,TypeError)):store.save_day('meta',ACCOUNT,DAY,data,NOW)
                db.assert_not_called()
        with self.assertRaises(ValueError):store.save_day('meta',ACCOUNT,'2026-10-10',report(),NOW)
        with self.assertRaises(ValueError):store.date_range('2026-01-01','2026-04-03')

    def test_tiktok_identity_currency_and_timezone_are_required(self):
        env={'TIKTOK_ACCESS_TOKEN':'SECRET','TIKTOK_ADVERTISER_ID':'123'}
        good={'code':0,'data':{'list':[{'advertiser_id':'123','name':'Dress','currency':'USD','timezone':'America/New_York'}]}}
        with patch.dict(os.environ,env),patch('advertising_sync._json_get',return_value=good):
            self.assertEqual(sync.tiktok_account()['timezone'],'America/New_York')
        for k,v in [('advertiser_id','456'),('currency',None),('timezone','GMT+9')]:
            bad=copy.deepcopy(good);bad['data']['list'][0][k]=v
            with self.subTest(field=k),patch.dict(os.environ,env),patch('advertising_sync._json_get',return_value=bad):
                with self.assertRaises(ads.AdsError):sync.tiktok_account()

    def test_meta_lower_level_and_precise_money(self):
        row={'campaign_id':'10','campaign_name':'Dress','adset_id':'20','adset_name':'US',
             'ad_id':'30','ad_name':'Black','publisher_platform':'instagram',
             'account_currency':'USD','spend':'10.123456789','date_start':DAY,'date_stop':DAY}
        with patch('ads_service._meta_config',return_value=('123','v25.0',{})),patch('ads_service._json_get',return_value={'data':[row]}) as api:
            r=ads.meta_report(DAY,DAY,ACCOUNT,level='ad',precise=True)
            self.assertEqual(r['rows'][0]['entity_id'],'30')
            self.assertEqual(r['rows'][0]['parent_id'],'20')
            self.assertEqual(r['rows'][0]['spend'],'10.123456789')
            self.assertEqual(api.call_args.args[2]['level'],'ad')
        row['date_stop']='2026-10-02'
        with patch('ads_service._meta_config',return_value=('123','v25.0',{})),patch('ads_service._json_get',return_value={'data':[row]}):
            with self.assertRaises(ads.AdsError):ads.meta_report(DAY,DAY,ACCOUNT)

    def test_tiktok_adgroup_grain(self):
        data={'code':0,'data':{'list':[{'dimensions':{'adgroup_id':'20'},'metrics':{'campaign_id':'10','adgroup_name':'US','spend':'3.25'}}], 'page_info':{'total_page':1}}}
        with patch.dict(os.environ,{'TIKTOK_ACCESS_TOKEN':'SECRET','TIKTOK_ADVERTISER_ID':'123'}),patch('ads_service._json_get',return_value=data) as api:
            r=ads.tiktok_report(DAY,DAY,level='adgroup',precise=True)
            self.assertEqual(r['rows'][0]['entity_id'],'20')
            self.assertEqual(r['rows'][0]['parent_id'],'10')
            self.assertEqual(api.call_args.args[2]['data_level'],'AUCTION_ADGROUP')

    def test_owner_and_csrf_protect_queue(self):
        os.environ.setdefault('AGENT_PASSWORD','test-only-password-123')
        os.environ.setdefault('AGENT_SESSION_SECRET','test-session-secret-'+'x'*32)
        os.environ.setdefault('DATABASE_URL','postgresql://unused')
        from app import app
        client=app.test_client()
        for path in ['/ai/marketing/archive/status','/ai/marketing/archive']:
            self.assertEqual(client.get(path).status_code,401)
        self.assertEqual(client.post('/ai/marketing/sync',json={}).status_code,401)
        with client.session_transaction() as session:session['owner']=True;session['csrf']='csrf'
        self.assertEqual(client.post('/ai/marketing/sync',json={}).status_code,403)
        with patch('advertising_sync.queue_sync',return_value={'id':1,'status':'queued'}) as queue:
            r=client.post('/ai/marketing/sync',json={'platform':'meta','start':DAY,'end':DAY},headers={'X-CSRF-Token':'csrf'})
            self.assertEqual(r.status_code,202);queue.assert_called_once_with('meta',DAY,DAY)
        self.assertEqual(client.get('/ai/marketing/archive?platform=meta&account_id=123&start=bad&end=bad').status_code,400)

    def test_archive_tool_status_can_be_followed_by_history(self):
        from types import SimpleNamespace
        import llm_service
        calls=[SimpleNamespace(type='function_call',name='read_ad_archive_status',call_id='s',arguments='{}'),
               SimpleNamespace(type='function_call',name='read_ad_history',call_id='h',arguments=json.dumps(
                   {'platform':'meta','account_id':'123','start_date':DAY,'end_date':DAY,'level':'campaign'}))]
        client=MagicMock()
        client.responses.create.side_effect=[SimpleNamespace(output=[calls[0]]),SimpleNamespace(output=[calls[1]]),SimpleNamespace(output=[],output_text='محفوظة')]
        with patch('llm_service.get_client',return_value=client),patch('advertising_store.status',return_value={'accounts':[{'id':'123'}]}),patch('advertising_store.read_history',return_value={'complete':False,'missing_dates':[DAY]}) as history:
            self.assertEqual(llm_service.ask_llm('حلل الأرشيف'),'محفوظة')
            history.assert_called_once()


@unittest.skipUnless(os.environ.get('TEST_ADS_DATABASE_URL'),'Set disposable TEST_ADS_DATABASE_URL for PostgreSQL integration')
class ArchivePostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.schema='ads_test_'+uuid.uuid4().hex
        cls.url=os.environ['TEST_ADS_DATABASE_URL']
        with psycopg.connect(cls.url) as c:c.execute('CREATE SCHEMA '+cls.schema)
        def connect():return psycopg.connect(cls.url,options='-c search_path='+cls.schema)
        cls.connect=staticmethod(connect)
        cls.patches=[patch('advertising_store._connect',side_effect=connect),patch('advertising_sync._connect',side_effect=connect),patch('marketing_manager._connect',side_effect=connect),patch.dict(os.environ,{'SHOPIFY_STORE_DOMAIN':'store.test'})]
        for p in cls.patches:p.start()
        store.initialize()

    @classmethod
    def tearDownClass(cls):
        for p in reversed(cls.patches):p.stop()
        import psycopg
        with psycopg.connect(cls.url) as c:c.execute('DROP SCHEMA '+cls.schema+' CASCADE')

    def setUp(self):
        with self.connect() as c:
            from marketing_manager import prepare_manager
            prepare_manager(c)
            c.execute('TRUNCATE marketing_decisions,marketing_alerts,marketing_analyses,marketing_policies,marketing_monitor_health,marketing_reconciliations RESTART IDENTITY CASCADE')
            c.execute('TRUNCATE advertising_accounts,advertising_entities,advertising_sync_runs,advertising_snapshots,advertising_partitions,advertising_facts RESTART IDENTITY CASCADE')

    def test_idempotent_migration_and_preserved_shopify_data(self):
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS shopify_connections(shop TEXT PRIMARY KEY,access_token TEXT)')
            c.execute("INSERT INTO shopify_connections VALUES ('store.test','private') ON CONFLICT DO NOTHING")
        store.initialize();store.initialize()
        with self.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM shopify_connections').fetchone()[0],1)

    def test_revisions_replaced_removed_rows_and_late_response(self):
        store.save_day('meta',ACCOUNT,DAY,report(),NOW)
        newer=NOW+timedelta(seconds=2)
        store.save_day('meta',ACCOUNT,DAY,report([{**ROW,'spend':'7.50'}]),newer)
        self.assertFalse(store.save_day('meta',ACCOUNT,DAY,report(),NOW+timedelta(seconds=1))['published'])
        r=store.read_history('meta','123',DAY,DAY)
        self.assertTrue(r['complete']);self.assertEqual(r['totals_for_available_days'][0]['spend'],'7.50')
        self.assertEqual(len(r['rows'][0]['actions']),2)
        store.save_day('meta',ACCOUNT,DAY,report([]),newer+timedelta(seconds=1))
        r=store.read_history('meta','123',DAY,'2026-10-02')
        self.assertEqual(r['rows'],[]);self.assertEqual(r['missing_dates'],['2026-10-02'])
        self.assertEqual(r['days'][0]['rows'],0)

    def test_precision_unknowns_and_levels_are_not_double_counted(self):
        store.save_day('meta',ACCOUNT,DAY,report([{**ROW,'spend':'10.123456789'},
            {**ROW,'entity_id':'11','spend':'1','clicks':None}]),NOW)
        store.save_day('meta',ACCOUNT,DAY,report([{**ROW,'entity_id':'30','spend':'999'}],level='ad'),NOW,level='ad')
        r=store.read_history('meta','123',DAY,DAY)
        t=r['totals_for_available_days'][0]
        self.assertEqual(t['spend'],'11.123456789');self.assertIsNone(t['clicks']);self.assertIsNone(t['cpc'])
        self.assertEqual(store.read_history('meta','123',DAY,DAY,level='ad')['totals_for_available_days'][0]['spend'],'999')

    def test_shop_account_currency_isolation_and_failure_keeps_old_data(self):
        store.save_day('meta',ACCOUNT,DAY,report(),NOW)
        with patch.dict(os.environ,{'SHOPIFY_STORE_DOMAIN':'another.test'}):
            self.assertEqual(store.read_history('meta','123',DAY,DAY)['rows'],[])
        self.assertEqual(store.read_history('meta','456',DAY,DAY)['rows'],[])
        with self.assertRaises(ValueError):store.save_day('meta',{**ACCOUNT,'currency':'KRW'},DAY,report([]),NOW+timedelta(seconds=1))
        self.assertEqual(len(store.read_history('meta','123',DAY,DAY)['rows']),1)

    def test_queue_worker_success_and_interruption_recovery(self):
        with patch('advertising_sync.account_for',return_value=ACCOUNT):
            job=sync.queue_sync('meta',DAY,DAY)
            self.assertEqual(store.status()['recent_runs'][0]['status'],'queued')
            def read(*args,**kwargs):return report(level=kwargs['level'])
            with patch('advertising_sync.meta_report',side_effect=read):self.assertTrue(sync.process_one_sync())
        self.assertEqual(store.status()['recent_runs'][0]['status'],'completed')
        json.dumps(store.status())
        with self.connect() as c:c.execute("UPDATE advertising_sync_runs SET status='running' WHERE id=%s",(job['id'],))
        self.assertFalse(sync.process_one_sync())
        self.assertEqual(store.status()['recent_runs'][0]['error_code'],'worker_interrupted')

    def test_failed_sync_retains_successful_day_and_does_not_claim_completion(self):
        with patch('advertising_sync.account_for',return_value=ACCOUNT):
            sync.queue_sync('meta',DAY,DAY)
            with patch('advertising_sync.meta_report',side_effect=[report(),ads.AdsError('SECRET')]):
                sync.process_one_sync()
        state=store.status()['recent_runs'][0]
        self.assertEqual(state['status'],'failed');self.assertEqual(state['error_code'],'sync_failed')
        self.assertFalse(store.read_history('meta','123',DAY,DAY)['complete'])
        self.assertFalse(store.read_history('meta','123',DAY,DAY,'ad')['complete'])

    def test_manager_policy_analysis_alert_dedupe_and_review_audit(self):
        import marketing_manager as manager
        from test_marketing_analysis import POLICY
        store.save_day('meta',ACCOUNT,DAY,report(),NOW)
        manager.save_policy('meta','123',POLICY)
        with self.connect() as c:c.execute("UPDATE advertising_snapshots SET saved_at=NOW()-INTERVAL '2 days'")
        a=manager.run_analysis('meta','123',DAY,DAY,compare=False)
        manager.run_analysis('meta','123',DAY,DAY,compare=False)
        dash=manager.dashboard();json.dumps(dash)
        self.assertEqual(len(dash['analyses']),2)
        keys=[x['evidence']['code'] for x in dash['alerts']]
        self.assertEqual(keys.count('data_quality'),2) # entity and account, not repeated per run
        f=a['entities'][0]['findings'][0]
        d=manager.record_decision(a['analysis_id'],'10','instagram',f['code'],'accepted_for_review')
        self.assertFalse(d['executed']);self.assertEqual(len(manager.dashboard()['decisions']),1)
        self.assertTrue(manager.acknowledge(dash['alerts'][0]['id']))
        with self.connect() as c:c.execute('UPDATE advertising_snapshots SET saved_at=NOW()')
        manager.run_analysis('meta','123',DAY,DAY,compare=False)
        self.assertTrue(all(x['resolved_at'] for x in manager.dashboard()['alerts']))
        with patch.dict(os.environ,{'SHOPIFY_STORE_DOMAIN':'other.test'}):
            with self.assertRaises(ValueError):manager.record_decision(a['analysis_id'],'10','instagram',f['code'],'accepted_for_review')
            self.assertFalse(manager.acknowledge(dash['alerts'][0]['id']))

    def test_monitoring_is_opt_in_and_queue_is_not_execution(self):
        import marketing_manager as manager
        from test_marketing_analysis import POLICY
        store.save_day('meta',ACCOUNT,DAY,report(),NOW)
        manager.save_policy('meta','123',POLICY)
        with patch('advertising_sync.queue_sync') as queue:
            manager.schedule_monitoring();queue.assert_not_called()
        manager.save_policy('meta','123',{**POLICY,'monitoring_enabled':True})
        with patch('advertising_sync.queue_sync') as queue:
            manager.schedule_monitoring();self.assertEqual(queue.call_count,1)
            self.assertEqual(queue.call_args.kwargs['expected_account_id'],'123')
            manager.schedule_monitoring();self.assertEqual(queue.call_count,1)

    def test_reconciliation_is_persisted_without_order_data(self):
        import marketing_manager as manager
        import shopify_reconciliation as reconciliation
        from test_marketing_complete import cohort,order
        from test_marketing_analysis import POLICY
        store.save_day('meta',ACCOUNT,DAY,report(),NOW)
        manager.save_policy('meta','123',POLICY)
        with patch('shopify_reconciliation.read_order_cohort',return_value=cohort([order()])),patch('database._connect',side_effect=self.connect):
            result=reconciliation.reconcile_orders('meta','123',DAY,DAY)
        self.assertEqual(result['matched_campaigns'][0]['paid_orders'],1)
        with self.connect() as c:
            saved=c.execute('SELECT report FROM marketing_reconciliations').fetchone()[0]
            self.assertNotIn('customerJourneySummary',json.dumps(saved));self.assertNotIn('order_id',saved)

    def test_scaling_guard_requires_fresh_matching_paid_campaign(self):
        import marketing_manager as manager
        from test_marketing_analysis import POLICY
        store.save_day('meta',ACCOUNT,DAY,report(),NOW)
        sample={'currency':'USD','entities':[{'entity_id':'10','findings':[{'decision':'propose_budget_increase','maximum_increase_percent':'15'}]}]}
        manager.apply_shopify_guard(sample,POLICY,'meta','123',DAY,DAY,'campaign')
        self.assertEqual(sample['entities'][0]['findings'][0]['decision'],'verify_shopify_before_scaling')

    def test_ad_scaling_needs_its_own_paid_utm_sample_and_positive_cash(self):
        import marketing_manager as manager
        from test_marketing_analysis import POLICY
        from psycopg.types.json import Jsonb
        store.save_day('meta',ACCOUNT,DAY,report(),NOW)
        store.save_day('meta',ACCOUNT,DAY,report([{**ROW,'entity_id':'20','parent_id':'10'}],level='adgroup'),NOW,level='adgroup')
        store.save_day('meta',ACCOUNT,DAY,report([{**ROW,'entity_id':'30','parent_id':'20'}],level='ad'),NOW,level='ad')
        evidence={'start_date':DAY,'end_date':DAY,'fetched_at':datetime.now(timezone.utc).isoformat(),
            'ads_complete':True,'shop_currency':'USD','currency_match':True,
            'matched_campaigns':[{'campaign_id':'10','paid_orders':5,'received':'500','refunded':'50'}],
            'matched_ads':[{'campaign_id':'10','ad_id':'30','paid_orders':5,'received':'500','refunded':'50'}]}
        with self.connect() as c:c.execute('INSERT INTO marketing_reconciliations(shop,platform,account_id,report) VALUES (%s,%s,%s,%s)',('store.test','meta','123',Jsonb(evidence)))
        sample={'currency':'USD','entities':[{'entity_id':'30','metrics':{'spend':'100'},'findings':[{'decision':'propose_budget_increase','maximum_increase_percent':'15'}]}]}
        manager.apply_shopify_guard(sample,POLICY,'meta','123',DAY,DAY,'ad')
        self.assertEqual(sample['entities'][0]['findings'][0]['decision'],'propose_budget_increase')
        evidence['matched_ads'][0]['ad_id']='31'
        with self.connect() as c:c.execute('INSERT INTO marketing_reconciliations(shop,platform,account_id,report) VALUES (%s,%s,%s,%s)',('store.test','meta','123',Jsonb(evidence)))
        manager.apply_shopify_guard(sample,POLICY,'meta','123',DAY,DAY,'ad')
        self.assertEqual(sample['entities'][0]['findings'][0]['decision'],'verify_shopify_before_scaling')
