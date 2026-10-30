from flask import Blueprint, current_app, jsonify, request
from agent_service import run_agent
from database import load_messages, get_preferences, set_preferences

agent_routes = Blueprint('agent_routes', __name__)

@agent_routes.get('/ai/health')
def ai_health():
    return jsonify(success=True, agent='Luree AI Agent', status='running')

@agent_routes.post('/ai/chat')
def ai_chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('message'), str):
        return jsonify(success=False, error='اكتبي رسالة نصية.'), 400
    message = data['message'].strip()
    if not message or len(message) > 4000:
        return jsonify(success=False, error='الرسالة يجب أن تكون بين 1 و4000 حرف.'), 400
    result = run_agent(message)
    return jsonify(result), 200 if result.get('success') else 503

@agent_routes.get('/ai/history')
def history():
    try:
        return jsonify(success=True, messages=load_messages(100))
    except Exception:
        current_app.logger.exception('History load failed')
        return jsonify(success=False, error='تعذّر تحميل الذاكرة.'), 503

@agent_routes.route('/ai/memory', methods=['GET', 'PUT'])
def memory():
    try:
        if request.method == 'PUT':
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or not isinstance(data.get('instructions'), str) or len(data['instructions']) > 4000:
                return jsonify(success=False, error='التعليمات يجب ألا تتجاوز 4000 حرف.'), 400
            set_preferences(data['instructions'].strip())
        return jsonify(success=True, instructions=get_preferences())
    except Exception:
        current_app.logger.exception('Memory update failed')
        return jsonify(success=False, error='تعذّر الوصول للذاكرة.'), 503

@agent_routes.get('/ai/inventory/alerts')
def inventory_alerts():
    from inventory_monitor import read_alerts
    try:
        return jsonify(success=True, **read_alerts())
    except Exception:
        return jsonify(success=False, error='تعذّر تحميل تنبيهات المخزون.'), 503

@agent_routes.post('/ai/inventory/alerts/<int:alert_id>/acknowledge')
def acknowledge_inventory_alert(alert_id):
    from inventory_monitor import acknowledge_alert
    try:
        if not acknowledge_alert(alert_id):
            return jsonify(success=False, error='التنبيه غير موجود.'), 404
        return jsonify(success=True)
    except Exception:
        return jsonify(success=False, error='تعذّر حفظ حالة التنبيه.'), 503

@agent_routes.get('/ai/marketing/status')
def marketing_status():
    from ads_service import configuration
    return jsonify(success=True, platforms=configuration())

@agent_routes.get('/ai/marketing/report')
def marketing_report():
    from ads_service import get_ads_context, default_dates, _dates
    start, end = default_dates()
    start, end = request.args.get('start', start), request.args.get('end', end)
    try:
        _dates(start, end)
        return jsonify(success=True, reports=get_ads_context(start, end))
    except ValueError as exc:
        return jsonify(success=False, error=str(exc)), 400

@agent_routes.get('/ai/marketing/verify')
def marketing_verify():
    from ads_service import verify_meta_connection
    return jsonify(success=True, meta=verify_meta_connection())

@agent_routes.get('/ai/actions')
def actions():
    from action_service import list_actions
    try:
        return jsonify(success=True, actions=list_actions())
    except Exception:
        return jsonify(success=False, error='تعذّر تحميل الإجراءات.'), 503

@agent_routes.post('/ai/actions/<int:action_id>/<decision>')
def decide(action_id, decision):
    from action_service import decide_action, ActionError
    try:
        return jsonify(success=True, state=decide_action(action_id, decision))
    except ActionError as exc:
        return jsonify(success=False, error=str(exc)), 409
    except Exception:
        return jsonify(success=False, error='تعذّر حفظ القرار؛ راجعي حالة الإجراء قبل المحاولة.'), 503

@agent_routes.post('/ai/actions/<int:action_id>/reconcile')
def reconcile_action(action_id):
    from action_service import reconcile_meta_pause, ActionError
    try:
        return jsonify(success=True,state=reconcile_meta_pause(action_id))
    except ActionError as exc:
        return jsonify(success=False,error=str(exc)),409
    except Exception:
        return jsonify(success=False,error='تعذّر التحقق من حالة الحملة؛ لم يتم إرسال إيقاف جديد.'),503

