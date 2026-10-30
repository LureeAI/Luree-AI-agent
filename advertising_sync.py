"""Read-only provider ingestion and durable, owner-requested sync jobs."""
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from database import _connect
from advertising_store import prepare, _scope, date_range, save_day
from ads_service import configuration, meta_account, meta_report, tiktok_report, AdsError, _json_get
import json


def tiktok_account():
    if not configuration()['tiktok']['configured']:
        raise AdsError('TikTok credentials are missing')
    aid = os.environ['TIKTOK_ADVERTISER_ID'].strip()
    if not aid.isdigit():
        raise AdsError('Invalid TikTok account ID')
    data = _json_get('https://business-api.tiktok.com/open_api/v1.3/advertiser/info/',
        {'Access-Token':os.environ['TIKTOK_ACCESS_TOKEN'].strip()},
        {'advertiser_ids':json.dumps([aid]),'fields':json.dumps(['advertiser_id','name','currency','timezone'])})
    body=data.get('data')
    rows=body.get('list') if isinstance(body,dict) else None
    if data.get('code') != 0 or not isinstance(rows,list) or len(rows)!=1:
        raise AdsError('Could not verify TikTok account metadata')
    row=rows[0]
    if not isinstance(row,dict) or str(row.get('advertiser_id'))!=aid:
        raise AdsError('Unexpected TikTok account')
    account={'id':aid,'name':row.get('name'),'currency':row.get('currency'),
             'timezone':row.get('timezone'),'metadata_source':'advertiser/info API'}
    try:
        from advertising_store import _account
        _account('tiktok',account)
    except (ValueError,TypeError,KeyError):
        # Numeric or GMT-offset provider zones are not silently interpreted as Seoul.
        raise AdsError('TikTok account currency/timezone could not be verified') from None
    return account


def account_for(platform):
    if platform == 'meta':
        return meta_account()
    if platform == 'tiktok':
        return tiktok_account()
    raise ValueError('Choose meta or tiktok')


def queue_sync(platform, start_date, end_date, expected_account_id=None):
    first,last=date_range(start_date,end_date,maximum=31)
    account=account_for(platform)
    if expected_account_id is not None and account['id']!=expected_account_id:
        raise ValueError('Configured account differs from monitored account')
    today=datetime.now(ZoneInfo(account['timezone'])).date()
    if last>=today:
        raise ValueError('اختاري أيامًا مكتملة قبل اليوم حسب توقيت حساب الإعلان.')
    with _connect() as conn:
        prepare(conn)
        conn.execute('SELECT pg_advisory_xact_lock(7432111)')
        pending=conn.execute('''SELECT COUNT(*) FROM advertising_sync_runs WHERE shop=%s
            AND status IN ('queued','running')''',(_scope(),)).fetchone()[0]
        if pending>=4:
            raise ValueError('هناك طلبات مزامنة قيد الانتظار؛ انتظري اكتمالها.')
        rid=conn.execute('''INSERT INTO advertising_sync_runs
            (shop,platform,account_id,start_date,end_date,status) VALUES (%s,%s,%s,%s,%s,'queued') RETURNING id''',
            (_scope(),platform,account['id'],first,last)).fetchone()[0]
    return {'id':rid,'status':'queued','account':account,'requires_worker':True}


def process_one_sync():
    # A session lock excludes overlapping workers without holding a transaction
    # open during provider requests. Process crashes release it automatically.
    with _connect() as lease:
        prepare(lease)
        lease.commit()
        locked=lease.execute('SELECT pg_try_advisory_lock(hashtextextended(%s, 0))',
                            ('ads-sync:'+_scope(),)).fetchone()[0]
        lease.commit()
        if not locked:
            return False
        try:
            # A prior crashed job cannot be mistaken for a successful complete run.
            lease.execute('''UPDATE advertising_sync_runs SET status='failed',error_code='worker_interrupted',
                completed_at=NOW() WHERE shop=%s AND status='running' ''',(_scope(),))
            job=lease.execute('''SELECT id,platform,account_id,start_date,end_date FROM advertising_sync_runs
                WHERE shop=%s AND status='queued' ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED''',(_scope(),)).fetchone()
            if not job:
                lease.commit()
                return False
            rid,platform,aid,first,last=job
            lease.execute("UPDATE advertising_sync_runs SET status='running',started_at=NOW() WHERE id=%s",(rid,))
            lease.commit()
            saved=0
            try:
                account=account_for(platform)
                if account['id']!=aid:
                    raise AdsError('Account changed since sync was requested')
                for offset in range((last-first).days+1):
                    day=(first+timedelta(days=offset)).isoformat()
                    # Keep each level distinct: campaign, ad group and ad totals
                    # must never be added together.
                    reports={}
                    requested_at=datetime.now(timezone.utc)
                    for level in ('campaign','adgroup','ad'):
                        reports[level]=(meta_report(day,day,account_info=account,level=level,precise=True,website_metrics=True)
                                if platform=='meta' else tiktok_report(day,day,level=level,precise=True,website_metrics=True))
                    for level,report in reports.items():
                        save_day(platform,account,day,report,requested_at,level=level,validate_only=True)
                    if platform=='tiktok':
                        roll_up_tiktok_purchases(reports)
                    for level,report in reports.items():
                        save_day(platform,account,day,report,requested_at,run_id=rid,level=level)
                    saved+=1
                    lease.execute('UPDATE advertising_sync_runs SET days_saved=%s WHERE id=%s',(saved,rid))
                    lease.commit()
                lease.execute("UPDATE advertising_sync_runs SET status='completed',completed_at=NOW() WHERE id=%s",(rid,))
            except Exception:
                # Never persist raw provider exceptions or credentials.
                lease.rollback()
                lease.execute("UPDATE advertising_sync_runs SET status='failed',error_code='sync_failed',completed_at=NOW() WHERE id=%s",(rid,))
            lease.commit()
            outcome=lease.execute('SELECT status FROM advertising_sync_runs WHERE id=%s',(rid,)).fetchone()[0]
            lease.commit()
            if outcome=='completed':
                try:
                    from marketing_manager import analyze_completed_sync
                    analyze_completed_sync(platform,aid,first,last)
                except Exception:
                    pass # Sync data remains successful; independent analysis health is recorded by the manager.
            return True
        finally:
            lease.execute('SELECT pg_advisory_unlock(hashtextextended(%s, 0))',('ads-sync:'+_scope(),))
            lease.commit()


def roll_up_tiktok_purchases(reports):
    """Campaign website conversions derive from one disjoint adgroup grain only.

    No app purchase, onsite purchase, generic conversion or cross-level totals.
    Incomplete parent IDs or absent purchase values remain unavailable.
    """
    from advertising_store import number
    from decimal import Decimal
    children=reports['adgroup']['rows']
    if any(not str(r.get('parent_id') or '').isdigit() for r in children):
        return
    for campaign in reports['campaign']['rows']:
        matched=[r for r in children if str(r['parent_id'])==str(campaign['entity_id'])]
        if not matched:continue
        for field in ('actions','action_values'):
            events=('tiktok_website_complete_payment','tiktok_website_add_to_cart','tiktok_website_landing_page_view') if field=='actions' else ('tiktok_website_complete_payment',)
            out=[]
            for event in events:
                values=[]
                for row in matched:
                    found=[v for v in row.get(field,[]) if v.get('action_type')==event]
                    values.append(number(found[0].get('value')) if len(found)==1 else None)
                if all(v is not None for v in values):
                    out.append({'action_type':event,'value':str(sum(values,Decimal(0)))})
            campaign[field]=out
