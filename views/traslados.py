from flask import flash, redirect, render_template, request, url_for

from core import app
from db import connection
from services.traslados import trasladar_ejemplar
from validators import as_int, val


@app.route('/traslados', methods=['GET', 'POST'])
def transfers():
    db = connection()
    if request.method == 'POST':
        try:
            book_id, to_room = as_int('book_id'), as_int('to_room_id')
            person, notes = val('person', 150, True), val('notes', 500)
            trasladar_ejemplar(db, book_id, to_room, person, notes)
            flash('Traslado registrado.', 'success')
        except ValueError as ex:
            flash(str(ex), 'danger')
        return redirect(url_for('transfers'))
    items = db.execute('''SELECT t.*,b.code,b.title, a.name source, z.name destination
                           FROM transfers t JOIN books b ON b.id=t.book_id
                           JOIN rooms a ON a.id=t.from_room_id JOIN rooms z ON z.id=t.to_room_id
                           ORDER BY t.id DESC''').fetchall()
    available = db.execute("SELECT id,code,title,room_id FROM books WHERE status='Disponible' ORDER BY title").fetchall()
    rooms_list = db.execute('SELECT id,name FROM rooms WHERE active=1 ORDER BY name').fetchall()
    return render_template('transfers.html', items=items, available=available, rooms=rooms_list)
