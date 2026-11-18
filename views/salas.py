import sqlite3

from flask import abort, flash, redirect, render_template, request, url_for

from core import app
from db import connection, log
from validators import val


@app.route('/salas', methods=['GET', 'POST'])
def rooms():
    db = connection()
    if request.method == 'POST':
        try:
            name, location, responsible = val('name', 100, True), val('location', 150), val('responsible', 120)
            with db:
                db.execute('INSERT INTO rooms(name,location,responsible) VALUES (?,?,?)', (name, location, responsible))
                log('Sala creada', name)
            flash('Sala registrada correctamente.', 'success')
        except (ValueError, sqlite3.IntegrityError) as ex:
            flash(str(ex), 'danger')
        return redirect(url_for('rooms'))
    items = db.execute('''SELECT r.*, COUNT(b.id) total FROM rooms r
                          LEFT JOIN books b ON b.room_id=r.id GROUP BY r.id ORDER BY r.name''').fetchall()
    return render_template('rooms.html', items=items)


@app.post('/salas/<int:room_id>/editar')
def edit_room(room_id):
    db = connection()
    try:
        name, location, responsible = val('name', 100, True), val('location', 150), val('responsible', 120)
        with db:
            cur = db.execute('UPDATE rooms SET name=?,location=?,responsible=? WHERE id=?',
                             (name, location, responsible, room_id))
            if not cur.rowcount: abort(404)
            log('Sala editada', name)
        flash('Sala actualizada.', 'success')
    except (ValueError, sqlite3.IntegrityError) as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('rooms'))


@app.post('/salas/<int:room_id>/estado')
def toggle_room(room_id):
    db = connection()
    room = db.execute('SELECT * FROM rooms WHERE id=?', (room_id,)).fetchone()
    if not room: abort(404)
    try:
        with db:
            if room['active']:
                count = db.execute('SELECT count(*) FROM books WHERE room_id=?', (room_id,)).fetchone()[0]
                if count:
                    raise ValueError(f'No se puede desactivar: la sala tiene {count} ejemplar(es). Traslada primero los ejemplares.')
            new_state = 0 if room['active'] else 1
            db.execute('UPDATE rooms SET active=? WHERE id=?', (new_state, room_id))
            log('Estado de sala', f"{room['name']}: {'activa' if new_state else 'inactiva'}")
        flash('Estado de la sala actualizado.', 'success')
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('rooms'))
