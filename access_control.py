import hmac
import os
import secrets
from datetime import timedelta
from flask import Blueprint, current_app, jsonify, redirect, render_template_string, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from database import login_allowed, record_login_failure, clear_login_failures

access = Blueprint('access', __name__)
LOGIN = '''<!doctype html><html lang="ar" dir="rtl"><meta name="viewport" content="width=device-width,initial-scale=1"><title>دخول Luree</title><body style="background:#10121a;color:#eee;font-family:Arial;padding:30px;max-width:420px;margin:auto"><h1 style="color:#eac884">Luree AI</h1><p>دخول خاص بغصون</p><p role="alert">{{ error }}</p><form method="post"><input type="hidden" name="csrf" value="{{ csrf }}"><label>كلمة المرور <input name="password" type="password" autocomplete="current-password" required maxlength="256"></label><button type="submit">دخول</button></form></body></html>'''

def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']

def configured():
    return bool(current_app.secret_key and len(current_app.secret_key) >= 32 and current_app.config.get('AGENT_PASSWORD_HASH') and os.environ.get('DATABASE_URL'))

def init_access(app):
    app.secret_key = os.environ.get('AGENT_SESSION_SECRET', '')
    password = os.environ.get('AGENT_PASSWORD', '')
    app.config['AGENT_PASSWORD_HASH'] = os.environ.get('AGENT_PASSWORD_HASH') or (generate_password_hash(password) if len(password) >= 12 else '')
    app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Lax', PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
                      MAX_CONTENT_LENGTH=16384)
    app.register_blueprint(access)
    app.jinja_env.globals['csrf_token'] = csrf_token

    @app.before_request
    def protect():
        if request.path in ('/health', '/ai/health'):
            return None
        if not configured():
            return jsonify(success=False, error='يجب إعداد حماية الدخول في Railway أولًا.'), 503
        if request.path == '/login':
            return None
        if not session.get('owner'):
            if request.path == '/assistant' or request.path == '/':
                return redirect('/login')
            return jsonify(success=False, error='يلزم تسجيل الدخول.'), 401
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            provided = request.headers.get('X-CSRF-Token', '')
            if not hmac.compare_digest(provided, session.get('csrf', '')) or not provided:
                return jsonify(success=False, error='حدّثي الصفحة ثم جرّبي مجددًا.'), 403

    @app.after_request
    def private_response(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        return response

@access.route('/login', methods=['GET', 'POST'])
def login():
    token = csrf_token()
    error = ''
    if request.method == 'POST':
        if not hmac.compare_digest(request.form.get('csrf', ''), token):
            return render_template_string(LOGIN, error='حدّثي الصفحة.', csrf=token), 403
        try:
            if not login_allowed():
                return render_template_string(LOGIN, error='محاولات كثيرة. انتظري خمس دقائق.', csrf=token), 429
            password = request.form.get('password', '')
            if len(password) <= 256 and check_password_hash(current_app.config['AGENT_PASSWORD_HASH'], password):
                clear_login_failures()
                session.clear()
                session['owner'] = True
                session.permanent = True
                csrf_token()
                return redirect('/assistant')
            record_login_failure()
            error = 'كلمة المرور غير صحيحة.'
        except Exception:
            current_app.logger.exception('Login storage failure')
            return render_template_string(LOGIN, error='تعذّر الاتصال. جرّبي مجددًا.', csrf=token), 503
        return render_template_string(LOGIN, error=error, csrf=token), 401
    return render_template_string(LOGIN, error=error, csrf=token)

@access.post('/logout')
def logout():
    session.clear()
    return jsonify(success=True)
