"""Funnel and video-performance diagnostics, with explicit evidence limitations."""
from collections import defaultdict
from decimal import Decimal
from advertising_store import number
from marketing_analysis import _event, _sum, _ratio, _serialize


def diagnose(report,policy):
    grouped=defaultdict(list)
    for row in report['rows']:grouped[(row['entity_id'],row['placement'])].append(row)
    mapping=policy.get('funnel_events',{})
    if report['platform']=='tiktok':
        mapping={**{'landing_page_view':'tiktok_website_landing_page_view','add_to_cart':'tiktok_website_add_to_cart','initiate_checkout':None},**mapping}
    stages=['landing_page_view','add_to_cart','initiate_checkout','purchase']
    findings=[];entities=[]
    for (eid,placement),rows in sorted(grouped.items()):
        counts={stage:_sum([_event(r.get('actions',[]),policy['purchase_event'] if stage=='purchase' else mapping.get(stage)) for r in rows]) for stage in stages}
        clicks=_sum([number(r['metrics'].get('link_clicks') if r['metrics'].get('link_clicks') is not None else r['metrics'].get('clicks')) for r in rows])
        stages_counts={'click':clicks,**counts};ratios=[]
        pairs=[('click','landing_page_view'),('landing_page_view','add_to_cart'),('add_to_cart','initiate_checkout'),('initiate_checkout','purchase')]
        warnings=[]
        for before,after in pairs:
            rate=_ratio(stages_counts[after],stages_counts[before],100)
            ratios.append({'from':before,'to':after,'event_ratio_percent':rate})
            if rate is not None and rate>100:warnings.append('non_cohort_counts_or_repeated_events')
        metrics={key:_sum([number(r['metrics'].get(key)) for r in rows]) for key in ('video_plays','video_2s','video_6s','video_p25','video_p50','video_p75','video_p100')}
        metrics['two_second_view_rate_percent']=_ratio(metrics['video_2s'],metrics['video_plays'],100)
        metrics['six_second_view_rate_percent']=_ratio(metrics['video_6s'],metrics['video_plays'],100)
        metrics['completion_rate_percent']=_ratio(metrics['video_p100'],metrics['video_plays'],100)
        incomplete=[s for s,v in counts.items() if v is None]
        if incomplete:findings.append({'entity_id':eid,'placement':placement,'code':'funnel_data_missing','stages':incomplete,
             'next_step':'راجعي أسماء الأحداث وصلاحية تقريرها والتتبّع قبل تفسير الفجوات كمشكلة في المتجر.'})
        if metrics['video_plays'] is not None and metrics['video_plays']>=1000 and metrics['two_second_view_rate_percent'] is not None and metrics['two_second_view_rate_percent']<30:
            findings.append({'entity_id':eid,'placement':placement,'code':'test_video_opening',
                'evidence':{'video_plays':metrics['video_plays'],'two_second_view_rate_percent':metrics['two_second_view_rate_percent']},
                'next_step':'اختبري افتتاحية مختلفة مع تثبيت الجمهور والعرض قدر الإمكان؛ هذا تشخيص إرشادي لا تجربة سببية.'})
        entities.append({'entity_id':eid,'entity_name':rows[-1].get('entity_name'),'placement':placement,
                         'event_counts':stages_counts,'ratios':ratios,'video':metrics,'warnings':warnings})
    return _serialize({'entities':entities,'findings':findings,
       'interpretation':'Ratios compare attributed event counts, not unique people or a linked user-session funnel.',
       'unknowns':['Missing stage means unavailable, not zero. Ratios above 100% are flagged, never clamped.',
                   'Repeat views, separate attribution definitions and cross-device conversions can prevent a monotonic funnel.',
                   'Audience groups can be compared by adgroup performance; demographics/targeting are not inferred.',
                   'Video metrics do not identify garment quality, creative content or incremental lift.'],
       'test_plan':{'method':'Change one variable at a time; define hypothesis, success metric, spend cap and duration before launch.',
                    'limitations':'No A/B significance claim is made from event totals; no test is launched automatically.'}})
