"""Read-only adapters for Meta (Facebook/Instagram) and TikTok ads."""
import json
import os
import re
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
import requests

class AdsError(RuntimeError):
    pass

def report_dates(period='last_7_days', start_date='', end_date='', timezone='Asia/Seoul', today=None):
    """Resolve relative periods on the server, in the reporting account's timezone."""
    if period == 'custom':
        return _dates(start_date, end_date)
    if start_date or end_date:
        raise ValueError('استخدمي custom مع تاريخ البداية والنهاية.')
    current = today or datetime.now(ZoneInfo(timezone)).date()
    if period == 'today':
        first = last = current
    elif period == 'yesterday':
        first = last = current - timedelta(days=1)
    elif period in ('last_7_days', 'last_30_days'):
        last = current - timedelta(days=1)
        first = last - timedelta(days=6 if period == 'last_7_days' else 29)
    elif period == 'previous_month':
        last = current.replace(day=1) - timedelta(days=1)
        first = last.replace(day=1)
    elif period == 'this_month':
        first, last = current.replace(day=1), current
    else:
        raise ValueError('الفترة غير مدعومة؛ حددي تاريخ البداية والنهاية.')
    return _dates(first.isoformat(), last.isoformat())

def _meta_config():
    if not configuration()['meta']['configured']:
        raise AdsError('ربط Facebook وInstagram يحتاج إعداد بيانات Meta.')
    account = os.environ['META_AD_ACCOUNT_ID'].strip().removeprefix('act_')
    version = os.environ['META_API_VERSION'].strip()
    if not account.isdigit() or not re.fullmatch(r'v\d+\.\d+', version):
        raise AdsError('معرّف حساب Meta أو إصدار API غير صحيح.')
    return account, version, {'Authorization': 'Bearer '+os.environ['META_ACCESS_TOKEN'].strip()}

def meta_account():
    account, version, headers = _meta_config()
    data = _json_get(f'https://graph.facebook.com/{version}/act_{account}', headers,
                     {'fields':'account_id,name,currency,timezone_name,account_status,user_tasks'})
    if str(data.get('account_id')) != account:
        raise AdsError('معرّف الحساب المستلم لا يطابق حساب Meta المطلوب.')
    if not all(isinstance(data.get(k), str) and data[k].strip() for k in ('name','currency','timezone_name')):
        raise AdsError('بيانات اسم الحساب أو عملته أو توقيته غير مكتملة.')
    try:
        ZoneInfo(data['timezone_name'])
    except (ValueError, KeyError):
        raise AdsError('توقيت الحساب غير معروف؛ لم يتم افتراض توقيت آخر.') from None
    for field, key in [('name','META_EXPECTED_ACCOUNT_NAME'),('currency','META_EXPECTED_CURRENCY'),('timezone_name','META_EXPECTED_TIMEZONE')]:
        expected = os.environ.get(key, '').strip()
        if expected and data[field] != expected:
            raise AdsError('بيانات حساب Meta لا تطابق إعدادات الحساب المتوقعة؛ راجعي الربط.')
    tasks = data.get('user_tasks')
    return {'id':account, 'name':data['name'], 'currency':data['currency'],
            'timezone':data['timezone_name'], 'account_status':data.get('account_status'),
            'tasks':tasks if isinstance(tasks,list) and all(isinstance(v,str) for v in tasks) else [],
            'token_expiry':'unknown', 'verified':True}

def verify_meta_connection():
    result = configuration()['meta'].copy()
    if not result['configured']:
        return result
    try:
        account = meta_account()
        start, end = report_dates('yesterday', timezone=account['timezone'])
        report = meta_report(start, end, account_info=account)
        return {**result, 'verified':True, 'account':account, 'report_read_verified':report['verified'],
                'checked_at':datetime.now(ZoneInfo('UTC')).isoformat()}
    except AdsError as exc:
        return {**result, 'verified':False, 'error':str(exc)}

def configuration():
    requirements = {
        'meta': ['META_ACCESS_TOKEN', 'META_AD_ACCOUNT_ID', 'META_API_VERSION'],
        'tiktok': ['TIKTOK_ACCESS_TOKEN', 'TIKTOK_ADVERTISER_ID'],
    }
    return {platform: {'configured': all(os.environ.get(k, '').strip() for k in keys),
        'missing': [k for k in keys if not os.environ.get(k, '').strip()],
        'verified': False} for platform, keys in requirements.items()}

def _dates(start, end):
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except (TypeError, ValueError):
        raise ValueError('استخدمي تاريخًا بصيغة YYYY-MM-DD.') from None
    if first > last or (last - first).days > 30:
        raise ValueError('اختاري مدة لا تتجاوز ٣١ يومًا.')
    return first.isoformat(), last.isoformat()

def default_dates():
    last = datetime.now(ZoneInfo('Asia/Seoul')).date() - timedelta(days=1)
    return (last-timedelta(days=6)).isoformat(), last.isoformat()

