"""Evidence-based decision support, never an automatic media buyer."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from advertising_store import number

VERSION='marketing-analysis-v1'
COSTS=('product_cost_per_order','shipping_cost_per_order','payment_fee_percent',
       'fixed_fee_per_order','refund_rate_percent','tax_percent_of_revenue')
DEFAULT_RULES={'minimum_impressions':'1000','minimum_clicks':'50','minimum_purchases':'5',
               'minimum_ctr_percent':'0.5','scale_margin_percent':'20','maximum_budget_increase_percent':'15',
               'maximum_snapshot_age_hours':'24','attribution_delay_days':'2'}


def validate_policy(policy):
    if not isinstance(policy,dict):raise ValueError('Policy must be an object')
    if set(policy)-{'currency','purchase_event','purchase_value_basis','costs','rules','monitoring_enabled','daily_spend_limit','funnel_events','require_shopify_confirmation'}:
        raise ValueError('Unknown policy fields')
    import re
    if not re.fullmatch('[A-Z]{3}',policy.get('currency','')):raise ValueError('Currency required')
    event=policy.get('purchase_event')
    if event is not None and (not isinstance(event,str) or not event or len(event)>150):raise ValueError('Exact purchase event required')
    if policy.get('purchase_value_basis') not in (None,'revenue_before_refunds_and_taxes'):
        raise ValueError('Confirm the purchase revenue basis')
    costs=policy.get('costs',{})
    if not isinstance(costs,dict) or set(costs)-set(COSTS):raise ValueError('Unknown cost fields')
    clean={k:None if costs.get(k) in (None,'') else str(number(costs[k])) for k in COSTS}
    for k in ('payment_fee_percent','refund_rate_percent','tax_percent_of_revenue'):
        if clean[k] is not None and number(clean[k])>100:raise ValueError('Percentage exceeds 100')
    if not isinstance(policy.get('rules',{}),dict):raise ValueError('Rules must be an object')
    rules={**DEFAULT_RULES,**policy.get('rules',{})}
    if set(rules)!=set(DEFAULT_RULES):raise ValueError('Unknown decision rule')
    rules={k:str(number(v)) if v not in (None,'') else None for k,v in rules.items()}
    if any(v is None or number(v)<=0 for k,v in rules.items() if k!='attribution_delay_days'):
        raise ValueError('Rules must be positive')
    if rules['attribution_delay_days'] is None or number(rules['attribution_delay_days'])>30:
        raise ValueError('Attribution delay must be 0–30 completed days')
    if number(rules['attribution_delay_days'])%1:raise ValueError('Attribution delay must be a whole number')
    if number(rules['maximum_snapshot_age_hours'])>168:raise ValueError('Snapshot age must not exceed seven days')
    if number(rules['maximum_budget_increase_percent'])>25:raise ValueError('Budget proposal exceeds 25% guardrail')
    events=policy.get('funnel_events',{})
    if not isinstance(events,dict) or set(events)-{'landing_page_view','add_to_cart','initiate_checkout'}:
        raise ValueError('Invalid funnel events')
    if any(v is not None and (not isinstance(v,str) or not v or len(v)>150) for v in events.values()):
        raise ValueError('Funnel events must be exact event names or null')
    require_shopify=policy.get('require_shopify_confirmation',True)
    if type(require_shopify) is not bool:raise ValueError('Shopify confirmation flag must be boolean')
    enabled=policy.get('monitoring_enabled',False)
    if type(enabled) is not bool:raise ValueError('Monitoring flag must be boolean')
    limit=number(policy.get('daily_spend_limit'))
    return {'currency':policy['currency'],'purchase_event':event,'purchase_value_basis':policy.get('purchase_value_basis'),
            'costs':clean,'rules':rules,'funnel_events':events,'require_shopify_confirmation':require_shopify,'monitoring_enabled':enabled,'daily_spend_limit':str(limit) if limit is not None else None}


def _sum(values):
    return None if not values or any(v is None for v in values) else sum(values,Decimal(0))


def _event(items,event):
    if not event:return None
    hits=[i for i in items if i.get('action_type')==event]
    # Absent event is unknown, not invented zero; ambiguous duplicates fail closed.
    return number(hits[0].get('value')) if len(hits)==1 else None


def _ratio(a,b,multiplier=1):
    return a*multiplier/b if a is not None and b is not None and b>0 else None


def _serialize(data):
    if isinstance(data,Decimal):return str(data)
    if isinstance(data,dict):return {k:_serialize(v) for k,v in data.items()}
    if isinstance(data,list):return [_serialize(v) for v in data]
    return data


def analyze_report(report, policy, previous=None, now=None):
    policy=validate_policy(policy)
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('Timezone-aware clock required')
    warnings=[]
    account=report.get('account') or {}
    if account.get('currency')!=policy['currency']:warnings.append('currency_mismatch')
    if not report.get('complete'):warnings.append('missing_dates')
    days=report.get('days',[])
    if not days:warnings.append('no_saved_days')
    max_age=timedelta(hours=float(policy['rules']['maximum_snapshot_age_hours']))
    for day in days:
        try:
            stamp=datetime.fromisoformat(day['saved_at'])
            if stamp.tzinfo is None or now-stamp>max_age or stamp>now+timedelta(minutes=5):
                warnings.append('stale_or_invalid_snapshot');break
        except (TypeError,ValueError,KeyError):warnings.append('stale_or_invalid_snapshot');break
    # Today/last completed dates can under-report delayed conversions.
    from zoneinfo import ZoneInfo
    try:
        last=datetime.fromisoformat(report['end_date']).date()
        local_today=now.astimezone(ZoneInfo(account['timezone'])).date()
        if (local_today-last).days<=int(number(policy['rules']['attribution_delay_days'])):
            warnings.append('attribution_window_not_mature')
    except (ValueError,KeyError,TypeError):warnings.append('unknown_account_timezone_or_dates')
    grouped=defaultdict(list)
    for row in report.get('rows',[]):grouped[(row['entity_id'],row['placement'])].append(row)
    entities=[]
    costs=policy['costs'];cost_ready=all(costs[k] is not None for k in COSTS)
    value_ready=policy.get('purchase_value_basis')=='revenue_before_refunds_and_taxes'
    for (eid,placement),rows in sorted(grouped.items()):
        m={k:_sum([number(r['metrics'].get(k)) for r in rows]) for k in ('spend','impressions','clicks')}
        # TikTok BASIC generic conversion does not identify a purchase event/value.
        supported=report['platform']=='meta' or (report['platform']=='tiktok' and policy['purchase_event']=='tiktok_website_complete_payment')
        purchases=_sum([_event(r.get('actions',[]),policy['purchase_event']) for r in rows]) if supported else None
        revenue=_sum([_event(r.get('action_values',[]),policy['purchase_event']) for r in rows]) if supported else None
        m.update(purchases=purchases,purchase_value=revenue,ctr_percent=_ratio(m['clicks'],m['impressions'],100),
                 cpc=_ratio(m['spend'],m['clicks']),cpm=_ratio(m['spend'],m['impressions'],1000),
                 purchase_cpa=_ratio(m['spend'],purchases),roas=_ratio(revenue,m['spend']),
                 purchase_conversion_rate_percent=_ratio(purchases,m['clicks'],100))
        contribution=profit=break_even_cpa=None
        if cost_ready and value_ready and revenue is not None and purchases is not None:
            net=revenue*(1-number(costs['refund_rate_percent'])/100-number(costs['tax_percent_of_revenue'])/100-number(costs['payment_fee_percent'])/100)
            contribution=net-purchases*(number(costs['product_cost_per_order'])+number(costs['shipping_cost_per_order'])+number(costs['fixed_fee_per_order']))
            profit=contribution-m['spend'] if m['spend'] is not None else None
            break_even_cpa=_ratio(contribution,purchases)
        m.update(estimated_contribution_before_ads=contribution,estimated_contribution_after_ads=profit,break_even_cpa=break_even_cpa)
        findings=[]
        def finding(code,priority,decision,reason):
            findings.append({'code':code,'priority':priority,'decision':decision,'reason':reason,
                             'requires_owner_approval':decision in ('propose_pause','propose_budget_increase'),
                             'executed':False})
        if warnings:
            finding('data_quality','high','wait_for_data','قرارات الأداء مؤجلة حتى اكتمال البيانات وحداثتها ونضج التحويلات.')
        else:
            if m['impressions'] is not None and m['impressions']>=number(policy['rules']['minimum_impressions']) and m['ctr_percent'] is not None and m['ctr_percent']<number(policy['rules']['minimum_ctr_percent']):
                finding('weak_ctr','medium','review_creative','معدل النقر أقل من الحد المختار؛ اختبري افتتاحية أو صورة أخرى. هذا لا يثبت سبب الضعف.')
            if purchases is None or revenue is None or not cost_ready or not value_ready:
                finding('missing_profit_inputs','high','request_data','يلزم حدث شراء محدد وقيمته وتكاليف الطلب وأساس الإيراد لتقييم الربحية.')
            elif m['clicks'] is None or m['clicks']<number(policy['rules']['minimum_clicks']) or purchases<number(policy['rules']['minimum_purchases']):
                finding('small_sample','medium','continue_observation','العينة أقل من الحدود المختارة؛ لا يوجد دليل كافٍ لزيادة الميزانية أو إيقاف الأداء.')
            elif profit is not None and profit<0:
                finding('negative_contribution','high','propose_pause','المساهمة التقديرية بعد الإعلان سالبة ضمن البيانات والتكاليف المحددة؛ راجعي التأخر والإسناد قبل الموافقة.')
            elif profit is not None and contribution is not None and m['spend'] is not None and m['spend']>0 and profit>0 and _ratio(profit,contribution,100)>=number(policy['rules']['scale_margin_percent']):
                finding('positive_contribution','medium','propose_budget_increase','مساهمة تقديرية موجبة وعينة كافية وفق السياسة؛ الزيادة مقترح محدود وتحتاج مراجعة سقف الإنفاق والتتبّع.')
                findings[-1]['maximum_increase_percent']=policy['rules']['maximum_budget_increase_percent']
            else:finding('near_break_even','medium','hold_budget','الأداء قريب من التعادل أو هامشه غير كافٍ للتوسّع وفق السياسة.')
        entities.append({'entity_id':eid,'entity_name':rows[-1].get('entity_name'),'placement':placement,
                         'metrics':m,'findings':findings})
    # Account spend is counted once across placements at this selected level only.
    spend=_sum([e['metrics']['spend'] for e in entities])
    daily=defaultdict(list)
    for r in report.get('rows',[]):daily[r['date']].append(number(r['metrics'].get('spend')))
    spend_alerts=[]
    if not warnings and policy['daily_spend_limit'] is not None:
        for day,values in sorted(daily.items()):
            total=_sum(values)
            if total is not None and total>number(policy['daily_spend_limit']):
                spend_alerts.append({'code':'daily_spend_limit','date':day,'spend':str(total),'limit':policy['daily_spend_limit'],
                    'decision':'review_spend','executed':False})
    comparison=None
    if previous:
        # Only consecutive, equally sized periods with matching account/grain can be compared.
        from datetime import date
        same=all(previous.get(k)==report.get(k) for k in ('platform','account_id','level','attribution'))
        same=same and (previous.get('account') or {}).get('currency')==account.get('currency') and (previous.get('account') or {}).get('timezone')==account.get('timezone')
        a,b,c,d=[date.fromisoformat(x) for x in (report['start_date'],report['end_date'],previous['start_date'],previous['end_date'])]
        if same and b-a==d-c and d+timedelta(days=1)==a:
            past=analyze_report(previous,policy,now=now)
            if not warnings and not past['data_warnings']:
                before=number(past['available_spend'])
                previous_entities={(e['entity_id'],e['placement']):e for e in past['entities']}
                changes=[]
                for entity in entities:
                    old=previous_entities.get((entity['entity_id'],entity['placement']))
                    if not old:continue
                    delta={}
                    for metric in ('spend','ctr_percent','purchase_cpa','roas','estimated_contribution_after_ads'):
                        current=entity['metrics'][metric]; prior=old['metrics'][metric]
                        current=Decimal(str(current)) if current is not None else None
                        prior=Decimal(str(prior)) if prior is not None else None
                        delta[metric]={'current':current,'previous':prior,
                            'change':current-prior if current is not None and prior is not None else None}
                    changes.append({'entity_id':entity['entity_id'],'placement':entity['placement'],'metrics':delta})
                comparison={'previous_start':previous['start_date'],'previous_end':previous['end_date'],
                            'spend_change_percent':_ratio(spend-before,before,100) if spend is not None and before is not None else None,
                            'entities':changes,
                            'causality':'Observed comparison, not proof of an experiment or causation'}
        if comparison is None:warnings.append('comparison_unavailable')
    return _serialize({'version':VERSION,'platform':report['platform'],'account_id':report['account_id'],'level':report['level'],
        'start_date':report['start_date'],'end_date':report['end_date'],'currency':account.get('currency'),
        'data_warnings':sorted(set(warnings)),'policy':policy,'available_spend':spend,'entities':entities,
        'spend_alerts':spend_alerts,'comparison':comparison,'generated_at':now.isoformat(),
        'limitations':['Decision support only; no action executed. Thresholds are heuristics, not statistical significance.',
            'Platform-attributed contribution estimate, not reconciled Shopify profit. Costs are owner-supplied averages.',
            'Audience demographics, targeting, creative content, budgets and tracking health are not inferred from performance.',
            'TikTok profit requires explicit tiktok_website_complete_payment and its value; generic conversion is never purchase.']})
