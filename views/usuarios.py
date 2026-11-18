import sqlite3

from flask import abort, flash, redirect, render_template, request, session, url_for

from core import ROLES, app
from db import connection
from security import admin_required, fingerprint
from services.usuarios import cambiar_estado_usuario, cambiar_rol, crear_usuario, restablecer_clave
from validators import val


@app.route('/usuarios')
@admin_required
def users():
    items = connection().execute('SELECT id, username, role, active, created_at FROM users ORDER BY username').fetchall()
    return render_template('usuarios.html', items=items, roles=ROLES, me=session['user_id'])


@app.post('/usuarios/nuevo')
@admin_required
def create_user():
    try:
        crear_usuario(connection(), val('username', 40, True), val('role', 20, True), request.form.get('password', ''))
        flash('Usuario creado.', 'success')
    except (ValueError, sqlite3.IntegrityError) as ex:
        flash('Ese nombre de usuario ya existe.' if isinstance(ex, sqlite3.IntegrityError) else str(ex), 'danger')
    return redirect(url_for('users'))


@app.post('/usuarios/<int:user_id>/rol')
@admin_required
def change_role(user_id):
    try:
        cambiar_rol(connection(), user_id, val('role', 20, True), session['user_id'])
        flash('Rol actualizado.', 'success')
    except LookupError:
        abort(404)
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('users'))


@app.post('/usuarios/<int:user_id>/estado')
@admin_required
def toggle_user(user_id):
    try:
        cambiar_estado_usuario(connection(), user_id, session['user_id'])
        flash('Estado actualizado.', 'success')
    except LookupError:
        abort(404)
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('users'))


@app.post('/usuarios/<int:user_id>/clave')
@admin_required
def reset_password(user_id):
    try:
        new_hash = restablecer_clave(connection(), user_id, request.form.get('password', ''))
        if user_id == session['user_id']:
            session['pwh'] = fingerprint(new_hash)  # mantiene la sesión propia tras cambiar su clave
        flash('Contraseña actualizada. Las sesiones abiertas de esa cuenta se cerrarán.', 'success')
    except LookupError:
        abort(404)
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('users'))