@agent_routes.get('/ai/videos/product')
def video_product():
    from video_service import product_video_details, VideoError
    try:
        return jsonify(success=True, product=product_video_details(request.args.get('id','')))
    except VideoError as exc:
        return jsonify(success=False,error=str(exc)),400
    except Exception:
        return jsonify(success=False,error='تعذّر قراءة صور الفستان.'),503

@agent_routes.route('/ai/videos',methods=['GET','POST'])
def video_jobs():
    from video_service import create_video_job, list_videos, VideoError
    try:
        if request.method=='POST':
            data=request.get_json(silent=True)
            if not isinstance(data,dict):
                return jsonify(success=False,error='بيانات الفيديو غير صحيحة.'),400
            aid=create_video_job(data.get('product_id'),data.get('image_ids'),data.get('include_price',True),data.get('include_voice',False),data.get('narration',''),data.get('language','en'),data.get('languages'),data.get('narrations'))
            return jsonify(success=True,video_id=aid,state='queued'),202
        return jsonify(success=True,videos=list_videos())
    except VideoError as exc:
        return jsonify(success=False,error=str(exc)),400
    except Exception:
        return jsonify(success=False,error='تعذّر الوصول إلى خدمة الفيديو.'),503

@agent_routes.get('/ai/videos/<int:video_id>/file')
def video_file(video_id):
    import io
    from flask import send_file
    from video_service import get_video
    try:
        video=get_video(video_id)
        if video is None:
            return jsonify(success=False,error='الفيديو غير جاهز أو غير موجود.'),404
        return send_file(io.BytesIO(video),mimetype='video/mp4',as_attachment=True,
            download_name=f'luree-dress-{video_id}-15s.mp4',conditional=True)
    except Exception:
        return jsonify(success=False,error='تعذّر تنزيل الفيديو.'),503

@agent_routes.delete('/ai/videos/<int:video_id>')
def remove_video(video_id):
    from video_service import delete_video
    try:
        if not delete_video(video_id):
            return jsonify(success=False,error='الفيديو قيد التجهيز أو غير موجود.'),409
        return jsonify(success=True)
    except Exception:
        return jsonify(success=False,error='تعذّر حذف الفيديو.'),503

@agent_routes.get('/ai/product-preparations/product')
def preparation_product():
    from product_workflow import details, PreparationError
    try:
        return jsonify(success=True, product=details(request.args.get('id','')))
    except PreparationError as exc:
        return jsonify(success=False,error=str(exc)),400
    except Exception:
        return jsonify(success=False,error='تعذّر قراءة تفاصيل المنتج.'),503

@agent_routes.get('/ai/product-preparations/publications')
def preparation_publications():
    from product_workflow import publications
    try:
        return jsonify(success=True, publications=publications())
    except Exception:
        return jsonify(success=False,error='قنوات النشر غير متاحة؛ يلزم read_publications وwrite_publications للنشر. يمكنك تجهيز التعديلات دون نشر.'),503

@agent_routes.post('/ai/product-preparations/copy')
def preparation_copy():
    from product_workflow import details, generate_copy, PreparationError
    try:
        data=request.get_json(silent=True)
        if not isinstance(data,dict):
            raise PreparationError('بيانات غير صحيحة.')
        return jsonify(success=True, copy=generate_copy(details(data.get('product_id')),data.get('notes','')))
    except PreparationError as exc:
        return jsonify(success=False,error=str(exc)),400
    except Exception:
        return jsonify(success=False,error='تعذّر تجهيز النصوص؛ لم يتغير المنتج.'),503

@agent_routes.post('/ai/product-preparations/price')
def preparation_price():
    from product_workflow import price_review, PreparationError
    try:
        data=request.get_json(silent=True)
        if not isinstance(data,dict):
            raise PreparationError('بيانات غير صحيحة.')
        return jsonify(success=True, review=price_review(**{k:data.get(k) for k in ('price','cost','shipping','fee_percent','fixed_fee')}))
    except PreparationError as exc:
        return jsonify(success=False,error=str(exc)),400