def _json_get(url, headers, params):
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20, allow_redirects=False)
        try:
            data = response.json()
        except ValueError:
            raise AdsError('وصل رد غير صالح من منصة الإعلانات؛ لم تُقرأ النتائج.') from None
        error = data.get('error') if isinstance(data,dict) else None
        code = error.get('code') if isinstance(error,dict) else None
        if code == 190 or response.status_code == 401:
            raise AdsError('مفتاح الوصول غير صالح أو انتهت صلاحيته؛ أعيدي ربط المنصة.')
        if code in (10,200,294) or response.status_code == 403:
            raise AdsError('صلاحيات قراءة الحساب غير كافية؛ راجعي صلاحية الوصول للحساب.')
        if code in (4,17,32,613) or response.status_code == 429:
            raise AdsError('تم بلوغ حد طلبات المنصة؛ حاولي لاحقًا.')
        if response.status_code != 200 or error:
            raise AdsError('تعذّر قراءة منصة الإعلانات؛ تحققي من الربط وإصدار API.')
        if not isinstance(data, dict):
            raise AdsError('وصل رد غير مكتمل من منصة الإعلانات.')
        return data
    except requests.RequestException:
        raise AdsError('تعذّر الاتصال بمنصة الإعلانات.') from None

def _number(value):
    if value is None or value == '':
        return None
    try:
        n = Decimal(str(value))
        return float(n) if n.is_finite() else None
    except InvalidOperation:
        return None

def meta_report(start, end, account_info=None):
    start, end = _dates(start, end)
    account, version, headers = _meta_config()
    account_info = account_info or meta_account()
    url = f'https://graph.facebook.com/{version}/act_{account}/insights'
    params = {'fields': 'campaign_id,campaign_name,impressions,clicks,spend,ctr,cpc,actions,action_values,account_currency,date_start,date_stop',
        'time_range':json.dumps({'since':start,'until':end}), 'level':'campaign',
        'breakdowns':'publisher_platform','limit':100}
    rows, seen = [], set()
    deadline=time.monotonic()+60
    for _ in range(100):
        if time.monotonic()>deadline:
            raise AdsError("تقرير Meta طويل؛ اختاري مدة أقصر.")
        data = _json_get(url, headers, params)
        if data.get('error') or not isinstance(data.get('data'), list):
            raise AdsError('تعذّر قراءة تقرير Meta كاملًا.')
        for item in data['data']:
            if not isinstance(item,dict) or not item.get('campaign_id') or not item.get('publisher_platform'):
                raise AdsError('صفوف تقرير Meta غير مكتملة؛ لم يُرجع تقرير جزئي.')
            if item.get('account_currency') != account_info['currency']:
                raise AdsError('عملة التقرير لا تطابق عملة الحساب؛ لم تُجمع النتائج.')
            for field in ('actions','action_values'):
                if not isinstance(item.get(field,[]),list) or not all(isinstance(v,dict) for v in item.get(field,[])):
                    raise AdsError('بيانات تحويلات Meta غير مكتملة.')
            rows.append({'campaign_id':item.get('campaign_id'),'campaign_name':item.get('campaign_name'),
                'placement':item.get('publisher_platform'), 'currency':item.get('account_currency'),
                **{k:_number(item.get(k)) for k in ('impressions','clicks','spend','ctr','cpc')},
                'actions':item.get('actions',[]), 'action_values':item.get('action_values',[])})
        paging = data.get('paging', {})
        if not isinstance(paging,dict):
            raise AdsError('بيانات صفحات Meta غير مكتملة.')
        if not paging.get('next'):
            return {'platform':'meta','verified':True,'start_date':start,'end_date':end,'rows':rows,
                'account':account_info, 'partial_day':end >= datetime.now(ZoneInfo(account_info['timezone'])).date().isoformat(),
                'coverage':'Facebook, Instagram and other returned Meta placements; dates use ad account timezone',
                'attribution':'Platform-attributed actions; not Shopify-confirmed purchases'}
        cursors = paging.get('cursors')
        cursor = cursors.get('after') if isinstance(cursors,dict) else None
        if not isinstance(cursor,str) or not cursor or cursor in seen:
            raise AdsError('توقفت صفحات تقرير Meta؛ لم يتم إرجاع تقرير جزئي.')
        # Ignore provider next URLs; keep token restricted to the fixed Meta host.
        seen.add(cursor); params['after'] = cursor
    raise AdsError('تقرير Meta كبير؛ اختاري مدة أقصر.')

