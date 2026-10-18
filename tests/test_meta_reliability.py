import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import ads_service as ads
import action_service as actions

ENV={'META_ACCESS_TOKEN':'PRIVATE','META_AD_ACCOUNT_ID':'123','META_API_VERSION':'v25.0'}
ACCOUNT={'id':'123','name':'Luree Fashions Ads','currency':'KRW','timezone':'Asia/Seoul'}
PROVIDER={'account_id':'123','name':'Luree Fashions Ads','currency':'KRW','timezone_name':'Asia/Seoul'}

class MetaReliabilityTests(unittest.TestCase):
    def test_relative_dates_are_calendar_accurate(self):
        self.assertEqual(ads.report_dates('yesterday',today=date(2026,1,1)),('2025-12-31','2025-12-31'))
        self.assertEqual(ads.report_dates('previous_month',today=date(2024,3,4)),('2024-02-01','2024-02-29'))
        self.assertEqual(ads.report_dates('last_30_days',today=date(2026,10,18)),('2026-09-18','2026-10-17'))
        for args in [('custom','','2026-10-18'),('yesterday','2026-10-17',''),('custom','2026-01-01','2026-02-01')]:
            with self.subTest(args=args),self.assertRaises(ValueError):ads.report_dates(*args)

    def test_account_identity_and_expected_settings(self):
        with patch.dict(os.environ,ENV,clear=True),patch('ads_service._json_get',return_value=PROVIDER):
            self.assertEqual(ads.meta_account()['token_expiry'],'unknown')
        for key,value in [('account_id','456'),('currency',None),('timezone_name','Unknown/Zone')]:
            with self.subTest(key=key),patch.dict(os.environ,ENV,clear=True),patch('ads_service._json_get',return_value={**PROVIDER,key:value}):
                with self.assertRaises(ads.AdsError):ads.meta_account()
        with patch.dict(os.environ,{**ENV,'META_EXPECTED_CURRENCY':'USD'},clear=True),patch('ads_service._json_get',return_value=PROVIDER):
            with self.assertRaises(ads.AdsError):ads.meta_account()

    def test_provider_errors_do_not_leak_token(self):
        for status,body in [(401,{'error':{'code':190,'message':'PRIVATE'}}),(403,{}),(429,{}),(200,[]),(200,{'error':{'code':17}})]:
            response=MagicMock(status_code=status)
            response.json.return_value=body
            with self.subTest(status=status,body=body),patch('ads_service.requests.get',return_value=response):
                with self.assertRaises(ads.AdsError) as error:ads._json_get('https://graph.facebook.com/test',{}, {})
                self.assertNotIn('PRIVATE',str(error.exception))

    def test_malformed_rows_and_paging_fail_closed(self):
        row={'campaign_id':'1','publisher_platform':'facebook','account_currency':'KRW'}
        pages=[{'data':[None]},{'data':[{**row,'account_currency':'USD'}]}, {'data':[{**row,'actions':[None]}]}, {'data':[], 'paging':[]}, {'data':[],'paging':{'next':'https://bad','cursors':[]}}]
        for page in pages:
            with self.subTest(page=page),patch.dict(os.environ,ENV,clear=True),patch('ads_service._json_get',return_value=page):
                with self.assertRaises(ads.AdsError):ads.meta_report('2026-10-01','2026-10-02',ACCOUNT)

    def test_missing_config_and_verified_empty_data(self):
        with patch.dict(os.environ,{},clear=True),patch('ads_service._json_get') as get:
            self.assertFalse(ads.verify_meta_connection()['verified'])
            self.assertFalse(ads.read_ad_report('meta','yesterday')['meta']['verified'])
            get.assert_not_called()
        with patch.dict(os.environ,ENV,clear=True),patch('ads_service._json_get',side_effect=[PROVIDER,{'data':[]}]):
            result=ads.verify_meta_connection()
            self.assertTrue(result['verified'])
            self.assertEqual(result['account']['id'],'123')

    def test_requested_period_resolves_in_account_timezone(self):
        with patch.dict(os.environ,ENV,clear=True),patch('ads_service.meta_account',return_value=ACCOUNT),patch('ads_service.report_dates',return_value=('2026-09-01','2026-09-30')) as dates,patch('ads_service.meta_report',return_value={'verified':True}) as report:
            self.assertTrue(ads.read_ad_report('meta','previous_month')['meta']['verified'])
            dates.assert_called_once_with('previous_month','','','Asia/Seoul')
            report.assert_called_once_with('2026-09-01','2026-09-30',account_info=ACCOUNT)

    def test_spend_question_can_request_real_report_without_ad_keyword(self):
        import llm_service
        call=SimpleNamespace(type='function_call',name='read_ad_report',call_id='call1',arguments='{"platform":"meta","period":"yesterday","start_date":"","end_date":""}')
        client=MagicMock()
        client.responses.create.side_effect=[SimpleNamespace(output=[call]),SimpleNamespace(output=[],output_text='نتائج مبارح')]
        with patch('llm_service.get_client',return_value=client),patch('ads_service.read_ad_report',return_value={'meta':{'verified':True,'rows':[]}}) as report:
            self.assertEqual(llm_service.ask_llm('كم صرفنا مبارح؟'),'نتائج مبارح')
            report.assert_called_once_with(platform='meta',period='yesterday',start_date='',end_date='')
            self.assertIn('read_ad_report',[t['name'] for t in client.responses.create.call_args_list[0].kwargs['tools']])

