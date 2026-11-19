import secrets
from datetime import date

from flask import abort, flash, redirect, request, session, url_for

from core import ADMIN_ONLY_POST, ROLES, WRITE_ROLES, app
from db import connection, init_db
from security import fingerprint, safe_back


@app.before_request
def before():
    init_db()
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    if request.method == 'POST' and not secrets.compare_digest(
            session.get('csrf', ''), request.form.get('csrf', '')):
        abort(400, 'Formulario inválido. Actualiza la página y vuelve a intentarlo.')
    allowed = {'setup', 'login', 'static'}
    endpoint = request.endpoint
    if not connection().execute('SELECT 1 FROM users LIMIT 1').fetchone():
        if endpoint not in {'setup', 'static'}:
            return redirect(url_for('setup'))
    elif endpoint not in allowed and not session.get('user_id'):
        return redirect(url_for('login'))
    if session.get('user_id'):
        current = connection().execute('SELECT role, active, password_hash FROM users WHERE id=?',
                                       (session['user_id'],)).fetchone()
        if (not current or not current['active']
                or session.get('pwh') != fingerprint(current['password_hash'])):
            session.clear()
            flash('Tu cuenta no está activa o la sesión expiró. Inicia sesión nuevamente.', 'danger')
            return redirect(url_for('login'))
        session['role'] = current['role']  # los cambios de rol aplican de inmediato
    if (request.method == 'POST' and session.get('user_id') and endpoint != 'logout'
            and session.get('role') not in WRITE_ROLES):
        flash('Tu rol de Consulta no permite modificar datos.', 'danger')
        return redirect(safe_back())
    if (request.method == 'POST' and session.get('user_id') and session.get('role') != 'admin'
            and endpoint in ADMIN_ONLY_POST):
        flash('Solo el Administrador puede realizar esta acción.', 'danger')
        return redirect(safe_back())


@app.context_processor
def context():
    return {'csrf_token': session.get('csrf', ''), 'current_user': session.get('username'),
            'current_role': ROLES.get(session.get('role'), ''), 'is_admin': session.get('role') == 'admin',
            'can_write': session.get('role') in WRITE_ROLES,
            'today': date.today().isoformat()}
