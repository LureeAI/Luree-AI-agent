import copy
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from test_marketing_analysis import report, POLICY, NOW
from marketing_analysis import analyze_report,validate_policy
from marketing_diagnostics import diagnose
from shopify_reconciliation import read_order_cohort,last_touch_evidence,reconcile_cohort,tracking_url
import ads_service as ads
from advertising_sync import roll_up_tiktok_purchases


def money(value,currency='USD'):return {'shopMoney':{'amount':value,'currencyCode':currency}}
def order(oid='1',**changes):
    o={'id':oid,'createdAt':'2026-10-16T10:00:00Z','test':False,'cancelledAt':None,'displayFinancialStatus':'PAID',
       'totalReceivedSet':money('100'),'totalRefundedSet':money('10'),
       'customerJourneySummary':{'ready':True,'lastVisit':{'utmParameters':{'source':'facebook','medium':'paid_social','campaign':'10','content':'30'}}}}
    o.update(changes);return o

def page(orders=None,more=False,cursor=None):
    return {'shop':{'currencyCode':'USD','ianaTimezone':'Asia/Seoul'},'currentAppInstallation':{'accessScopes':[{'handle':'read_all_orders'}]},
            'orders':{'nodes':[order()] if orders is None else orders,'pageInfo':{'hasNextPage':more,'endCursor':cursor}}}

def cohort(orders):return {'orders':orders,'coverage':{'shop_currency':'USD','report_timezone':'Asia/Seoul'},
                          'start_utc':'2026-10-15T15:00:00+00:00','end_exclusive_utc':'2026-10-16T15:00:00+00:00','fetched_at':NOW.isoformat()}

