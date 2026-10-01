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
