"""Owner mandates and a bounded Meta campaign watchdog.

No launch, resume, budget increase, or TikTok write adapter is implemented here.
Model output cannot authorize a mandate or execute an action.
"""
import json
import os
import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
import requests
from database import _connect, store_key
from ads_service import _json_get, configuration, AdsError
from action_service import current_campaign

LOCK = 7432110
PURCHASE = 'offsite_conversion.fb_pixel_purchase'

class ControlError(ValueError):
    pass


def money(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ControlError('يلزم مبلغ صريح؛ لا يمكن افتراض التكلفة.')
    try:
        n = Decimal(str(value))
    except InvalidOperation:
        raise ControlError('المبلغ غير صحيح.') from None
    if not n.is_finite() or n < 0 or n > Decimal('1000000000'):
        raise ControlError('المبلغ غير صحيح.')
    return n


def validate_mandate(data):
    if not isinstance(data, dict):
        raise ControlError('بيانات التفويض غير صحيحة.')
    if data.get('mode') not in ('observe', 'auto_pause'):
        raise ControlError('اختاري مراقبة أو إيقاف تلقائي ضمن القواعد.')
    cid = data.get('campaign_id')
    if not isinstance(cid, str) or not re.fullmatch(r'[0-9]{1,40}', cid):
        raise ControlError('يلزم معرف حملة Meta صحيح.')
    currency = data.get('currency')
    if not isinstance(currency, str) or not re.fullmatch('[A-Z]{3}', currency):
        raise ControlError('يلزم رمز عملة الحساب، مثل USD أو KRW.')
    amounts = {k: money(data.get(k)) for k in ('daily_limit', 'total_limit')}
    if any(n <= 0 for n in amounts.values()) or amounts['daily_limit'] > amounts['total_limit']:
        raise ControlError('الحدود يجب أن تكون موجبة؛ اليومي لا يتجاوز الإجمالي.')
    try:
        expiry = datetime.fromisoformat(data.get('expires_at', '').replace('Z', '+00:00'))
        if expiry.utcoffset() is None:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ControlError('حددي انتهاء التفويض بتاريخ وتوقيت واضحين.') from None
    now = datetime.now(timezone.utc)
    if not now < expiry <= now + timedelta(days=30):
        raise ControlError('التفويض ينتهي خلال ٣٠ يومًا كحد أقصى.')
    return dict(campaign_id=cid, currency=currency, mode=data['mode'],
                expires_at=expiry.isoformat(), **{k: str(v) for k, v in amounts.items()})


def prepare(conn):
    conn.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK,))
    conn.execute('''CREATE TABLE IF NOT EXISTS ad_mandates (
        shop TEXT NOT NULL, campaign_id TEXT NOT NULL, policy JSONB NOT NULL,
        enabled BOOLEAN NOT NULL DEFAULT TRUE, revision INTEGER NOT NULL DEFAULT 1,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY(shop,campaign_id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS ad_control_events (
        id BIGSERIAL PRIMARY KEY, shop TEXT NOT NULL, campaign_id TEXT NOT NULL,
        revision INTEGER NOT NULL, reason TEXT NOT NULL, state TEXT NOT NULL,
        evidence JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    conn.execute('CREATE INDEX IF NOT EXISTS ad_control_events_shop_id ON ad_control_events(shop,id)')
    conn.execute('''CREATE TABLE IF NOT EXISTS ad_control_health (
        shop TEXT PRIMARY KEY, checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        state TEXT NOT NULL, message TEXT NOT NULL)''')


def meta_account():
    if not configuration()['meta']['configured']:
        raise ControlError('ربط حساب Meta بالوكيل غير مكتمل.')
    account = os.environ['META_AD_ACCOUNT_ID'].removeprefix('act_').strip()
    version = os.environ['META_API_VERSION'].strip()
    if not account.isdigit() or not re.fullmatch(r'v\d+\.\d+', version):
        raise ControlError('إعداد حساب Meta غير صحيح.')
    result = _json_get(f'https://graph.facebook.com/{version}/act_{account}',
                       {'Authorization': 'Bearer ' + os.environ['META_ACCESS_TOKEN']},
                       {'fields': 'id,currency,timezone_name,account_status'})
    if result.get('id') != 'act_' + account or result.get('account_status') != 1:
        raise ControlError('حساب الإعلانات غير نشط أو غير مطابق.')
    try:
        ZoneInfo(result['timezone_name'])
    except (KeyError, ValueError, TypeError):
        raise ControlError('توقيت حساب الإعلانات غير متاح.') from None
    return result


def campaign_spend(cid, since, until):
    # A single campaign, without placement breakdowns, avoids double-counting rows.
    result = _json_get(f"https://graph.facebook.com/{os.environ['META_API_VERSION']}/{cid}/insights",
                       {'Authorization': 'Bearer ' + os.environ['META_ACCESS_TOKEN']},
                       {'fields': 'campaign_id,spend,account_currency,actions',
                        'time_range': json.dumps({'since': since, 'until': until}), 'limit': 10})
    rows = result.get('data')
    # Empty, paginated, or ambiguous data must never be treated as zero spend.
    if not isinstance(rows, list) or len(rows) != 1 or result.get('paging', {}).get('next'):
        raise ControlError('تقرير الحملة غير مكتمل أو لم يظهر بعد؛ لا نفترض أن الصرف صفر.')
    row = rows[0]
    if row.get('campaign_id') != cid or not row.get('account_currency') or row.get('spend') is None:
        raise ControlError('تقرير الحملة غير مطابق.')
    spend = money(row['spend'])
    purchases = None
    actions = row.get('actions', [])
    if isinstance(actions, list):
        found = [a for a in actions if a.get('action_type') == PURCHASE]
        if len(found) == 1:
            purchases = str(money(found[0].get('value')))
    return {'spend': str(spend), 'currency': row['account_currency'],
            'platform_attributed_purchases': purchases}


def save_mandate(data):
    policy = validate_mandate(data)
    shop = store_key()
    if not shop:
        raise ControlError('معرف المتجر غير موجود.')
    # Read and validate the real account and campaign; user JSON cannot supply evidence.
    account = meta_account()
    campaign = current_campaign(policy['campaign_id'])
    if account['currency'] != policy['currency']:
        raise ControlError('عملة التفويض تختلف عن عملة حساب الإعلان.')
    # All spend from this account-local date, including earlier spend today, counts.
    today = datetime.now(ZoneInfo(account['timezone_name'])).date().isoformat()
    policy.update(account_id=os.environ['META_AD_ACCOUNT_ID'].removeprefix('act_').strip(),
                  timezone=account['timezone_name'], start_date=today,
                  campaign_name=campaign['name'])
    with _connect() as conn:
        prepare(conn)
        old = conn.execute('SELECT policy,enabled FROM ad_mandates WHERE shop=%s AND campaign_id=%s FOR UPDATE',
                           (shop, policy['campaign_id'])).fetchone()
        # Editing, expiring, or revoking cannot silently reset the spend window.
        if old:
            policy['start_date'] = old[0]['start_date']
        conn.execute('''INSERT INTO ad_mandates(shop,campaign_id,policy) VALUES (%s,%s,%s::jsonb)
            ON CONFLICT(shop,campaign_id) DO UPDATE SET policy=EXCLUDED.policy,enabled=TRUE,
            revision=ad_mandates.revision+1,updated_at=NOW()''',
                     (shop, policy['campaign_id'], json.dumps(policy)))
        conn.execute('''INSERT INTO ad_control_events(shop,campaign_id,revision,reason,state,evidence)
            SELECT shop,campaign_id,revision,'mandate_saved','recorded',policy FROM ad_mandates
            WHERE shop=%s AND campaign_id=%s''', (shop, policy['campaign_id']))
    return policy


def revoke_mandate(cid):
    with _connect() as conn:
        prepare(conn)
        return conn.execute('''UPDATE ad_mandates SET enabled=FALSE,revision=revision+1,updated_at=NOW()
            WHERE shop=%s AND campaign_id=%s RETURNING campaign_id''', (store_key(), cid)).fetchone() is not None


def evaluate(policy, snapshot, now=None):
    """Pure, deterministic limits; LLM suggestions cannot bypass them."""
    now = now or datetime.now(timezone.utc)
    checked = datetime.fromisoformat(snapshot['checked_at'])
    if checked.utcoffset() is None or not 0 <= (now - checked).total_seconds() <= 120:
        return 'stale_data'
    if snapshot['account_id'] != policy['account_id'] or snapshot['currency'] != policy['currency']:
        return 'account_mismatch'
    if snapshot['status'] != 'ACTIVE':
        return 'not_active'
    if now >= datetime.fromisoformat(policy['expires_at']):
        return 'mandate_expired'
    if money(snapshot['total_spend']) >= money(policy['total_limit']):
        return 'total_limit'
    if money(snapshot['daily_spend']) >= money(policy['daily_limit']):
        return 'daily_limit'
    return 'within_limits'


def pause_campaign(cid):
    """One write attempt. Caller durably records intent first; never auto-retries."""
    response = requests.post(f"https://graph.facebook.com/{os.environ['META_API_VERSION']}/{cid}",
        headers={'Authorization': 'Bearer ' + os.environ['META_ACCESS_TOKEN']},
        data={'status': 'PAUSED'}, timeout=20, allow_redirects=False)
    if response.status_code != 200 or response.json().get('success') is not True:
        raise ControlError('لم يتم تأكيد الإيقاف من Meta.')
    if current_campaign(cid).get('status') != 'PAUSED':
        raise ControlError('لم يتم التحقق من حالة الحملة بعد الإيقاف.')


def scan_ads():
    shop = store_key()
    if not shop:
        return False
    with _connect() as conn:
        prepare(conn)
        conn.commit()
        # Session lock survives intent commits and prevents two workers from sending the same pause.
        if not conn.execute('SELECT pg_try_advisory_lock(%s)', (LOCK,)).fetchone()[0]:
            return False
        try:
            health = conn.execute('SELECT checked_at FROM ad_control_health WHERE shop=%s', (shop,)).fetchone()
            if health and (datetime.now(timezone.utc) - health[0]).total_seconds() < 240:
                return False
            pending = conn.execute("SELECT id,campaign_id FROM ad_control_events WHERE shop=%s AND state='executing'", (shop,)).fetchall()
            for eid, cid in pending:
                try:
                    state = 'paused' if current_campaign(cid).get('status') == 'PAUSED' else 'needs_review'
                except Exception:
                    state = 'needs_review'
                conn.execute('UPDATE ad_control_events SET state=%s,updated_at=NOW() WHERE id=%s', (state, eid))
            conn.commit()
            policies = conn.execute('SELECT campaign_id,policy,revision FROM ad_mandates WHERE shop=%s AND enabled=TRUE', (shop,)).fetchall()
            errors = False
            for cid, policy, revision in policies:
                try:
                    account = meta_account()
                    campaign = current_campaign(cid)
                    today = datetime.now(ZoneInfo(account['timezone_name'])).date().isoformat()
                    total = campaign_spend(cid, policy['start_date'], today)
                    daily = campaign_spend(cid, today, today)
                    if total['currency'] != account['currency'] or daily['currency'] != account['currency']:
                        raise ControlError('عملات التقارير غير متطابقة.')
                    snapshot = dict(account_id=str(campaign['account_id']), currency=account['currency'],
                        status=campaign['status'], total_spend=total['spend'], daily_spend=daily['spend'],
                        start_date=policy['start_date'], end_date=today,
                        checked_at=datetime.now(timezone.utc).isoformat(),
                        platform_attributed_purchases=total['platform_attributed_purchases'])
                    reason = evaluate(policy, snapshot)
                    if reason == 'account_mismatch':
                        raise ControlError('حساب التفويض لا يطابق الربط الحالي.')
                    blocked = conn.execute("SELECT 1 FROM ad_control_events WHERE shop=%s AND campaign_id=%s AND state='needs_review' LIMIT 1", (shop, cid)).fetchone()
                    live = (reason in ('daily_limit', 'total_limit', 'mandate_expired') and
                            policy['mode'] == 'auto_pause' and
                            os.environ.get('ADS_AUTOPAUSE_ENABLED') == 'true' and not blocked)
                    state = 'executing' if live else 'blocked_review' if blocked else 'observed'
                    eid = conn.execute('''INSERT INTO ad_control_events(shop,campaign_id,revision,reason,state,evidence)
                        VALUES (%s,%s,%s,%s,%s,%s::jsonb) RETURNING id''',
                        (shop, cid, revision, reason, state, json.dumps(snapshot))).fetchone()[0]
                    conn.commit()  # Persist intent BEFORE the external mutation.
                    if live:
                        try:
                            pause_campaign(cid)
                            state = 'paused'
                        except Exception:
                            state = 'needs_review'
                            errors = True
                        conn.execute('UPDATE ad_control_events SET state=%s,updated_at=NOW() WHERE id=%s', (state, eid))
                        conn.commit()
                except Exception:
                    conn.rollback()
                    errors = True
                    conn.execute('''INSERT INTO ad_control_events(shop,campaign_id,revision,reason,state,evidence)
                        VALUES (%s,%s,%s,'provider_or_data_unavailable','error','{}'::jsonb)''', (shop, cid, revision))
                    conn.commit()
            conn.execute('''INSERT INTO ad_control_health(shop,state,message) VALUES (%s,%s,%s)
                ON CONFLICT(shop) DO UPDATE SET checked_at=NOW(),state=EXCLUDED.state,message=EXCLUDED.message''',
                (shop, 'attention' if errors else 'ok',
                 'تعذر فحص أو إيقاف بعض الحملات؛ راجعي السجل وMeta.' if errors else 'اكتملت دورة المراقبة.'))
            conn.commit()
            return True
        finally:
            conn.execute('SELECT pg_advisory_unlock(%s)', (LOCK,))
            conn.commit()


def dashboard():
    with _connect() as conn:
        prepare(conn)
        policies = conn.execute('SELECT campaign_id,policy,enabled,revision FROM ad_mandates WHERE shop=%s', (store_key(),)).fetchall()
        events = conn.execute('''SELECT id,campaign_id,reason,state,evidence,created_at FROM ad_control_events
            WHERE shop=%s ORDER BY id DESC LIMIT 100''', (store_key(),)).fetchall()
        health = conn.execute('SELECT checked_at,state,message FROM ad_control_health WHERE shop=%s', (store_key(),)).fetchone()
    return dict(live_pause_enabled=os.environ.get('ADS_AUTOPAUSE_ENABLED') == 'true',
        capabilities={'meta_reports': True, 'meta_rule_pause': True, 'campaign_launch': False,
                      'budget_changes': False, 'tiktok_writes': False, 'external_alert_delivery': False},
        health=dict(checked_at=health[0].isoformat(), state=health[1], message=health[2]) if health else None,
        mandates=[dict(campaign_id=r[0], policy=r[1], enabled=r[2], revision=r[3]) for r in policies],
        events=[dict(id=r[0], campaign_id=r[1], reason=r[2], state=r[3], evidence=r[4], created_at=r[5].isoformat()) for r in events])
