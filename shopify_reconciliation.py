"""Order-cohort reconciliation with explicit UTM evidence, no inferred ad credit."""
QUERY='query ReconcileOrders($after:String,$filter:String!){ shop { ianaTimezone currencyCode } currentAppInstallation { accessScopes { handle } } orders(first:100,after:$after,query:$filter,sortKey:CREATED_AT){nodes{id createdAt processedAt test cancelledAt displayFinancialStatus currentTotalPriceSet{shopMoney{amount currencyCode}} totalReceivedSet{shopMoney{amount currencyCode}} totalRefundedSet{shopMoney{amount currencyCode}} customerJourneySummary{ready firstVisit{source utmParameters{source medium campaign content}} lastVisit{source utmParameters{source medium campaign content}}}}pageInfo{hasNextPage endCursor}}}\n'
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone, time
from decimal import Decimal
import os
import re
import time as clock
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from advertising_store import date_range, number, read_history, _scope
from shopify_service import _graphql_request


def _money(order, field, currency):
    m=order.get(field,{}).get('shopMoney',{})
    if m.get('currencyCode')!=currency or m.get('amount') is None:
        raise ValueError('Order money currency or value is missing')
    return number(m['amount'])


def read_order_cohort(start_date,end_date,report_timezone,now=None):
    first,last=date_range(start_date,end_date,31)
    zone=ZoneInfo(report_timezone)
    start=datetime.combine(first,time.min,zone).astimezone(timezone.utc)
    stop=datetime.combine(last+timedelta(days=1),time.min,zone).astimezone(timezone.utc)
    search='created_at:>='+start.isoformat()+' created_at:<'+stop.isoformat()
    orders=[];seen=set();seen_ids=set();cursor=None;deadline=clock.monotonic()+90;metadata=None
    while True:
        if clock.monotonic()>deadline or len(orders)>=25000:raise RuntimeError('Order cohort too large; no partial reconciliation')
        d=_graphql_request(QUERY,{'after':cursor,'filter':search})
        shop=d.get('shop');installation=d.get('currentAppInstallation')
        if not isinstance(shop,dict) or not isinstance(installation,dict):raise ValueError('Missing order access metadata')
        scopes={s['handle'] for s in installation.get('accessScopes',[])}
        current=now or datetime.now(timezone.utc)
        if 'read_all_orders' not in scopes and start<current-timedelta(days=60):
            raise ValueError('Order scope does not cover the requested history')
        if not scopes.intersection({'read_orders','write_orders','read_all_orders'}):raise ValueError('Missing order access')
        current_meta={'shop_currency':shop['currencyCode'],'shop_timezone':shop['ianaTimezone'],
                      'all_order_history_permission':'read_all_orders' in scopes,'report_timezone':report_timezone}
        if metadata is not None and metadata!=current_meta:raise ValueError('Store metadata changed during read')
        metadata=current_meta
        conn=d.get('orders')
        if not isinstance(conn,dict) or not isinstance(conn.get('nodes'),list) or not isinstance(conn.get('pageInfo'),dict):
            raise ValueError('Incomplete order page')
        for order in conn['nodes']:
            if not isinstance(order,dict) or not order.get('id') or order['id'] in seen_ids:raise ValueError('Invalid or repeated order')
            seen_ids.add(order['id'])
            created=datetime.fromisoformat(order['createdAt'].replace('Z','+00:00'))
            if created.tzinfo is None or not start<=created<stop:raise ValueError('Order outside requested UTC interval')
            orders.append(order)
        page=conn['pageInfo']
        if type(page.get('hasNextPage')) is not bool:raise ValueError('Incomplete order pagination')
        if not page['hasNextPage']:break
        cursor=page.get('endCursor')
        if not cursor or cursor in seen or not conn['nodes']:raise ValueError('Order pagination did not advance')
        seen.add(cursor)
    return {'orders':orders,'coverage':metadata,'start_utc':start.isoformat(),'end_exclusive_utc':stop.isoformat(),
            'fetched_at':datetime.now(timezone.utc).isoformat()}


