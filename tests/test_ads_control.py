import os
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, Mock
import ads_control as c
from flask import Flask
from agent_routes import agent_routes
from ads_control_ui import render_control

NOW = datetime.now(timezone.utc)

def policy(**updates):
    p = dict(campaign_id='123', mode='auto_pause', currency='USD', daily_limit='10',
             total_limit='40', account_id='99', expires_at=(NOW+timedelta(days=1)).isoformat())
    p.update(updates)
    return p

def snapshot(**updates):
    p = dict(account_id='99', currency='USD', status='ACTIVE', daily_spend='3',
             total_spend='9', checked_at=NOW.isoformat())
    p.update(updates)
    return p

class PolicyTests(unittest.TestCase):
    def test_valid_and_no_implicit_live_mode(self):
        self.assertEqual(c.validate_mandate(policy())['daily_limit'], '10')
        for mode in (None, 'autonomous', 'launch'):
            with self.assertRaises(c.ControlError): c.validate_mandate(policy(mode=mode))

    def test_invalid_amounts_never_authorize(self):
        for v in ('NaN', 'Infinity', '', None, True, -1, '1e100'):
            with self.subTest(v=v), self.assertRaises(c.ControlError):
                c.validate_mandate(policy(daily_limit=v))
        with self.assertRaises(c.ControlError): c.validate_mandate(policy(daily_limit='50'))

    def test_expiry_and_currency_required(self):
        for exp in ('2026-01-01', 'invalid', (NOW+timedelta(days=40)).isoformat()):
            with self.assertRaises(c.ControlError): c.validate_mandate(policy(expires_at=exp))
        with self.assertRaises(c.ControlError): c.validate_mandate(policy(currency='usd'))

    def test_boundaries_decimal(self):
        self.assertEqual(c.evaluate(policy(), snapshot(), NOW), 'within_limits')
        self.assertEqual(c.evaluate(policy(), snapshot(daily_spend='10'), NOW), 'daily_limit')
        self.assertEqual(c.evaluate(policy(), snapshot(total_spend='40.00'), NOW), 'total_limit')
        self.assertEqual(c.evaluate(policy(daily_limit='0.30'), snapshot(daily_spend='0.3'), NOW), 'daily_limit')

    def test_expired_mandate_requests_pause_not_resume(self):
        self.assertEqual(c.evaluate(policy(expires_at=(NOW-timedelta(seconds=1)).isoformat()), snapshot(), NOW), 'mandate_expired')
        self.assertEqual(c.evaluate(policy(), snapshot(status='PAUSED'), NOW), 'not_active')

    def test_stale_future_and_wrong_account_block(self):
        for seconds in (-121, 30):
            self.assertEqual(c.evaluate(policy(),snapshot(checked_at=(NOW+timedelta(seconds=seconds)).isoformat()),NOW),'stale_data')
        self.assertEqual(c.evaluate(policy(),snapshot(account_id='100'),NOW),'account_mismatch')
        self.assertEqual(c.evaluate(policy(),snapshot(currency='KRW'),NOW),'account_mismatch')

class ProviderTests(unittest.TestCase):
    @patch.dict(os.environ, {'META_API_VERSION':'v25.0','META_ACCESS_TOKEN':'test'})
    @patch('ads_control._json_get')
    def test_missing_and_partial_reports_are_not_zero(self, get):
        for data in ({'data':[]}, {'data':[{'campaign_id':'123','account_currency':'USD'}]},
                     {'data':[{}], 'paging':{'next':'more'}}):
            get.return_value=data
            with self.assertRaises(c.ControlError): c.campaign_spend('123','2026-10-15','2026-10-15')

    @patch.dict(os.environ, {'META_API_VERSION':'v25.0','META_ACCESS_TOKEN':'test'})
    @patch('ads_control._json_get')
    def test_only_one_purchase_type_and_correct_currency(self,get):
        get.return_value={'data':[{'campaign_id':'123','account_currency':'USD','spend':'10.20',
            'actions':[{'action_type':c.PURCHASE,'value':'2'}, {'action_type':'purchase','value':'2'}]}]}
        r=c.campaign_spend('123','2026-10-15','2026-10-15')
        self.assertEqual(r['platform_attributed_purchases'],'2')
        self.assertEqual(r['spend'],'10.20')

    @patch.dict(os.environ, {'META_API_VERSION':'v25.0','META_ACCESS_TOKEN':'test'})
    @patch('ads_control.current_campaign',return_value={'status':'PAUSED'})
    @patch('ads_control.requests.post')
    def test_pause_verified_and_no_retry(self,post,current):
        post.return_value=Mock(status_code=200,json=lambda:{'success':True})
        c.pause_campaign('123'); self.assertEqual(post.call_count,1)
        self.assertEqual(post.call_args.kwargs['data'],{'status':'PAUSED'})
        post.reset_mock();post.side_effect=TimeoutError()
        with self.assertRaises(TimeoutError): c.pause_campaign('123')
        self.assertEqual(post.call_count,1)

    @patch.dict(os.environ, {'META_API_VERSION':'v25.0','META_ACCESS_TOKEN':'test'})
    @patch('ads_control.current_campaign',return_value={'status':'ACTIVE'})
    @patch('ads_control.requests.post',return_value=Mock(status_code=200,json=lambda:{'success':True}))
    def test_success_response_without_paused_readback_is_uncertain(self,*_):
        with self.assertRaises(c.ControlError): c.pause_campaign('123')

