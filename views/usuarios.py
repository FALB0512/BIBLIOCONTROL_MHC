import sqlite3

from flask import abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from core import ROLES, app
from db import connection, log
from security import admin_required, fingerprint, other_active_admins
from validators import val


@app.route('/usuarios')
@admin_required
def users():
    items = connection().execute('SELECT id, username, role, active, created_at FROM users ORDER BY username').fetchall()
    return render_template('usuarios.html', items=items, roles=ROLES, me=session['user_id'])


@app.post('/usuarios/nuevo')
@admin_required
def create_user():
    db = connection()
    try:
        username, role = val('username', 40, True), val('role', 20, True)
        password = request.form.get('password', '')
        if role not in ROLES: raise ValueError('Rol inválido.')
        if len(password) < 10: raise ValueError('La contraseña debe tener al menos 10 caracteres.')
        with db:
            db.execute('INSERT INTO users(username,password_hash,role) VALUES (?,?,?)',
                       (username, generate_password_hash(password), role))
            log('Usuario creado', f'{username} · {ROLES[role]}')
        flash('Usuario creado.', 'success')
    except (ValueError, sqlite3.IntegrityError) as ex:
        flash('Ese nombre de usuario ya existe.' if isinstance(ex, sqlite3.IntegrityError) else str(ex), 'danger')
    return redirect(url_for('users'))


@app.post('/usuarios/<int:user_id>/rol')
@admin_required
def change_role(user_id):
    db = connection()
    user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not user: abort(404)
    try:
        role = val('role', 20, True)
        if role not in ROLES: raise ValueError('Rol inválido.')
        if user_id == session['user_id']: raise ValueError('No puedes cambiar tu propio rol.')
        if user['role'] == 'admin' and role != 'admin' and not other_active_admins(user_id):
            raise ValueError('Debe quedar al menos un Administrador activo.')
        with db:
            db.execute('UPDATE users SET role=? WHERE id=?', (role, user_id))
            log('Rol cambiado', f"{user['username']}: {ROLES[role]}")
        flash('Rol actualizado.', 'success')
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('users'))


@app.post('/usuarios/<int:user_id>/estado')
@admin_required
def toggle_user(user_id):
    db = connection()
    user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not user: abort(404)
    try:
        if user_id == session['user_id']: raise ValueError('No puedes desactivar tu propia cuenta.')
        if user['active'] and user['role'] == 'admin' and not other_active_admins(user_id):
            raise ValueError('Debe quedar al menos un Administrador activo.')
        new_state = 0 if user['active'] else 1
        with db:
            db.execute('UPDATE users SET active=? WHERE id=?', (new_state, user_id))
            log('Estado de usuario', f"{user['username']}: {'activo' if new_state else 'inactivo'}")
        flash('Estado actualizado.', 'success')
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('users'))


@app.post('/usuarios/<int:user_id>/clave')
@admin_required
def reset_password(user_id):
    db = connection()
    user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not user: abort(404)
    try:
        password = request.form.get('password', '')
        if len(password) < 10: raise ValueError('La contraseña debe tener al menos 10 caracteres.')
        new_hash = generate_password_hash(password)
        with db:
            db.execute('UPDATE users SET password_hash=? WHERE id=?', (new_hash, user_id))
            log('Contraseña restablecida', user['username'])
        if user_id == session['user_id']:
            session['pwh'] = fingerprint(new_hash)  # mantiene la sesión propia tras cambiar su clave
        flash('Contraseña actualizada. Las sesiones abiertas de esa cuenta se cerrarán.', 'success')
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('users'))
