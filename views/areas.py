import sqlite3

from flask import abort, flash, redirect, render_template, request, url_for

from core import app
from db import connection
from services.areas import cambiar_estado_area, crear_area, crear_tipo, editar_area, eliminar_area
from validators import as_int, val


@app.route('/areas', methods=['GET', 'POST'])
def areas():
    db = connection()
    if request.method == 'POST':
        try:
            crear_area(db, as_int('code'), val('name', 100, True))
            flash('Área registrada.', 'success')
        except (ValueError, sqlite3.IntegrityError) as ex:
            flash('Ese código de área ya existe.' if isinstance(ex, sqlite3.IntegrityError) else str(ex), 'danger')
        return redirect(url_for('areas'))
    items = db.execute('''SELECT a.*, (SELECT COUNT(*) FROM books b WHERE b.area_id=a.id) total
                          FROM areas a ORDER BY a.code''').fetchall()
    return render_template('areas.html', items=items, types=db.execute('SELECT * FROM doc_types ORDER BY rowid').fetchall())


@app.post('/areas/<int:area_id>/estado')
def toggle_area(area_id):
    try:
        cambiar_estado_area(connection(), area_id)
    except LookupError:
        abort(404)
    flash('Estado del área actualizado.', 'success')
    return redirect(url_for('areas'))


@app.post('/tipos')
def create_type():
    try:
        crear_tipo(connection(), val('code', 5, True), val('name', 100, True))
        flash('Tipo de documento registrado.', 'success')
    except (ValueError, sqlite3.IntegrityError) as ex:
        flash('Ese tipo de documento ya existe.' if isinstance(ex, sqlite3.IntegrityError) else str(ex), 'danger')
    return redirect(url_for('areas'))


@app.post('/areas/<int:area_id>/editar')
def edit_area(area_id):
    try:
        editar_area(connection(), area_id, val('name', 100, True))
        flash('Área actualizada.', 'success')
    except LookupError:
        abort(404)
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('areas'))


@app.post('/areas/<int:area_id>/eliminar')
def delete_area(area_id):
    try:
        eliminar_area(connection(), area_id)
        flash('Área eliminada.', 'success')
    except LookupError:
        abort(404)
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('areas'))
