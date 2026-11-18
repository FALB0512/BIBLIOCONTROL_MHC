import secrets

from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from core import app
from db import connection
from security import LOGIN_FAILS, fingerprint, login_blocked, register_failure
from validators import val


@app.route('/configuracion', methods=['GET', 'POST'])
def setup():
    if connection().execute('SELECT 1 FROM users LIMIT 1').fetchone():
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = val('username', 40, True)
        password = request.form.get('password', '')
        if len(password) < 10:
            flash('La contraseña debe tener al menos 10 caracteres.', 'danger')
        else:
            connection().execute("INSERT INTO users(username,password_hash,role) VALUES (?,?,'admin')",
                                 (username, generate_password_hash(password)))
            connection().commit()
            flash('Administrador creado. Inicia sesión.', 'success')
            return redirect(url_for('login'))
    return render_template('setup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = val('username', 40)
        key = username.lower()
        if login_blocked(key):
            flash('Demasiados intentos fallidos. Espera 15 minutos e inténtalo de nuevo.', 'danger')
            return render_template('login.html')
        user = connection().execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if user and user['active'] and check_password_hash(user['password_hash'], request.form.get('password', '')):
            LOGIN_FAILS.pop(key, None)
            session.clear()
            session.update(user_id=user['id'], username=user['username'], role=user['role'],
                           pwh=fingerprint(user['password_hash']), csrf=secrets.token_urlsafe(32))
            return redirect(url_for('dashboard'))
        register_failure(key)
        flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')


@app.post('/salir')
def logout():
    session.clear()
    return redirect(url_for('login'))