class ActionRecoveryTests(unittest.TestCase):
    def test_execution_claim_commits_before_external_write(self):
        events=[]
        conn=MagicMock()
        conn.execute.return_value.fetchone.return_value=('meta_pause','1','PAUSED',{},'pending',False)
        cm=MagicMock()
        cm.__enter__.return_value=conn
        cm.__exit__.side_effect=lambda *args:events.append('commit')
        with patch('action_service._connect',return_value=cm),patch('action_service._apply',side_effect=lambda *args:events.append('write')):
            self.assertEqual(actions.decide_action(1,'approve'),'completed')
        self.assertLess(events.index('commit'),events.index('write'))

    def test_crash_leaves_claim_and_repeated_approval_cannot_resend(self):
        conn=MagicMock()
        conn.execute.return_value.fetchone.return_value=('meta_pause','1','PAUSED',{},'pending',False)
        with patch('action_service._connect') as db,patch('action_service._apply',side_effect=KeyboardInterrupt) as apply:
            db.return_value.__enter__.return_value=conn
            with self.assertRaises(KeyboardInterrupt):actions.decide_action(1,'approve')
            self.assertTrue(any(c.args[1][0]=='executing' for c in conn.execute.call_args_list if c.args[0].startswith('UPDATE')))
            conn.execute.return_value.fetchone.return_value=('meta_pause','1','PAUSED',{},'executing',False)
            with self.assertRaises(actions.ActionError):actions.decide_action(1,'approve')
            self.assertEqual(apply.call_count,1)

    def test_pause_requires_readback_and_reconcile_only_reads(self):
        before={'status':'ACTIVE','updated_time':'same'}
        response=MagicMock(status_code=200)
        response.json.return_value={'success':True}
        with patch.dict(os.environ,ENV),patch('action_service.current_campaign',return_value=before),patch('action_service.requests.post',return_value=response) as post:
            with self.assertRaises(RuntimeError):actions._apply('meta_pause','1','PAUSED',before)
            self.assertEqual(post.call_count,1)
        conn=MagicMock()
        conn.execute.return_value.fetchone.return_value=('1','needs_review')
        with patch('action_service._connect') as db,patch('action_service.current_campaign',return_value={'status':'PAUSED'}),patch('action_service.requests.post') as post:
            db.return_value.__enter__.return_value=conn
            self.assertEqual(actions.reconcile_meta_pause(1),'completed')
            post.assert_not_called()

    def test_reconcile_requires_owner_and_csrf(self):
        from app import app
        client=app.test_client()
        self.assertEqual(client.post('/ai/actions/1/reconcile').status_code,401)
        with client.session_transaction() as session:session['owner']=True;session['csrf']='csrf'
        self.assertEqual(client.post('/ai/actions/1/reconcile').status_code,403)
        with patch('action_service.reconcile_meta_pause',return_value='completed') as reconcile:
            self.assertEqual(client.post('/ai/actions/1/reconcile',headers={'X-CSRF-Token':'csrf'}).json['state'],'completed')
            reconcile.assert_called_once_with(1)