def tiktok_report(start, end):
    start, end = _dates(start, end)
    if not configuration()['tiktok']['configured']:
        raise AdsError('ربط TikTok يحتاج إعداد بيانات حساب الإعلانات.')
    account = os.environ['TIKTOK_ADVERTISER_ID'].strip()
    if not account.isdigit():
        raise AdsError('معرّف حساب TikTok غير صحيح.')
    params = {'advertiser_id':account,'report_type':'BASIC','service_type':'AUCTION',
        'data_level':'AUCTION_CAMPAIGN','dimensions':json.dumps(['campaign_id']),
        'metrics':json.dumps(['campaign_name','spend','impressions','clicks','ctr','cpc','conversion']),
        'start_date':start,'end_date':end,'page':1,'page_size':100}
    rows = []
    deadline=time.monotonic()+60
    for page in range(1,101):
        if time.monotonic()>deadline:
            raise AdsError("تقرير TikTok طويل؛ اختاري مدة أقصر.")
        params['page'] = page
        data = _json_get('https://business-api.tiktok.com/open_api/v1.3/report/integrated/get/',
            {'Access-Token':os.environ['TIKTOK_ACCESS_TOKEN']},params)
        body = data.get('data') or {}
        if not isinstance(body,dict):
            raise AdsError('بيانات تقرير TikTok غير مكتملة.')
        if data.get('code') != 0 or not isinstance(body.get('list'),list):
            raise AdsError('تعذّر قراءة تقرير TikTok كاملًا.')
        for item in body['list']:
            if not isinstance(item,dict) or not isinstance(item.get('metrics'),dict) or not isinstance(item.get('dimensions'),dict):
                raise AdsError('صفوف تقرير TikTok غير مكتملة.')
            metrics = item.get('metrics',{})
            rows.append({'campaign_id':item.get('dimensions',{}).get('campaign_id'),
                'campaign_name':metrics.get('campaign_name'),'placement':'tiktok',
                'currency':None,
                **{k:_number(metrics.get(k)) for k in ('spend','impressions','clicks','ctr','cpc','conversion')}})
        page_info = body.get('page_info')
        total = page_info.get('total_page') if isinstance(page_info,dict) else None
        if type(total) is not int or total < 0:
            raise AdsError('بيانات صفحات TikTok غير مكتملة.')
        if page >= total:
            return {'platform':'tiktok','verified':True,'start_date':start,'end_date':end,'rows':rows,
                'coverage':'Auction campaign report; dates use advertiser timezone; currency requires account confirmation',
                'attribution':'conversion is the campaign conversion event, not necessarily a purchase'}
    raise AdsError('تقرير TikTok كبير؛ اختاري مدة أقصر.')

def get_ads_context(start=None, end=None):
    if (start is None) != (end is None):
        raise ValueError('حددي تاريخ البداية والنهاية معًا.')
    if start is None or end is None:
        start,end = default_dates()
    result = {}
    for platform, reader in [('meta',meta_report),('tiktok',tiktok_report)]:
        if not configuration()[platform]['configured']:
            result[platform] = {'configured':False,'missing':configuration()[platform]['missing']}
        else:
            try:
                result[platform] = reader(start,end)
            except AdsError as exc:
                result[platform] = {'verified':False,'error':str(exc)}
    return result

def read_ad_report(platform, period, start_date='', end_date=''):
    """Read-only model tool; dates and account identity are resolved before reporting."""
    if platform not in ('meta','tiktok','all'):
        raise ValueError('اختاري meta أو tiktok أو all.')
    results = {}
    for name in (('meta','tiktok') if platform == 'all' else (platform,)):
        config = configuration()[name]
        if not config['configured']:
            results[name] = {**config, 'error':'بيانات الربط غير مكتملة.'}
            continue
        try:
            if name == 'meta':
                account = meta_account()
                first,last = report_dates(period,start_date,end_date,account['timezone'])
                results[name] = meta_report(first,last,account_info=account)
            else:
                first,last = report_dates(period,start_date,end_date)
                results[name] = tiktok_report(first,last)
                results[name]['date_selection_timezone'] = 'Asia/Seoul'
                results[name]['timezone_warning'] = 'Relative dates selected in Seoul; confirm advertiser timezone.'
        except (AdsError,ValueError) as exc:
            results[name] = {'verified':False,'error':str(exc)}
    return results

AD_REPORT_TOOL = {
    'type':'function','name':'read_ad_report',
    'description':'Read actual advertising spend, clicks, impressions and attributed actions. Use whenever the owner asks about ad performance, spend (including كم صرفنا مبارح), or campaign analysis. Relative periods are resolved by the server. Previous month means the prior calendar month; last_30_days means 30 completed dates. Never execute ads.',
    'parameters':{'type':'object','properties':{
        'platform':{'type':'string','enum':['meta','tiktok','all']},
        'period':{'type':'string','enum':['today','yesterday','last_7_days','last_30_days','previous_month','this_month','custom']},
        'start_date':{'type':'string','description':'YYYY-MM-DD only for custom; otherwise empty string.'},
        'end_date':{'type':'string','description':'YYYY-MM-DD only for custom; otherwise empty string.'}},
        'required':['platform','period','start_date','end_date'],'additionalProperties':False},'strict':True}