class RouteTests(unittest.TestCase):
    def setUp(self):
        app=Flask(__name__);app.register_blueprint(agent_routes);self.client=app.test_client()

    @patch('ads_control.dashboard',return_value={'capabilities':{'campaign_launch':False}})
    def test_status_exposes_real_capabilities(self,_):
        self.assertFalse(self.client.get('/ai/marketing/control').json['control']['capabilities']['campaign_launch'])

    @patch('ads_control.save_mandate',side_effect=c.ControlError('invalid'))
    def test_bad_policy_400(self,_):
        self.assertEqual(self.client.put('/ai/marketing/control',json={}).status_code,400)

    def test_ui_render(self):
        app=Flask(__name__);app.jinja_env.globals['csrf_token']=lambda:'test'
        with app.test_request_context():
            html=render_control()
        self.assertIn('تفويض حملة موجودة',html)
        # JavaScript string remains escaped, not an illegal literal newline.
        self.assertIn("+'\\n'+JSON.stringify",html)

if __name__=='__main__': unittest.main()

class ScanTests(unittest.TestCase):
    def run_scan(self, mode='auto_pause', live='true', uncertain=False, blocked=False):
        conn=Mock();conn.__enter__=Mock(return_value=conn);conn.__exit__=Mock(return_value=False)
        p=policy(mode=mode,start_date=NOW.date().isoformat())
        calls=[]
        def execute(sql,params=None):
            calls.append(sql)
            r=Mock()
            if 'SELECT checked_at' in sql:r.fetchone.return_value=None
            elif 'pg_try_advisory_lock' in sql:r.fetchone.return_value=(True,)
            elif "state='executing'" in sql:r.fetchall.return_value=[]
            elif 'SELECT campaign_id,policy,revision' in sql:r.fetchall.return_value=[('123',p,1)]
            elif "state='needs_review'" in sql:r.fetchone.return_value=(1,) if blocked else None
            elif 'RETURNING id' in sql:r.fetchone.return_value=(7,)
            return r
        conn.execute.side_effect=execute
        def pause(cid):
            self.assertTrue(conn.commit.called)
            self.assertTrue(any('INSERT INTO ad_control_events' in q for q in calls))
            if uncertain:raise TimeoutError()
        env={'SHOPIFY_STORE_DOMAIN':'test.myshopify.com','META_AD_ACCOUNT_ID':'99','ADS_AUTOPAUSE_ENABLED':live}
        with patch.dict(os.environ,env),patch('ads_control._connect',return_value=conn),patch('ads_control.prepare'),patch('ads_control.meta_account',return_value={'currency':'USD','timezone_name':'Asia/Seoul'}),patch('ads_control.current_campaign',return_value={'account_id':'99','status':'ACTIVE'}),patch('ads_control.campaign_spend',return_value={'currency':'USD','spend':'40','platform_attributed_purchases':None}),patch('ads_control.pause_campaign',side_effect=pause) as send:
            c.scan_ads()
        return send,conn

    def test_auto_pause_requires_both_owner_mandate_and_switch(self):
        for mode,live,expected in [('observe','true',0),('auto_pause','false',0),('auto_pause','true',1)]:
            with self.subTest(mode=mode,live=live):
                send,_=self.run_scan(mode,live);self.assertEqual(send.call_count,expected)

    def test_uncertain_write_blocks_future_execution(self):
        send,conn=self.run_scan(uncertain=True)
        self.assertEqual(send.call_count,1)
        self.assertTrue(any(call.args[1]==('needs_review',7) for call in conn.execute.call_args_list if call.args[0].startswith('UPDATE ad_control_events')))
        send,_=self.run_scan(blocked=True);send.assert_not_called()

    @patch('ads_control._connect')
    def test_no_store_never_touches_provider(self,connect):
        with patch.dict(os.environ,{'SHOPIFY_STORE_DOMAIN':''}):self.assertFalse(c.scan_ads())
        connect.assert_not_called()

    def test_authentication_and_csrf_protect_control(self):
        from access_control import init_access
        with patch.dict(os.environ,{'DATABASE_URL':'postgresql://test','AGENT_PASSWORD':'test-password-long','AGENT_SESSION_SECRET':'s'*32}):
            app=Flask(__name__);init_access(app);app.register_blueprint(agent_routes)
            client=app.test_client()
            self.assertEqual(client.get('/marketing-control').status_code,401)
            self.assertEqual(client.get('/ai/marketing/control').status_code,401)
            with client.session_transaction() as session:session['owner']=True;session['csrf']='token'
            self.assertEqual(client.put('/ai/marketing/control',json=policy()).status_code,403)