class CompleteMarketing(unittest.TestCase):
    def test_tiktok_website_purchase_is_explicit_and_generic_conversion_ignored(self):
        metrics={'complete_payment':'3','total_complete_payment_rate':'150','conversion':'999','web_event_add_to_cart':'9','total_landing_page_view':'90','video_play_actions':'1000','video_views_p100':'100'}
        data={'code':0,'data':{'list':[{'dimensions':{'adgroup_id':'20'},'metrics':{**metrics,'campaign_id':'10'}}],'page_info':{'total_page':1}}}
        with patch.dict(os.environ,{'TIKTOK_ACCESS_TOKEN':'SECRET','TIKTOK_ADVERTISER_ID':'123'}),patch('ads_service._json_get',return_value=data):
            row=ads.tiktok_report('2026-10-16','2026-10-16',level='adgroup',precise=True,website_metrics=True)['rows'][0]
        self.assertEqual(row['actions'][0]['value'],'3');self.assertEqual(row['action_values'][0]['value'],'150');self.assertEqual(row['video_p100'],'100')
        r=report();r['platform']='tiktok';r['rows'][0].update(actions=row['actions'],action_values=row['action_values'])
        p={**POLICY,'purchase_event':'tiktok_website_complete_payment'}
        self.assertEqual(analyze_report(r,p,now=NOW)['entities'][0]['metrics']['purchases'],'3')
        self.assertIsNone(analyze_report(r,POLICY,now=NOW)['entities'][0]['metrics']['purchases'])
    def test_tiktok_rollup_uses_adgroups_once_and_missing_values_stay_missing(self):
        def child(value,**kw):return {'parent_id':'10','actions':[{'action_type':'tiktok_website_complete_payment','value':value}], 'action_values':[],**kw}
        reports={'campaign':{'rows':[{'entity_id':'10'}]},'adgroup':{'rows':[child('2'),child('3')]},'ad':{'rows':[child('999')]}}
        roll_up_tiktok_purchases(reports)
        self.assertEqual(reports['campaign']['rows'][0]['actions'][0]['value'],'5')
        self.assertEqual(reports['campaign']['rows'][0]['action_values'],[])
        reports['adgroup']['rows'][1]['actions']=[];roll_up_tiktok_purchases(reports)
        self.assertEqual(reports['campaign']['rows'][0]['actions'],[])
    def test_funnel_is_noncohort_and_ratios_are_not_clamped(self):
        r=report();r['rows'][0]['actions'] += [{'action_type':'lpv','value':'50'},{'action_type':'cart','value':'75'}]
        r['rows'][0]['metrics'].update(video_plays='2000',video_2s='200',video_p100='100')
        p=validate_policy({**POLICY,'funnel_events':{'landing_page_view':'lpv','add_to_cart':'cart'}})
        d=diagnose(r,p);e=d['entities'][0]
        self.assertEqual(e['ratios'][1]['event_ratio_percent'],'150');self.assertIsNone(e['event_counts']['initiate_checkout'])
        self.assertIn('non_cohort_counts_or_repeated_events',e['warnings']);self.assertEqual(e['video']['completion_rate_percent'],'5')
        self.assertTrue(any(f['code']=='test_video_opening' for f in d['findings']))
    def test_order_reader_utc_boundaries_pagination_and_scope(self):
        with patch('shopify_reconciliation._graphql_request',side_effect=[page(more=True,cursor='a'),page([order('2')])]) as api:
            result=read_order_cohort('2026-10-16','2026-10-16','Asia/Seoul',now=NOW)
            self.assertEqual(len(result['orders']),2)
            self.assertIn('2026-10-15T15:00:00+00:00',api.call_args_list[0].args[1]['filter'])
        bad=page();bad['currentAppInstallation']['accessScopes']=[{'handle':'read_orders'}]
        with patch('shopify_reconciliation._graphql_request',return_value=bad):
            with self.assertRaises(ValueError):read_order_cohort('2026-10-16','2026-10-16','Asia/Seoul',now=datetime(2027,1,1,tzinfo=timezone.utc))
    def test_duplicate_cursor_order_and_wrong_dates_fail_closed(self):
        for pages in [[page(more=True,cursor='a'),page()], [page([order(createdAt='2026-10-17T10:00:00Z')])]]:
            with self.subTest(pages=pages),patch('shopify_reconciliation._graphql_request',side_effect=pages):
                with self.assertRaises(ValueError):read_order_cohort('2026-10-16','2026-10-16','Asia/Seoul',now=NOW)
    def test_matching_requires_ready_paid_last_touch_and_numeric_campaign(self):
        self.assertEqual(last_touch_evidence(order())[0]['campaign_id'],'10')
        for edits,reason in [({'ready':False},'journey_not_ready'),({'lastVisit':None},'missing_last_touch_utm')]:
            o=order();o['customerJourneySummary'].update(edits);self.assertEqual(last_touch_evidence(o)[1],reason)
        for k,v in [('medium','organic'),('campaign','Dress campaign'),('source','google')]:
            o=order();o['customerJourneySummary']['lastVisit']['utmParameters'][k]=v
            self.assertIsNone(last_touch_evidence(o)[0])
    def test_reconciliation_cash_refunds_tests_cancellations_and_unmatched(self):
        r=report();r['level']='campaign';r['rows'][0]['entity_id']='10'
        unknown=order('4');unknown['customerJourneySummary']=None
        c=cohort([order(),order('2',test=True),order('3',cancelledAt='2026-10-16T10:01:00Z'),unknown])
        result=reconcile_cohort(c,r,'purchase')
        self.assertEqual(result['confirmed_paid_orders_in_cohort'],2)
        self.assertEqual(result['cohort_total_received'],'300');self.assertEqual(result['cohort_total_refunded'],'30')
        self.assertEqual(result['matched_campaigns'][0]['paid_orders'],1)
        self.assertEqual(result['unmatched_paid_orders']['journey_not_ready'],1)
        self.assertFalse(result['direct_revenue_equivalence_confirmed'])
        self.assertNotIn('customerJourneySummary',str(result));self.assertNotIn('lastVisit',str(result))
    def test_currency_mismatch_is_visible_and_malformed_money_is_rejected(self):
        r=report();r['level']='campaign';r['account']['currency']='KRW'
        self.assertFalse(reconcile_cohort(cohort([order()]),r,'purchase')['revenue_comparison_available'])
        with self.assertRaises(ValueError):reconcile_cohort(cohort([order(totalRefundedSet=money('NaN'))]),r,'purchase')
    def test_tracking_url_is_store_scoped_and_does_not_publish(self):
        with patch.dict(os.environ,{'SHOPIFY_STORE_DOMAIN':'store.myshopify.com','SHOPIFY_PUBLIC_STORE_URL':'https://lureefashions.com'}):
            r=tracking_url('https://lureefashions.com/products/dress?variant=4&fbclid=SECRET','meta','10','30')
            self.assertIn('utm_campaign=10',r['url']);self.assertIn('variant=4',r['url']);self.assertNotIn('SECRET',r['url']);self.assertFalse(r['published'])
            with self.assertRaises(ValueError):tracking_url('https://evil.example/','meta','10','30')
    def test_new_routes_are_owner_and_csrf_protected(self):
        from app import app
        c=app.test_client()
        self.assertEqual(c.post('/ai/marketing/reconcile',json={}).status_code,401)
        with c.session_transaction() as s:s['owner']=True;s['csrf']='csrf'
        self.assertEqual(c.post('/ai/marketing/tracking-url',json={}).status_code,403)
        with patch('shopify_reconciliation.reconcile_orders',return_value={'confirmed_paid_orders_in_cohort':0}):
            self.assertEqual(c.post('/ai/marketing/reconcile',json={'platform':'meta','account_id':'123','start':'2026-10-16','end':'2026-10-16'},headers={'X-CSRF-Token':'csrf'}).status_code,200)
