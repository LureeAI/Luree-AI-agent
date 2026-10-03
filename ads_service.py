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
        if response.status_code != 200:
            raise AdsError('تعذّر قراءة منصة الإعلانات؛ تحققي من صلاحية الربط.')
        data = response.json()
        if not isinstance(data, dict):
            raise AdsError('وصل رد غير مكتمل من منصة الإعلانات.')
        return data
    except (requests.RequestException, ValueError):
        raise AdsError('تعذّر الاتصال بمنصة الإعلانات.') from None

def _number(value):
    if value is None or value == '':
        return None
    try:
        n = Decimal(str(value))
        return float(n) if n.is_finite() else None
    except InvalidOperation:
        return None

def meta_report(start, end):
    start, end = _dates(start, end)
    if not configuration()['meta']['configured']:
        raise AdsError('ربط Facebook وInstagram يحتاج إعداد بيانات Meta.')
    account = os.environ['META_AD_ACCOUNT_ID'].removeprefix('act_').strip()
    version = os.environ['META_API_VERSION'].strip()
    if not account.isdigit() or not re.fullmatch(r'v\d+\.\d+', version):
        raise AdsError('معرّف حساب Meta أو إصدار API غير صحيح.')
    token = os.environ['META_ACCESS_TOKEN']
    url = f'https://graph.facebook.com/{version}/act_{account}/insights'
    params = {'fields': 'campaign_id,campaign_name,impressions,clicks,spend,ctr,cpc,actions,action_values,account_currency,date_start,date_stop',
        'time_range':json.dumps({'since':start,'until':end}), 'level':'campaign',
        'breakdowns':'publisher_platform','limit':100}
    rows, seen = [], set()
    deadline=time.monotonic()+60
    for _ in range(100):
        if time.monotonic()>deadline:
            raise AdsError("تقرير Meta طويل؛ اختاري مدة أقصر.")
        data = _json_get(url, {'Authorization':'Bearer '+token}, params)
        if data.get('error') or not isinstance(data.get('data'), list):
            raise AdsError('تعذّر قراءة تقرير Meta كاملًا.')
        for item in data['data']:
            rows.append({'campaign_id':item.get('campaign_id'),'campaign_name':item.get('campaign_name'),
                'placement':item.get('publisher_platform'), 'currency':item.get('account_currency'),
                **{k:_number(item.get(k)) for k in ('impressions','clicks','spend','ctr','cpc')},
                'actions':item.get('actions',[]), 'action_values':item.get('action_values',[])})
        paging = data.get('paging', {})
        if not paging.get('next'):
            return {'platform':'meta','verified':True,'start_date':start,'end_date':end,'rows':rows,
                'coverage':'Facebook, Instagram and other returned Meta placements; dates use ad account timezone',
                'attribution':'Platform-attributed actions; not Shopify-confirmed purchases'}
        cursor = paging.get('cursors',{}).get('after')
        if not cursor or cursor in seen:
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
        if data.get('code') != 0 or not isinstance(body.get('list'),list):
            raise AdsError('تعذّر قراءة تقرير TikTok كاملًا.')
        for item in body['list']:
            metrics = item.get('metrics',{})
            rows.append({'campaign_id':item.get('dimensions',{}).get('campaign_id'),
                'campaign_name':metrics.get('campaign_name'),'placement':'tiktok',
                'currency':None,
                **{k:_number(metrics.get(k)) for k in ('spend','impressions','clicks','ctr','cpc','conversion')}})
        total = (body.get('page_info') or {}).get('total_page')
        if type(total) is not int or total < 0:
            raise AdsError('بيانات صفحات TikTok غير مكتملة.')
        if page >= total:
            return {'platform':'tiktok','verified':True,'start_date':start,'end_date':end,'rows':rows,
                'coverage':'Auction campaign report; dates use advertiser timezone; currency requires account confirmation',
                'attribution':'conversion is the campaign conversion event, not necessarily a purchase'}
    raise AdsError('تقرير TikTok كبير؛ اختاري مدة أقصر.')

def get_ads_context(start=None, end=None):
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

