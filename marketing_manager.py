"""Persist analysis policies, decision evidence, review outcomes and in-app alerts."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from decimal import Decimal
from zoneinfo import ZoneInfo
from psycopg.types.json import Jsonb
from database import _connect
from advertising_store import prepare, _scope, read_history, status
from marketing_analysis import validate_policy, analyze_report


def prepare_manager(conn):
    prepare(conn)
    conn.execute('SELECT pg_advisory_xact_lock(7432112)')
    conn.execute('''CREATE TABLE IF NOT EXISTS marketing_policies (
        shop TEXT NOT NULL, platform TEXT NOT NULL, account_id TEXT NOT NULL,
        policy JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        next_monitor_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(shop,platform,account_id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS marketing_analyses (
        id BIGSERIAL PRIMARY KEY,shop TEXT NOT NULL,platform TEXT NOT NULL,account_id TEXT NOT NULL,
        report JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    conn.execute('''CREATE TABLE IF NOT EXISTS marketing_reconciliations (
        id BIGSERIAL PRIMARY KEY,shop TEXT NOT NULL,platform TEXT NOT NULL,account_id TEXT NOT NULL,
        report JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    conn.execute('''CREATE TABLE IF NOT EXISTS marketing_monitor_health (
        shop TEXT NOT NULL,platform TEXT NOT NULL,account_id TEXT NOT NULL,stage TEXT NOT NULL,
        status TEXT NOT NULL,checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(shop,platform,account_id,stage))''')
    conn.execute('CREATE INDEX IF NOT EXISTS marketing_analysis_shop ON marketing_analyses(shop,id DESC)')
    conn.execute('''CREATE TABLE IF NOT EXISTS marketing_alerts (
        id BIGSERIAL PRIMARY KEY,shop TEXT NOT NULL,platform TEXT NOT NULL,account_id TEXT NOT NULL,
        dedupe_key TEXT NOT NULL,analysis_id BIGINT NOT NULL REFERENCES marketing_analyses,
        evidence JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        acknowledged_at TIMESTAMPTZ,UNIQUE(shop,platform,account_id,dedupe_key))''')
    conn.execute('ALTER TABLE marketing_alerts ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ')
    conn.execute('''CREATE TABLE IF NOT EXISTS marketing_decisions (
        id BIGSERIAL PRIMARY KEY,shop TEXT NOT NULL,analysis_id BIGINT NOT NULL REFERENCES marketing_analyses,
        entity_id TEXT NOT NULL,placement TEXT NOT NULL,code TEXT NOT NULL,
        outcome TEXT NOT NULL CHECK(outcome IN ('accepted_for_review','rejected','deferred')),
        note TEXT NOT NULL DEFAULT '',created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')


def _identity(platform,account_id):
    if platform not in ('meta','tiktok') or not isinstance(account_id,str) or not account_id.isdigit():
        raise ValueError('Platform and account ID required')


def save_policy(platform,account_id,policy):
    _identity(platform,account_id)
    policy=validate_policy(policy)
    event=policy['purchase_event']
    allowed={'meta':{'purchase','omni_purchase','offsite_conversion.fb_pixel_purchase','onsite_web_purchase'},
             'tiktok':{'tiktok_website_complete_payment'}}
    if event is not None and event not in allowed[platform]:
        raise ValueError('Select a supported explicit purchase event, never a generic conversion or checkout')
    # Require an archived, identified account; never attach costs to a guessed account.
    accounts=status()['accounts']
    match=next((a for a in accounts if a['platform']==platform and a['id']==account_id),None)
    if not match or match['currency']!=policy['currency']:raise ValueError('Saved account/currency does not match')
    with _connect() as c:
        prepare_manager(c)
        c.execute('''INSERT INTO marketing_policies(shop,platform,account_id,policy)
            VALUES (%s,%s,%s,%s) ON CONFLICT(shop,platform,account_id)
            DO UPDATE SET policy=EXCLUDED.policy,updated_at=NOW(),next_monitor_at=NOW()''',(_scope(),platform,account_id,Jsonb(policy)))
    return policy


def load_policy(platform,account_id):
    _identity(platform,account_id)
    with _connect() as c:
        prepare_manager(c)
        row=c.execute('SELECT policy FROM marketing_policies WHERE shop=%s AND platform=%s AND account_id=%s',(_scope(),platform,account_id)).fetchone()
    return row[0] if row else None


def run_analysis(platform,account_id,start_date,end_date,level='campaign',compare=True):
    policy=load_policy(platform,account_id)
    if policy is None:raise ValueError('Configure costs, event mapping and decision policy first')
    report=read_history(platform,account_id,start_date,end_date,level)
    previous=None
    if compare:
        from datetime import date
        start,end=date.fromisoformat(start_date),date.fromisoformat(end_date)
        prev_end=start-timedelta(days=1);prev_start=prev_end-(end-start)
        previous=read_history(platform,account_id,prev_start.isoformat(),prev_end.isoformat(),level)
    analysis=analyze_report(report,policy,previous)
    from marketing_diagnostics import diagnose
    analysis['diagnostics']=diagnose(report,policy)
    eligible=[e for e in analysis['entities'] if e['metrics']['purchases'] is not None
              and Decimal(e['metrics']['purchases'])>=Decimal(policy['rules']['minimum_purchases'])]
    quality=[w for w in analysis['data_warnings'] if w!='comparison_unavailable']
    analysis['descriptive_rankings']={
        'by_purchase_cpa':[] if quality else [{'entity_id':e['entity_id'],'placement':e['placement'],'purchase_cpa':e['metrics']['purchase_cpa']}
            for e in sorted([e for e in eligible if e['metrics']['purchase_cpa'] is not None],key=lambda e:Decimal(e['metrics']['purchase_cpa']))],
        'by_roas':[] if quality else [{'entity_id':e['entity_id'],'placement':e['placement'],'roas':e['metrics']['roas']}
            for e in sorted([e for e in eligible if e['metrics']['roas'] is not None],key=lambda e:Decimal(e['metrics']['roas']),reverse=True)],
        'interpretation':'Descriptive ranking within this account/range/grain only. Different objectives/audiences are not controlled; no causal winner or significant experiment is claimed.'}

    analysis['source_days']=report['days']
    apply_shopify_guard(analysis,policy,platform,account_id,start_date,end_date,level)
    with _connect() as c:
        prepare_manager(c)
        aid=c.execute('''INSERT INTO marketing_analyses(shop,platform,account_id,report)
            VALUES (%s,%s,%s,%s) RETURNING id''',(_scope(),platform,account_id,Jsonb(analysis))).fetchone()[0]
        findings=[{**f,'entity_id':e['entity_id'],'placement':e['placement'],'metrics':e['metrics']}
                  for e in analysis['entities'] for f in e['findings'] if f['priority']=='high']
        findings+=analysis['spend_alerts']
        if analysis['data_warnings']:
            findings.append({'code':'data_quality','warnings':analysis['data_warnings'],'decision':'review_data','executed':False})
        c.execute('''UPDATE marketing_alerts AS alerts SET resolved_at=NOW()
            FROM marketing_analyses AS old WHERE alerts.analysis_id=old.id AND alerts.shop=%s
            AND alerts.platform=%s AND alerts.account_id=%s AND old.report->>'end_date'=%s
            AND old.report->>'level'=%s AND alerts.resolved_at IS NULL''',(_scope(),platform,account_id,end_date,level))
        for f in findings:
            # One alert per condition/entity/report ending day, not per worker poll.
            key=hashlib.sha256(json.dumps([level,end_date,f.get('entity_id'),f.get('placement'),f['code'],f.get('date')]).encode()).hexdigest()
            c.execute('''INSERT INTO marketing_alerts(shop,platform,account_id,dedupe_key,analysis_id,evidence)
                VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(shop,platform,account_id,dedupe_key) DO UPDATE SET analysis_id=EXCLUDED.analysis_id,evidence=EXCLUDED.evidence,resolved_at=NULL''',
                (_scope(),platform,account_id,key,aid,Jsonb(f)))
    return {'analysis_id':aid,**analysis}


def dashboard():
    with _connect() as c:
        prepare_manager(c)
        health=c.execute('SELECT platform,account_id,stage,status,checked_at FROM marketing_monitor_health WHERE shop=%s',(_scope(),)).fetchall()
        policies=c.execute('SELECT platform,account_id,policy FROM marketing_policies WHERE shop=%s',(_scope(),)).fetchall()
        analyses=c.execute('SELECT id,platform,account_id,report,created_at FROM marketing_analyses WHERE shop=%s ORDER BY id DESC LIMIT 20',(_scope(),)).fetchall()
        alerts=c.execute('SELECT id,platform,account_id,evidence,created_at,acknowledged_at,resolved_at FROM marketing_alerts WHERE shop=%s ORDER BY id DESC LIMIT 100',(_scope(),)).fetchall()
        decisions=c.execute('SELECT id,analysis_id,entity_id,placement,code,outcome,note,created_at FROM marketing_decisions WHERE shop=%s ORDER BY id DESC LIMIT 100',(_scope(),)).fetchall()
    def rows(names,data):return [dict(zip(names,[v.isoformat() if isinstance(v,datetime) else v for v in r])) for r in data]
    return {'monitor_health':rows(('platform','account_id','stage','status','checked_at'),health),'policies':rows(('platform','account_id','policy'),policies),
            'analyses':rows(('id','platform','account_id','report','created_at'),analyses),
            'alerts':rows(('id','platform','account_id','evidence','created_at','acknowledged_at','resolved_at'),alerts),
            'decisions':rows(('id','analysis_id','entity_id','placement','code','outcome','note','created_at'),decisions),
            'execution_enabled':False}


def acknowledge(alert_id):
    with _connect() as c:
        prepare_manager(c)
        return c.execute('''UPDATE marketing_alerts SET acknowledged_at=COALESCE(acknowledged_at,NOW())
            WHERE id=%s AND shop=%s RETURNING id''',(alert_id,_scope())).fetchone() is not None


def record_decision(analysis_id,entity_id,placement,code,outcome,note=''):
    if outcome not in ('accepted_for_review','rejected','deferred') or not isinstance(note,str) or len(note)>2000:
        raise ValueError('Invalid review decision')
    with _connect() as c:
        prepare_manager(c)
        row=c.execute('SELECT report FROM marketing_analyses WHERE id=%s AND shop=%s',(analysis_id,_scope())).fetchone()
        finding=next((f for e in (row[0]['entities'] if row else []) if e['entity_id']==entity_id and e['placement']==placement
                      for f in e['findings'] if f['code']==code),None)
        if not finding:raise ValueError('Decision evidence not found')
        # Acceptance only records intent. It cannot call any advertising adapter.
        rid=c.execute('''INSERT INTO marketing_decisions(shop,analysis_id,entity_id,placement,code,outcome,note)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id''',(_scope(),analysis_id,entity_id,placement,code,outcome,note)).fetchone()[0]
    return {'id':rid,'outcome':outcome,'executed':False}


def schedule_monitoring():
    """Opt-in hourly refresh requests; runs in the existing advertising worker."""
    from advertising_sync import queue_sync
    accounts={(a['platform'],a['id']):a for a in status()['accounts']}
    now=datetime.now(timezone.utc)
    with _connect() as c:
        prepare_manager(c)
        policies=c.execute('''SELECT platform,account_id,policy FROM marketing_policies
            WHERE shop=%s AND next_monitor_at<=NOW() FOR UPDATE SKIP LOCKED''',(_scope(),)).fetchall()
        selected=[]
        for platform,aid,policy in policies:
            if policy.get('monitoring_enabled'):
                c.execute('UPDATE marketing_policies SET next_monitor_at=NOW()+INTERVAL \'1 hour\' WHERE shop=%s AND platform=%s AND account_id=%s',(_scope(),platform,aid))
                selected.append((platform,aid,policy))
    for platform,aid,policy in selected:
        account=accounts.get((platform,aid))
        if not account:continue
        # Keep a conversion-delay buffer and request both seven-day periods.
        last=now.astimezone(ZoneInfo(account['timezone'])).date()-timedelta(days=1+int(Decimal(policy['rules']['attribution_delay_days'])))
        first=last-timedelta(days=13)
        try:
            with _connect() as c:
                pending=c.execute("SELECT 1 FROM advertising_sync_runs WHERE shop=%s AND platform=%s AND account_id=%s AND status IN ('queued','running')",(_scope(),platform,aid)).fetchone()
            if not pending:queue_sync(platform,first.isoformat(),last.isoformat(),expected_account_id=aid)
            record_monitor_health(platform,aid,'refresh','queued_or_pending')
        except Exception:
            record_monitor_health(platform,aid,'refresh','failed')


def record_monitor_health(platform,account_id,stage,state):
    with _connect() as c:
        prepare_manager(c)
        c.execute('''INSERT INTO marketing_monitor_health(shop,platform,account_id,stage,status)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(shop,platform,account_id,stage)
            DO UPDATE SET status=EXCLUDED.status,checked_at=NOW()''',(_scope(),platform,account_id,stage,state))


def analyze_completed_sync(platform,account_id,first,last):
    policy=load_policy(platform,account_id)
    if not policy or not policy['monitoring_enabled']:return
    start=max(first,last-timedelta(days=6))
    try:
        from shopify_reconciliation import reconcile_orders
        reconcile_orders(platform,account_id,start.isoformat(),last.isoformat())
        record_monitor_health(platform,account_id,'shopify_reconciliation','completed')
    except Exception:record_monitor_health(platform,account_id,'shopify_reconciliation','failed_or_unavailable')
    try:
        run_analysis(platform,account_id,start.isoformat(),last.isoformat())
        record_monitor_health(platform,account_id,'analysis','completed')
    except Exception:record_monitor_health(platform,account_id,'analysis','failed')


def apply_shopify_guard(analysis,policy,platform,account_id,start,end,level):
    """No scaling proposal by default without fresh matched paid-order evidence.

    Even a match does not establish incrementality or exact platform attribution.
    """
    policy=validate_policy(policy)
    with _connect() as c:
        prepare_manager(c)
        row=c.execute('''SELECT report FROM marketing_reconciliations WHERE shop=%s AND platform=%s
            AND account_id=%s AND report->>'start_date'=%s AND report->>'end_date'=%s
            ORDER BY id DESC LIMIT 1''',(_scope(),platform,account_id,start,end)).fetchone()
        parents=c.execute('''SELECT level,entity_id,parent_id FROM advertising_entities
            WHERE shop=%s AND platform=%s AND account_id=%s''',(_scope(),platform,account_id)).fetchall()
    reconciliation=row[0] if row else None
    fresh=False
    if reconciliation:
        try:
            stamp=datetime.fromisoformat(reconciliation['fetched_at'])
            age=datetime.now(timezone.utc)-stamp
            fresh=(stamp.tzinfo is not None and timedelta(0)<=age<=timedelta(hours=24)
                and reconciliation['ads_complete'] and reconciliation['shop_currency']==analysis['currency']
                and reconciliation['currency_match'])
        except (ValueError,TypeError,KeyError):pass
    confirmed={x['campaign_id'] for x in (reconciliation.get('matched_campaigns',[]) if fresh else []) if x['paid_orders']>0}
    parent={(l,i):p for l,i,p in parents}
    analysis['shopify_review']={'fresh_matching_cohort':fresh,'matched_paid_campaigns':sorted(confirmed),
        'required_for_scaling':policy.get('require_shopify_confirmation',True),
        'limitation':'Observed paid last-touch UTM evidence only, not causal or exact event-ID proof.'}
    if not policy.get('require_shopify_confirmation',True):return
    for entity in analysis['entities']:
        campaign=entity['entity_id'] if level=='campaign' else parent.get((level,entity['entity_id']))
        if level=='ad':campaign=parent.get(('adgroup',campaign))
        matched=[]
        if fresh:
            if level=='campaign':matched=[x for x in reconciliation.get('matched_campaigns',[]) if x['campaign_id']==campaign]
            elif level=='ad':matched=[x for x in reconciliation.get('matched_ads',[]) if x['ad_id']==entity['entity_id'] and x['campaign_id']==campaign]
            else:matched=[x for x in reconciliation.get('matched_ads',[]) if parent.get(('ad',x['ad_id']))==entity['entity_id'] and x['campaign_id']==campaign]
        count=sum(x['paid_orders'] for x in matched)
        cash=sum((Decimal(x['received']) for x in matched),Decimal(0))
        refunds=sum((Decimal(x['refunded']) for x in matched),Decimal(0))
        costs=policy['costs'];contribution=None
        if matched and all(v is not None for v in costs.values()) and entity['metrics']['spend'] is not None:
            contribution=cash-refunds-cash*(Decimal(costs['payment_fee_percent'])+Decimal(costs['tax_percent_of_revenue']))/100-count*(Decimal(costs['product_cost_per_order'])+Decimal(costs['shipping_cost_per_order'])+Decimal(costs['fixed_fee_per_order']))-Decimal(entity['metrics']['spend'])
        entity['shopify_cash_evidence']={'matched_paid_orders':count,'received':str(cash),'refunded':str(refunds),
            'estimated_contribution_after_ads':str(contribution) if contribution is not None else None,
            'basis':'Observed UTM cohort cash less actual cohort refunds and owner average costs/fees/tax estimate. Not audited profit.'}
        enough=(fresh and campaign in confirmed and count>=Decimal(policy['rules']['minimum_purchases']) and contribution is not None and contribution>0)
        for finding in entity['findings']:
            if finding['decision']=='propose_budget_increase' and not enough:
                finding.update(code='shopify_confirmation_required',priority='high',decision='verify_shopify_before_scaling',
                    reason='زيادة الميزانية مؤجلة حتى تتوفر عينة طلبات مدفوعة مطابقة للمستوى مع مساهمة نقدية تقديرية موجبة؛ ترتيب ROAS وحده لا يكفي.',requires_owner_approval=False)
                finding.pop('maximum_increase_percent',None)



ANALYSIS_TOOL={'type':'function','name':'analyze_ad_performance',
 'description':'Analyze archived ad performance using saved owner costs and exact purchase event. Produces evidence, estimated contribution, comparison and review-only recommendations. Does not execute decisions. Disclose data warnings and assumptions.',
 'parameters':{'type':'object','properties':{k:{'type':'string'} for k in ('platform','account_id','start_date','end_date','level')},
 'required':['platform','account_id','start_date','end_date','level'],'additionalProperties':False},'strict':True}
