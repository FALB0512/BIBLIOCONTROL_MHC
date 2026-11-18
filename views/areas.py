import sqlite3

from flask import abort, flash, redirect, render_template, request, url_for

from core import app
from db import connection, log
from validators import as_int, val


def identifier_parts(db, area_id, doc_type):
    """Valida área activa y tipo; devuelve el código numérico del área."""
    area = db.execute('SELECT code FROM areas WHERE id=? AND active=1', (area_id,)).fetchone()
    if not area: raise ValueError('Selecciona un área activa.')
    if not db.execute('SELECT 1 FROM doc_types WHERE code=?', (doc_type,)).fetchone():
        raise ValueError('Tipo de documento inválido.')
    return area['code']


def next_identifier(db, area_id, doc_type):
    area_code = identifier_parts(db, area_id, doc_type)
    seq = db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM books WHERE area_id=? AND doc_type=?',
                     (area_id, doc_type)).fetchone()[0]
    return f'{area_code} {doc_type}-{seq:03d}', seq


@app.route('/areas', methods=['GET', 'POST'])
def areas():
    db = connection()
    if request.method == 'POST':
        try:
            code, name = as_int('code'), val('name', 100, True)
            if not 100 <= code <= 2000: raise ValueError('El código de área debe estar entre 100 y 2000.')
            with db:
                db.execute('INSERT INTO areas(code,name) VALUES (?,?)', (code, name))
                log('Área creada', f'{code} · {name}')
            flash('Área registrada.', 'success')
        except (ValueError, sqlite3.IntegrityError) as ex:
            flash('Ese código de área ya existe.' if isinstance(ex, sqlite3.IntegrityError) else str(ex), 'danger')
        return redirect(url_for('areas'))
    items = db.execute('''SELECT a.*, (SELECT COUNT(*) FROM books b WHERE b.area_id=a.id) total
                          FROM areas a ORDER BY a.code''').fetchall()
    return render_template('areas.html', items=items, types=db.execute('SELECT * FROM doc_types ORDER BY rowid').fetchall())


@app.post('/areas/<int:area_id>/estado')
def toggle_area(area_id):
    db = connection()
    area = db.execute('SELECT * FROM areas WHERE id=?', (area_id,)).fetchone()
    if not area: abort(404)
    new_state = 0 if area['active'] else 1
    with db:
        db.execute('UPDATE areas SET active=? WHERE id=?', (new_state, area_id))
        log('Estado de área', f"{area['code']}: {'activa' if new_state else 'inactiva'}")
    flash('Estado del área actualizado.', 'success')
    return redirect(url_for('areas'))