@agent_routes.route('/ai/product-preparations',methods=['GET','POST'])
def product_preparations():
    from product_workflow import list_preparations, save_proposal, PreparationError
    try:
        if request.method=='POST':
            data=request.get_json(silent=True)
            if not isinstance(data,dict):
                raise PreparationError('بيانات غير صحيحة.')
            return jsonify(success=True, **save_proposal(data.get('product_id'),data.get('proposal'))),201
        return jsonify(success=True, preparations=list_preparations())
    except PreparationError as exc:
        return jsonify(success=False,error=str(exc)),400
    except Exception:
        return jsonify(success=False,error='تعذّر حفظ أو قراءة تجهيز المنتجات؛ لم يبدأ التنفيذ.'),503

@agent_routes.post('/ai/product-preparations/<int:aid>/<decision>')
def preparation_decision(aid, decision):
    from product_workflow import decide, PreparationError
    try:
        return jsonify(success=True,state=decide(aid,decision))
    except PreparationError as exc:
        return jsonify(success=False,error=str(exc)),409
    except Exception:
        return jsonify(success=False,error='راجعي حالة التجهيز وشوبيفاي؛ لا تعيدي التنفيذ قبل التحقق.'),503

@agent_routes.post('/ai/product-preparations/<int:aid>/reconcile')
def preparation_reconcile(aid):
    from product_workflow import reconcile, PreparationError
    try:
        data=request.get_json(silent=True)
        return jsonify(success=True,state=reconcile(aid,(data or {}).get('confirmed') if isinstance(data,dict) else False))
    except PreparationError as exc:
        return jsonify(success=False,error=str(exc)),409
    except Exception:
        return jsonify(success=False,error='تعذّر تسجيل المراجعة.'),503


@agent_routes.before_request
def preparation_request_limit():
    # A reviewed description plus media IDs can exceed the chat's 16 KiB cap.
    if request.path.startswith('/ai/product-preparations'):
        request.max_content_length = 65536


@agent_routes.get('/ai/marketing/archive/status')
def ad_archive_status():
    from advertising_store import status
    try:
        return jsonify(success=True, **status())
    except Exception:
        return jsonify(success=False,error='تعذّر قراءة أرشيف الحملات.'),503


@agent_routes.get('/ai/marketing/archive')
def ad_archive():
    from advertising_store import read_history
    try:
        result=read_history(request.args.get('platform',''),request.args.get('account_id',''),
            request.args.get('start',''),request.args.get('end',''),request.args.get('level','campaign'))
        return jsonify(success=True,report=result)
    except (ValueError,TypeError):
        return jsonify(success=False,error='حددي المنصة والحساب والمستوى وفترة لا تتجاوز ٩٢ يومًا.'),400
    except Exception:
        return jsonify(success=False,error='تعذّر قراءة أرشيف الحملات.'),503


@agent_routes.post('/ai/marketing/sync')
def ad_sync():
    from advertising_sync import queue_sync
    from ads_service import AdsError
    data=request.get_json(silent=True)
    if not isinstance(data,dict):
        return jsonify(success=False,error='بيانات المزامنة غير صحيحة.'),400
    try:
        return jsonify(success=True,**queue_sync(data.get('platform'),data.get('start'),data.get('end'))),202
    except (ValueError,TypeError):
        return jsonify(success=False,error='اختاري منصة وأيامًا مكتملة بمدة حتى ٣١ يومًا؛ قد توجد طلبات كثيرة قيد الانتظار.'),400
    except AdsError:
        return jsonify(success=False,error='تعذّر التحقق من حساب الإعلانات؛ راجعي بيانات الربط والصلاحيات.'),502
    except Exception:
        return jsonify(success=False,error='تعذّر تسجيل المزامنة.'),503


