import copy
import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from marketing_analysis import analyze_report, validate_policy

NOW=datetime(2026,10,20,tzinfo=timezone.utc)
POLICY={'currency':'USD','purchase_event':'purchase','purchase_value_basis':'revenue_before_refunds_and_taxes',
        'costs':{'product_cost_per_order':'10','shipping_cost_per_order':'5','payment_fee_percent':'3',
                 'fixed_fee_per_order':'1','refund_rate_percent':'0','tax_percent_of_revenue':'0'},'daily_spend_limit':'90'}

def report(spend='100',purchases='10',value='500',clicks='100',date='2026-10-16'):
    return {'platform':'meta','account_id':'123','level':'ad','attribution':'same',
      'account':{'currency':'USD','timezone':'Asia/Seoul'},'start_date':date,'end_date':date,'complete':True,'missing_dates':[],
      'days':[{'date':date,'saved_at':NOW.isoformat()}],
      'rows':[{'date':date,'entity_id':'30','entity_name':'Black dress','placement':'instagram',
               'metrics':{'spend':spend,'impressions':'1000','clicks':clicks},
               'actions':[{'action_type':'purchase','value':purchases},{'action_type':'omni_purchase','value':'999'}],
               'action_values':[{'action_type':'purchase','value':value}]}]}

class AnalysisTests(unittest.TestCase):
    def analyze(self,r=None,p=None,previous=None):return analyze_report(r or report(),p or POLICY,previous,now=NOW)
    def test_profit_math_and_no_double_counting(self):
        a=self.analyze();e=a['entities'][0];m=e['metrics']
        self.assertEqual(m['purchases'],'10');self.assertEqual(m['purchase_cpa'],'10')
        self.assertEqual(m['roas'],'5');self.assertEqual(m['estimated_contribution_before_ads'],'325.00')
        self.assertEqual(m['estimated_contribution_after_ads'],'225.00');self.assertEqual(m['break_even_cpa'],'32.50')
        f=e['findings'][0];self.assertEqual(f['decision'],'propose_budget_increase');self.assertFalse(f['executed'])
        self.assertEqual(a['spend_alerts'][0]['code'],'daily_spend_limit')
        json.dumps(a)
    def test_negative_contribution_recommends_review_not_execution(self):
        f=self.analyze(report(spend='400'))['entities'][0]['findings'][0]
        self.assertEqual(f['decision'],'propose_pause');self.assertTrue(f['requires_owner_approval']);self.assertFalse(f['executed'])
    def test_small_sample_never_scales_or_pauses(self):
        for r in [report(purchases='1'),report(clicks='10')]:
            fs=self.analyze(r)['entities'][0]['findings']
            self.assertEqual(fs[0]['code'],'small_sample')
    def test_unknown_cost_event_and_currency_fail_closed(self):
        p=copy.deepcopy(POLICY);p['costs']['product_cost_per_order']=None
        self.assertIsNone(self.analyze(p=p)['entities'][0]['metrics']['estimated_contribution_after_ads'])
        r=report();r['rows'][0]['actions']=[]
        self.assertIsNone(self.analyze(r)['entities'][0]['metrics']['purchases'])
        r=report();r['account']['currency']='KRW'
        self.assertEqual(self.analyze(r)['entities'][0]['findings'][0]['decision'],'wait_for_data')
    def test_missing_stale_immature_and_future_timestamp_block_actions(self):
        cases=[]
        r=report();r['complete']=False;cases.append(r)
        r=report();r['days'][0]['saved_at']=(NOW-timedelta(days=2)).isoformat();cases.append(r)
        r=report(date='2026-10-19');cases.append(r)
        r=report();r['days'][0]['saved_at']=(NOW+timedelta(days=2)).isoformat();cases.append(r)
        for r in cases:
            with self.subTest(r=r):
                a=self.analyze(r);self.assertEqual(a['entities'][0]['findings'][0]['decision'],'wait_for_data');self.assertEqual(a['spend_alerts'],[])
    def test_tiktok_conversion_is_never_purchase(self):
        r=report();r['platform']='tiktok';r['rows'][0]['metrics']['conversion']='25'
        a=self.analyze(r);self.assertIsNone(a['entities'][0]['metrics']['purchase_cpa']);self.assertIsNone(a['entities'][0]['metrics']['roas'])
    def test_period_comparison_requires_same_grain_currency_and_adjacent_dates(self):
        previous=report(spend='50',date='2026-10-15')
        self.assertEqual(self.analyze(previous=previous)['comparison']['spend_change_percent'],'100')
        for k,v in [('level','campaign'),('account_id','456'),('end_date','2026-10-14')]:
            bad=copy.deepcopy(previous);bad[k]=v
            self.assertIsNone(self.analyze(previous=bad)['comparison'])
    def test_ctr_is_weighted_not_average_and_zero_denominators_unknown(self):
        r=report();r['rows'].append(copy.deepcopy(r['rows'][0]));r['rows'][1]['metrics'].update(impressions='9000',clicks='0')
        self.assertEqual(self.analyze(r)['entities'][0]['metrics']['ctr_percent'],'1')
        m=self.analyze(report(spend='0',clicks='0'))['entities'][0]['metrics'];self.assertIsNone(m['roas']);self.assertIsNone(m['cpc'])
    def test_policy_guards(self):
        for mod in [{'rules':{'maximum_budget_increase_percent':'50'}},{'rules':{'attribution_delay_days':'2.5'}},
                    {'rules':{'minimum_clicks':'0'}},{'rules':None},{'monitoring_enabled':'yes'}]:
            with self.subTest(mod=mod),self.assertRaises(ValueError):validate_policy({**POLICY,**mod})
    def test_manager_endpoints_are_private_and_csrf_protected(self):
        from app import app
        c=app.test_client()
        self.assertEqual(c.get('/ai/marketing/manager').status_code,401)
        with c.session_transaction() as s:s['owner']=True;s['csrf']='csrf'
        for path in ['/ai/marketing/analysis','/ai/marketing/decisions','/ai/marketing/alerts/1/acknowledge']:
            self.assertEqual(c.post(path,json={}).status_code,403)
        with patch('marketing_manager.record_decision',return_value={'executed':False,'outcome':'accepted_for_review'}) as decision:
            r=c.post('/ai/marketing/decisions',json={'analysis_id':1,'entity_id':'30','placement':'instagram','code':'positive_contribution','outcome':'accepted_for_review'},headers={'X-CSRF-Token':'csrf'})
            self.assertEqual(r.status_code,200);self.assertFalse(r.json['executed']);decision.assert_called_once()
