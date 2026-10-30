"""Durable daily ad warehouse; no credentials, customer identifiers or ad writes."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from zoneinfo import ZoneInfo
from psycopg.types.json import Jsonb
from database import _connect, store_key

ATTRIBUTION = {
    'meta': 'provider-default:publisher_platform:actions-not-shopify-orders:v1',
    'tiktok': 'provider-default:auction:conversion-not-necessarily-purchase:v1',
}


def prepare(conn):
    if conn.execute("SELECT to_regclass('advertising_schema_versions')").fetchone()[0]:
        if conn.execute('SELECT 1 FROM advertising_schema_versions WHERE version=1').fetchone():
            return
    conn.execute('SELECT pg_advisory_xact_lock(7432110)')
    conn.execute(Path(__file__).with_name('migrations').joinpath('001_advertising.sql').read_text())


def initialize():
    with _connect() as conn:
        prepare(conn)
    return {'schema_version': 1}


def _scope():
    shop = store_key()
    if not shop:
        raise ValueError('SHOPIFY_STORE_DOMAIN is required')
    return shop


def date_range(start, end, maximum=92):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first > last or (last-first).days >= maximum:
        raise ValueError(f'Choose between 1 and {maximum} inclusive days')
    return first, last


def number(value):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise ValueError('Invalid numeric metric')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('Invalid numeric metric') from None
    if not result.is_finite() or result < 0:
        raise ValueError('Invalid numeric metric')
    return result


def _account(platform, account):
    if platform not in ATTRIBUTION or not isinstance(account, dict):
        raise ValueError('Unsupported advertising account')
    if not re.fullmatch(r'\d+', str(account.get('id', ''))):
        raise ValueError('Invalid account ID')
    if not re.fullmatch(r'[A-Z]{3}', account.get('currency', '')):
        raise ValueError('Account currency must be confirmed before storing money')
    ZoneInfo(account['timezone'])


def save_day(platform, account, day, report, requested_at, run_id=None, level='campaign', validate_only=False):
    """Publish a complete day atomically; re-sync replaces, never adds duplicates.

    Snapshots keep revisions for late attribution. Only the newest request can
    become current, even if an older network request finishes afterward.
    """
    shop = _scope()
    _account(platform, account)
    account={**account,'id':str(account['id'])}
    report_day = date.fromisoformat(day)
    if level not in ('campaign', 'adgroup', 'ad'):
        raise ValueError('Unsupported report level')
    if requested_at.tzinfo is None:
        raise ValueError('Timezone-aware request timestamp required')
    if report_day >= requested_at.astimezone(ZoneInfo(account['timezone'])).date():
        raise ValueError('Only completed account-local days can be archived')
    if report.get('platform') != platform or report.get('level', 'campaign') != level:
        raise ValueError('Report platform/level mismatch')
    if report.get('account') and str(report['account'].get('id')) != str(account['id']):
        raise ValueError('Report account mismatch')
    if report.get('verified') is not True or report.get('start_date') != day or report.get('end_date') != day:
        raise ValueError('A verified complete single-day report is required')
    rows = report.get('rows')
    if not isinstance(rows, list):
        raise ValueError('Invalid report rows')
    seen, cleaned = set(), []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid report row')
        entity_id = str(row.get('entity_id') or (row.get('campaign_id') if level == 'campaign' else '') or '')
        placement = row.get('placement')
        if not entity_id.isdigit() or not isinstance(placement, str) or not placement:
            raise ValueError('Missing entity ID or placement')
        key = (entity_id, placement)
        if key in seen:
            raise ValueError('Duplicate report grain; refusing to double count')
        seen.add(key)
        if row.get('currency') not in (None, account['currency']):
            raise ValueError('Report currency does not match account')
        # No arbitrary provider payloads: tokens/PII cannot enter JSONB via rows.
        metrics = {k: str(number(row[k])) if row.get(k) is not None else None
                   for k in ('spend','impressions','clicks','ctr','cpc','conversion','reach','frequency','link_clicks','video_plays','video_2s','video_6s','video_p25','video_p50','video_p75','video_p100')}
        lists = []
        for field in ('actions', 'action_values'):
            values = row.get(field, [])
            if not isinstance(values, list):
                raise ValueError('Invalid action list')
            out = []
            for item in values:
                if not isinstance(item, dict) or not isinstance(item.get('action_type'), str):
                    raise ValueError('Invalid action')
                # Preserve separate windows; never sum aliases or windows.
                action = {'action_type': item['action_type']}
                for k, v in item.items():
                    if k == 'value' or re.fullmatch(r'\d+d_(click|view)', k):
                        action[k] = None if v is None else str(number(v))
                out.append(action)
            lists.append(out)
        cleaned.append((entity_id, placement, row.get('entity_name') or row.get('campaign_name'), row.get('parent_id'), metrics, *lists))
    if validate_only:
        return {'validated':True,'rows':len(cleaned)}
    with _connect() as conn:
        prepare(conn)
        # Serialize account metadata + snapshot publication across processes.
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))',
                     (f'{shop}:{platform}:{account["id"]}',))
        existing = conn.execute('''SELECT currency, timezone FROM advertising_accounts
            WHERE shop=%s AND platform=%s AND account_id=%s''', (shop,platform,account['id'])).fetchone()
        if existing and tuple(existing) != (account['currency'], account['timezone']):
            raise ValueError('Account currency/timezone changed; reconcile before re-sync')
        conn.execute('''INSERT INTO advertising_accounts(shop,platform,account_id,name,currency,timezone,metadata_source)
            VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(shop,platform,account_id)
            DO UPDATE SET name=EXCLUDED.name, metadata_source=EXCLUDED.metadata_source, updated_at=NOW()''',
            (shop,platform,account['id'],account.get('name'),account['currency'],account['timezone'],account.get('metadata_source','api')))
        attr = ATTRIBUTION[platform]
        current = conn.execute('''SELECT s.requested_at FROM advertising_partitions p
            JOIN advertising_snapshots s ON s.id=p.snapshot_id
            WHERE p.shop=%s AND p.platform=%s AND p.account_id=%s AND p.report_date=%s
            AND p.level=%s AND p.attribution=%s''', (shop,platform,account['id'],report_day,level,attr)).fetchone()
        if current and current[0] >= requested_at:
            return {'published':False, 'reason':'newer_snapshot_exists'}
        sid = conn.execute('''INSERT INTO advertising_snapshots
            (shop,platform,account_id,report_date,level,attribution,requested_at,run_id,row_count)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (shop,platform,account['id'],report_day,level,attr,requested_at,run_id,len(cleaned))).fetchone()[0]
        for entity, placement, name, parent, metrics, actions, values in cleaned:
            conn.execute('''INSERT INTO advertising_entities(shop,platform,account_id,level,entity_id,name,parent_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(shop,platform,account_id,level,entity_id)
                DO UPDATE SET name=EXCLUDED.name,parent_id=EXCLUDED.parent_id,updated_at=NOW()''', (shop,platform,account['id'],level,entity,name,parent))
            conn.execute('''INSERT INTO advertising_facts
                (snapshot_id,entity_id,placement,spend,impressions,clicks,metrics,actions,action_values)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (sid,entity,placement,
                number(metrics['spend']),number(metrics['impressions']),number(metrics['clicks']),
                Jsonb(metrics),Jsonb(actions),Jsonb(values)))
        conn.execute('''INSERT INTO advertising_partitions(shop,platform,account_id,report_date,level,attribution,snapshot_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(shop,platform,account_id,report_date,level,attribution)
            DO UPDATE SET snapshot_id=EXCLUDED.snapshot_id''', (shop,platform,account['id'],report_day,level,attr,sid))
    return {'published':True, 'snapshot_id':sid, 'rows':len(cleaned)}


def read_history(platform, account_id, start_date, end_date, level='campaign'):
    """Explicit account and campaign grain prevent mixing accounts or levels."""
    shop = _scope()
    if level not in ('campaign','adgroup','ad'):
        raise ValueError('Unsupported report level')
    if platform not in ATTRIBUTION or not str(account_id).isdigit():
        raise ValueError('Choose a platform and numeric account ID')
    first,last = date_range(start_date,end_date)
    with _connect() as conn:
        prepare(conn)
        account = conn.execute('''SELECT name,currency,timezone FROM advertising_accounts
            WHERE shop=%s AND platform=%s AND account_id=%s''', (shop,platform,account_id)).fetchone()
        days = conn.execute('''SELECT p.report_date,s.saved_at,s.row_count FROM advertising_partitions p
            JOIN advertising_snapshots s ON s.id=p.snapshot_id
            WHERE p.shop=%s AND p.platform=%s AND p.account_id=%s AND p.level=%s
            AND p.attribution=%s AND p.report_date BETWEEN %s AND %s ORDER BY p.report_date''',
            (shop,platform,account_id,level,ATTRIBUTION[platform],first,last)).fetchall()
        rows = conn.execute('''SELECT p.report_date,f.entity_id,e.name,f.placement,f.spend,f.impressions,
            f.clicks,f.metrics,f.actions,f.action_values FROM advertising_partitions p
            JOIN advertising_facts f ON f.snapshot_id=p.snapshot_id
            LEFT JOIN advertising_entities e ON e.shop=p.shop AND e.platform=p.platform
                AND e.account_id=p.account_id AND e.level=p.level AND e.entity_id=f.entity_id
            WHERE p.shop=%s AND p.platform=%s AND p.account_id=%s AND p.level=%s
            AND p.attribution=%s AND p.report_date BETWEEN %s AND %s
            ORDER BY p.report_date,f.entity_id,f.placement LIMIT 5001''',
            (shop,platform,account_id,level,ATTRIBUTION[platform],first,last)).fetchall()
    if len(rows)>5000:
        raise ValueError('Report too large; select a shorter range')
    present = {r[0] for r in days}
    missing = [(first+timedelta(days=i)).isoformat() for i in range((last-first).days+1)
               if first+timedelta(days=i) not in present]
    groups = {}
    details = []
    for day, entity, name, placement, spend, impressions, clicks, metrics, actions, values in rows:
        group = groups.setdefault(placement, {'placement':placement,'spend':[],'impressions':[],'clicks':[]})
        for key,value in [('spend',spend),('impressions',impressions),('clicks',clicks)]:
            group[key].append(value)
        details.append({'date':day.isoformat(),'entity_id':entity,'entity_name':name,
                        'placement':placement,'metrics':metrics,'actions':actions,'action_values':values})
    totals = []
    for g in groups.values():
        t={'placement':g['placement']}
        for key in ('spend','impressions','clicks'):
            t[key] = None if any(v is None for v in g[key]) else str(sum(g[key],Decimal(0)))
        spend,clicks,impressions = (number(t[k]) for k in ('spend','clicks','impressions'))
        t['cpc'] = str(spend/clicks) if spend is not None and clicks else None
        t['cpm'] = str(spend*1000/impressions) if spend is not None and impressions else None
        t['ctr_percent'] = str(clicks*100/impressions) if clicks is not None and impressions else None
        totals.append(t)
    return {'platform':platform,'level':level,'account_id':account_id,'account':None if not account else
            {'name':account[0],'currency':account[1],'timezone':account[2]},
            'start_date':start_date,'end_date':end_date,'source':'stored_daily_snapshots',
            'live':False,'complete':not missing,'missing_dates':missing,
            'days':[{'date':d.isoformat(),'saved_at':at.isoformat(),'rows':count} for d,at,count in days],
            'totals_for_available_days':totals,'rows':details,
            'attribution':ATTRIBUTION[platform],
            'limitations':['Stored data may be stale; inspect saved_at. Missing dates are unavailable, not zero.',
                'Do not sum overlapping action types/windows. TikTok conversion may not mean purchase.',
                'Reach/frequency are not additive; Shopify orders and profit are not inferred.']}


def status():
    with _connect() as conn:
        prepare(conn)
        accounts = conn.execute('''SELECT a.platform,a.account_id,a.name,a.currency,a.timezone,
            MAX(s.saved_at) FROM advertising_accounts a LEFT JOIN advertising_snapshots s
            ON s.shop=a.shop AND s.platform=a.platform AND s.account_id=a.account_id
            WHERE a.shop=%s GROUP BY a.platform,a.account_id,a.name,a.currency,a.timezone''',(_scope(),)).fetchall()
        runs = conn.execute('''SELECT id,platform,status,start_date,end_date,days_saved,error_code,started_at,completed_at
            FROM advertising_sync_runs WHERE shop=%s ORDER BY id DESC LIMIT 20''',(_scope(),)).fetchall()
    def serial(values):
        return [v.isoformat() if isinstance(v,(date,datetime)) else v for v in values]
    return {'schema_version':1,'accounts':[dict(zip(('platform','id','name','currency','timezone','last_saved_at'),serial(r))) for r in accounts],
            'recent_runs':[dict(zip(('id','platform','status','start_date','end_date','days_saved','error_code','started_at','completed_at'),serial(r))) for r in runs]}

HISTORY_TOOL = {'type':'function','name':'read_ad_history',
    'description':'Read stored daily campaign results for an explicit platform/account and up to 92 inclusive dates at one level: campaign, adgroup or ad. Historical archive only, never live; disclose missing dates and freshness. Never sum overlapping actions or confuse TikTok conversions with purchases.',
    'parameters':{'type':'object','properties':{k:{'type':'string'} for k in ('platform','account_id','start_date','end_date','level')},
        'required':['platform','account_id','start_date','end_date','level'],'additionalProperties':False},'strict':True}

STATUS_TOOL = {'type':'function','name':'read_ad_archive_status',
    'description':'List saved ad accounts, account IDs, currency, timezone, sync jobs and archive freshness. Use before read_ad_history if the account ID is unknown. This is stored metadata, not verification of a live connection.',
    'parameters':{'type':'object','properties':{},'required':[],'additionalProperties':False},'strict':True}
