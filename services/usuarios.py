"""Reglas de cuentas de usuario y roles."""
from werkzeug.security import generate_password_hash

from core import ROLES
from db import log
from security import other_active_admins


def crear_usuario(db, username, role, password):
    if role not in ROLES: raise ValueError('Rol inválido.')
    if len(password) < 10: raise ValueError('La contraseña debe tener al menos 10 caracteres.')
    with db:
        db.execute('INSERT INTO users(username,password_hash,role) VALUES (?,?,?)',
                   (username, generate_password_hash(password), role))
        log('Usuario creado', f'{username} · {ROLES[role]}')


def cambiar_rol(db, user_id, role, actor_id):
    user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not user: raise LookupError('Usuario no encontrado.')
    if role not in ROLES: raise ValueError('Rol inválido.')
    if user_id == actor_id: raise ValueError('No puedes cambiar tu propio rol.')
    if user['role'] == 'admin' and role != 'admin' and not other_active_admins(user_id):
        raise ValueError('Debe quedar al menos un Administrador activo.')
    with db:
        db.execute('UPDATE users SET role=? WHERE id=?', (role, user_id))
        log('Rol cambiado', f"{user['username']}: {ROLES[role]}")


def cambiar_estado_usuario(db, user_id, actor_id):
    user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not user: raise LookupError('Usuario no encontrado.')
    if user_id == actor_id: raise ValueError('No puedes desactivar tu propia cuenta.')
    if user['active'] and user['role'] == 'admin' and not other_active_admins(user_id):
        raise ValueError('Debe quedar al menos un Administrador activo.')
    new_state = 0 if user['active'] else 1
    with db:
        db.execute('UPDATE users SET active=? WHERE id=?', (new_state, user_id))
        log('Estado de usuario', f"{user['username']}: {'activo' if new_state else 'inactivo'}")
    return new_state


def restablecer_clave(db, user_id, password):
    """Devuelve el nuevo hash para que la ruta actualice la sesión propia si aplica."""
    user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not user: raise LookupError('Usuario no encontrado.')
    if len(password) < 10: raise ValueError('La contraseña debe tener al menos 10 caracteres.')
    new_hash = generate_password_hash(password)
    with db:
        db.execute('UPDATE users SET password_hash=? WHERE id=?', (new_hash, user_id))
        log('Contraseña restablecida', user['username'])
    return new_hash
