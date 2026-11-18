import sqlite3

from flask import abort, flash, redirect, render_template, request, url_for

from core import app
from db import connection
from services.salas import cambiar_estado_sala, crear_sala, editar_sala
from validators import val


@app.route('/salas', methods=['GET', 'POST'])
def rooms():
    db = connection()
    if request.method == 'POST':
        try:
            crear_sala(db, val('name', 100, True), val('location', 150), val('responsible', 120))
            flash('Sala registrada correctamente.', 'success')
        except (ValueError, sqlite3.IntegrityError) as ex:
            flash(str(ex), 'danger')
        return redirect(url_for('rooms'))
    items = db.execute('''SELECT r.*, COUNT(b.id) total FROM rooms r
                          LEFT JOIN books b ON b.room_id=r.id GROUP BY r.id ORDER BY r.name''').fetchall()
    return render_template('rooms.html', items=items)


@app.post('/salas/<int:room_id>/editar')
def edit_room(room_id):
    try:
        editar_sala(connection(), room_id, val('name', 100, True), val('location', 150), val('responsible', 120))
        flash('Sala actualizada.', 'success')
    except LookupError:
        abort(404)
    except (ValueError, sqlite3.IntegrityError) as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('rooms'))


@app.post('/salas/<int:room_id>/estado')
def toggle_room(room_id):
    try:
        cambiar_estado_sala(connection(), room_id)
        flash('Estado de la sala actualizado.', 'success')
    except LookupError:
        abort(404)
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('rooms'))