def last_touch_evidence(order):
    journey=order.get('customerJourneySummary')
    if not isinstance(journey,dict) or journey.get('ready') is not True:return None,'journey_not_ready'
    visit=journey.get('lastVisit')
    utm=visit.get('utmParameters') if isinstance(visit,dict) else None
    if not isinstance(utm,dict):return None,'missing_last_touch_utm'
    source=str(utm.get('source') or '').strip().lower()
    platform={'facebook':'meta','fb':'meta','instagram':'meta','ig':'meta','meta':'meta','tiktok':'tiktok'}.get(source)
    if not platform:return None,'unknown_or_other_source'
    if str(utm.get('medium') or '').strip().lower() not in ('paid_social','cpc','ppc','paid'):
        return None,'paid_medium_not_confirmed'
    campaign=str(utm.get('campaign') or '').strip()
    ad=str(utm.get('content') or '').strip()
    if not campaign.isdigit():return None,'campaign_id_utm_missing'
    return {'platform':platform,'campaign_id':campaign,'ad_id':ad if ad.isdigit() else None,
            'method':'observed_paid_last_touch_utm'},None


def reconcile_cohort(cohort,ad_report,purchase_event):
    account=ad_report.get('account') or {}
    coverage=cohort['coverage'];currency=coverage['shop_currency']
    currency_match=account.get('currency')==currency
    if ad_report['level']!='campaign':raise ValueError('Reconciliation uses campaign grain only')
    campaigns={r['entity_id'] for r in ad_report['rows']}
    excluded=Counter();unmatched=Counter();paid_orders=0;received=Decimal(0);refunded=Decimal(0)
    matched_ads=defaultdict(lambda:{'paid_orders':0,'received':Decimal(0),'refunded':Decimal(0)})
    matched=defaultdict(lambda:{'paid_orders':0,'received':Decimal(0),'refunded':Decimal(0)})
    for order in cohort['orders']:
        if type(order.get('test')) is not bool:raise ValueError('Unknown test-order status')
        if order['test']:excluded['test_orders']+=1;continue
        cash=_money(order,'totalReceivedSet',currency);refund=_money(order,'totalRefundedSet',currency)
        received+=cash;refunded+=refund
        if order.get('cancelledAt'):excluded['cancelled_orders']+=1;continue
        financial=order.get('displayFinancialStatus')
        if financial not in ('PAID','PARTIALLY_REFUNDED','REFUNDED') or cash<=0:
            excluded['not_confirmed_paid']+=1;continue
        paid_orders+=1
        evidence,reason=last_touch_evidence(order)
        if not evidence:unmatched[reason]+=1;continue
        if evidence['platform']!=ad_report['platform']:unmatched['other_platform']+=1;continue
        if evidence['campaign_id'] not in campaigns:unmatched['campaign_not_in_report']+=1;continue
        g=matched[evidence['campaign_id']];g['paid_orders']+=1;g['received']+=cash;g['refunded']+=refund
        if evidence['ad_id']:
            ad=matched_ads[(evidence['campaign_id'],evidence['ad_id'])];ad['paid_orders']+=1;ad['received']+=cash;ad['refunded']+=refund
    platform_count=[];platform_value=[]
    for row in ad_report['rows']:
        for name,target in [('actions',platform_count),('action_values',platform_value)]:
            values=[x.get('value') for x in row.get(name,[]) if x.get('action_type')==purchase_event]
            target.append(number(values[0]) if len(values)==1 else None)
    def total(values):return str(sum(values,Decimal(0))) if values and all(x is not None for x in values) else None
    return {'source':'Shopify created-order cohort vs platform-attributed campaign reporting',
        'start_date':ad_report['start_date'],'end_date':ad_report['end_date'],'report_timezone':coverage['report_timezone'],
        'shop_currency':currency,'ad_currency':account.get('currency'),'currency_match':currency_match,
        'order_coverage':coverage,'order_interval_utc':[cohort['start_utc'],cohort['end_exclusive_utc']],
        'fetched_at':cohort['fetched_at'],'ads_complete':ad_report.get('complete',False),'ads_missing_dates':ad_report.get('missing_dates',[]),
        'confirmed_paid_orders_in_cohort':paid_orders,'cohort_total_received':str(received),'cohort_total_refunded':str(refunded),
        'cohort_net_cash':str(received-refunded),'excluded_from_paid_order_matching':dict(excluded),'unmatched_paid_orders':dict(unmatched),
        'matched_campaigns':[{'campaign_id':k,'paid_orders':v['paid_orders'],'received':str(v['received']),
                              'refunded':str(v['refunded']),'net_cash':str(v['received']-v['refunded'])} for k,v in sorted(matched.items())],
        'matched_ads':[{'campaign_id':k[0],'ad_id':k[1],'paid_orders':v['paid_orders'],'received':str(v['received']),'refunded':str(v['refunded']),'net_cash':str(v['received']-v['refunded'])} for k,v in sorted(matched_ads.items())],
        'platform_attributed_purchases':total(platform_count),'platform_attributed_purchase_value':total(platform_value),
        'revenue_comparison_available':currency_match and ad_report.get('complete',False) and total(platform_value) is not None,
        'direct_revenue_equivalence_confirmed':False,
        'limitations':['UTMs are observed last-touch evidence, not causal proof or platform event-ID reconciliation.',
          'No cross-platform purchase totals are added. Platforms may claim the same order under different windows.',
          'Cohort uses order creation date. Received/refunded are current cumulative values for those orders, not cash movements in the reporting period.',
          'Shopify cash includes shipping/taxes; platform purchase value may use a different basis. No profit or tracking-error conclusion follows from a gap.',
          'Missing consent/UTMs, cross-device activity, ad blockers, delayed payments and attribution windows can create differences.']}


