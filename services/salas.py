"""Reglas de salas de reunión."""
from db import log


def crear_sala(db, name, location, responsible):
    with db:
        db.execute('INSERT INTO rooms(name,location,responsible) VALUES (?,?,?)', (name, location, responsible))
        log('Sala creada', name)


def editar_sala(db, room_id, name, location, responsible):
    with db:
        cur = db.execute('UPDATE rooms SET name=?,location=?,responsible=? WHERE id=?',
                         (name, location, responsible, room_id))
        if not cur.rowcount: raise LookupError('Sala no encontrada.')
        log('Sala editada', name)


def cambiar_estado_sala(db, room_id):
    room = db.execute('SELECT * FROM rooms WHERE id=?', (room_id,)).fetchone()
    if not room: raise LookupError('Sala no encontrada.')
    with db:
        if room['active']:
            count = db.execute('SELECT count(*) FROM books WHERE room_id=?', (room_id,)).fetchone()[0]
            if count:
                raise ValueError(f'No se puede desactivar: la sala tiene {count} ejemplar(es). Traslada primero los ejemplares.')
        new_state = 0 if room['active'] else 1
        db.execute('UPDATE rooms SET active=? WHERE id=?', (new_state, room_id))
        log('Estado de sala', f"{room['name']}: {'activa' if new_state else 'inactiva'}")
    return new_state


def eliminar_sala(db, room_id):
    room = db.execute('SELECT * FROM rooms WHERE id=?', (room_id,)).fetchone()
    if not room: raise LookupError('Sala no encontrada.')
    count = db.execute('SELECT count(*) FROM books WHERE room_id=?', (room_id,)).fetchone()[0]
    if count: raise ValueError(f'No se puede eliminar: la sala tiene {count} ejemplar(es). Puedes desactivarla.')
    historial = db.execute("""SELECT (SELECT count(*) FROM transfers WHERE from_room_id=? OR to_room_id=?)
                              + (SELECT count(*) FROM audits WHERE room_id=?)
                              + (SELECT count(*) FROM bajas WHERE room_id=?)""",
                           (room_id, room_id, room_id, room_id)).fetchone()[0]
    if historial: raise ValueError('No se puede eliminar: la sala tiene historial de traslados, auditorías o bajas. Puedes desactivarla.')
    with db:
        db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
        log('Sala eliminada', room['name'])
