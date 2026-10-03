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