def reconcile_orders(platform,account_id,start_date,end_date):
    from marketing_manager import load_policy
    report=read_history(platform,account_id,start_date,end_date,'campaign')
    policy=load_policy(platform,account_id)
    if not report.get('account') or not policy:raise ValueError('Account and policy required')
    cohort=read_order_cohort(start_date,end_date,report['account']['timezone'])
    result=reconcile_cohort(cohort,report,policy['purchase_event'])
    # Persist aggregate evidence only: no order IDs, customer data, raw URLs or UTMs.
    from database import _connect
    from psycopg.types.json import Jsonb
    with _connect() as c:
        from marketing_manager import prepare_manager
        prepare_manager(c)
        c.execute('''CREATE TABLE IF NOT EXISTS marketing_reconciliations (
            id BIGSERIAL PRIMARY KEY,shop TEXT NOT NULL,platform TEXT NOT NULL,account_id TEXT NOT NULL,
            report JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
        rid=c.execute('INSERT INTO marketing_reconciliations(shop,platform,account_id,report) VALUES (%s,%s,%s,%s) RETURNING id',
                      (_scope(),platform,account_id,Jsonb(result))).fetchone()[0]
    return {'reconciliation_id':rid,**result}


def tracking_url(destination,platform,campaign_id,ad_id):
    if platform not in ('meta','tiktok') or not str(campaign_id).isdigit() or not str(ad_id).isdigit():raise ValueError('Real numeric campaign/ad IDs required')
    u=urlsplit(destination)
    allowed={urlsplit(os.environ.get('SHOPIFY_PUBLIC_STORE_URL','')).hostname,_scope()}
    if u.scheme!='https' or u.hostname not in allowed or u.username or u.password or u.port not in (None,443):
        raise ValueError('Use the configured merchant HTTPS storefront URL')
    query={k:v for k,v in parse_qsl(u.query) if k=='variant'}
    query.update(utm_source=platform,utm_medium='paid_social',utm_campaign=str(campaign_id),utm_content=str(ad_id))
    return {'url':urlunsplit((u.scheme,u.netloc,u.path,urlencode(query),'')),
            'published':False,'purpose':'Numeric campaign/ad UTM evidence on future orders; historical UTMs cannot be recovered'}

RECONCILE_TOOL={'type':'function','name':'reconcile_ad_orders',
 'description':'Read Shopify paid/refunded order cohort and compare with archived campaign-attributed purchases. Requires verified account and saved policy. No exact event-ID match or causal proof is claimed. Does not return customer data. Up to 31 inclusive days.',
 'parameters':{'type':'object','properties':{k:{'type':'string'} for k in ('platform','account_id','start_date','end_date')},
 'required':['platform','account_id','start_date','end_date'],'additionalProperties':False},'strict':True}
