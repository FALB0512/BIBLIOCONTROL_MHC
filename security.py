import hashlib
import time
from functools import wraps
from urllib.parse import urlparse

from flask import flash, redirect, request, session, url_for

from db import connection


def safe_back():
    """Vuelve a la página anterior solo si es de este mismo sitio; si no, al panel."""
    ref = urlparse(request.referrer or '')
    if ref.netloc == request.host and ref.path:
        return ref.path + (f'?{ref.query}' if ref.query else '')
    return url_for('dashboard')


def fingerprint(password_hash):
    """Huella del hash de contraseña: si cambia, las sesiones anteriores dejan de ser válidas."""
    return hashlib.sha256(password_hash.encode()).hexdigest()


LOGIN_FAILS = {}  # usuario -> (intentos, inicio de la ventana, bloqueado hasta)
MAX_FAILS, FAIL_WINDOW, LOCK_SECONDS = 5, 900, 900


def login_blocked(username):
    entry = LOGIN_FAILS.get(username)
    return bool(entry) and entry[2] > time.time()


def register_failure(username):
    now = time.time()
    count, since, _ = LOGIN_FAILS.get(username, (0, now, 0))
    if now - since > FAIL_WINDOW:
        count, since = 0, now
    count += 1
    LOGIN_FAILS[username] = (count, since, now + LOCK_SECONDS if count >= MAX_FAILS else 0)


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Solo un Administrador puede gestionar usuarios.', 'danger')
            return redirect(url_for('dashboard'))
        return view(*args, **kwargs)
    return wrapper


def other_active_admins(user_id):
    return connection().execute("SELECT count(*) FROM users WHERE role='admin' AND active=1 AND id<>?",
                                (user_id,)).fetchone()[0]