@agent_routes.route('/ai/marketing/policy',methods=['GET','PUT'])
def marketing_policy():
    from marketing_manager import load_policy,save_policy
    data=request.get_json(silent=True) if request.method=='PUT' else request.args
    if not data:return jsonify(success=False,error='بيانات السياسة مطلوبة.'),400
    try:
        platform,aid=data.get('platform'),data.get('account_id')
        policy=save_policy(platform,aid,data.get('policy')) if request.method=='PUT' else load_policy(platform,aid)
        return jsonify(success=True,policy=policy)
    except (ValueError,TypeError,KeyError):return jsonify(success=False,error='راجعي الحساب والعملة والتكاليف وقواعد القرار.'),400
    except Exception:return jsonify(success=False,error='تعذّر الوصول للسياسة.'),503


@agent_routes.post('/ai/marketing/analysis')
def marketing_analysis():
    from marketing_manager import run_analysis
    data=request.get_json(silent=True)
    if not isinstance(data,dict):return jsonify(success=False,error='بيانات غير صحيحة.'),400
    try:
        return jsonify(success=True,analysis=run_analysis(data.get('platform'),data.get('account_id'),data.get('start'),data.get('end'),data.get('level','campaign')))
    except (ValueError,TypeError):return jsonify(success=False,error='راجعي السياسة والحساب والفترة.'),400
    except Exception:return jsonify(success=False,error='تعذّر التحليل؛ لم ينفذ أي إجراء.'),503


@agent_routes.get('/ai/marketing/manager')
def marketing_dashboard():
    from marketing_manager import dashboard
    try:return jsonify(success=True,**dashboard())
    except Exception:return jsonify(success=False,error='تعذّر قراءة التحليلات والتنبيهات.'),503


@agent_routes.post('/ai/marketing/alerts/<int:alert_id>/acknowledge')
def marketing_ack(alert_id):
    from marketing_manager import acknowledge
    try:
        if not acknowledge(alert_id):return jsonify(success=False,error='التنبيه غير موجود.'),404
        return jsonify(success=True)
    except Exception:return jsonify(success=False,error='تعذّر حفظ مراجعة التنبيه.'),503


@agent_routes.post('/ai/marketing/decisions')
def marketing_decision():
    from marketing_manager import record_decision
    data=request.get_json(silent=True)
    if not isinstance(data,dict):return jsonify(success=False,error='بيانات غير صحيحة.'),400
    try:return jsonify(success=True,**record_decision(data.get('analysis_id'),data.get('entity_id'),data.get('placement'),data.get('code'),data.get('outcome'),data.get('note','')))
    except (ValueError,TypeError):return jsonify(success=False,error='القرار أو دليله غير صحيح.'),400
    except Exception:return jsonify(success=False,error='تعذّر تسجيل القرار؛ لم ينفذ أي إجراء.'),503


@agent_routes.post('/ai/marketing/reconcile')
def marketing_reconcile():
    from shopify_reconciliation import reconcile_orders
    data=request.get_json(silent=True)
    if not isinstance(data,dict):return jsonify(success=False,error='بيانات غير صحيحة.'),400
    try:return jsonify(success=True,report=reconcile_orders(data.get('platform'),data.get('account_id'),data.get('start'),data.get('end')))
    except (ValueError,TypeError,KeyError):return jsonify(success=False,error='راجعي الحساب والسياسة والفترة وصلاحية قراءة الطلبات.'),400
    except Exception:return jsonify(success=False,error='تعذّر جلب الطلبات كاملة؛ لم تُرجع مطابقة جزئية.'),503


@agent_routes.post('/ai/marketing/tracking-url')
def marketing_tracking_url():
    from shopify_reconciliation import tracking_url
    data=request.get_json(silent=True)
    if not isinstance(data,dict):return jsonify(success=False,error='بيانات غير صحيحة.'),400
    try:return jsonify(success=True,**tracking_url(data.get('destination',''),data.get('platform'),data.get('campaign_id'),data.get('ad_id')))
    except (ValueError,TypeError):return jsonify(success=False,error='حددي رابط المتجر المسموح ومعرّفات الحملة والإعلان الرقمية.'),400
