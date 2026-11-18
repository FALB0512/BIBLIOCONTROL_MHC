from flask import flash, redirect, render_template, request, url_for

from core import app
from db import connection, log
from validators import as_int, val


@app.route('/traslados', methods=['GET','POST'])
def transfers():
    db = connection()
    if request.method == 'POST':
        try:
            book_id, to_room = as_int('book_id'), as_int('to_room_id')
            person, notes = val('person', 150, True), val('notes', 500)
            with db:
                book = db.execute('SELECT * FROM books WHERE id=?', (book_id,)).fetchone()
                if not book or book['status'] != 'Disponible':
                    raise ValueError('Solo se pueden trasladar ejemplares disponibles.')
                if to_room == book['room_id']: raise ValueError('Selecciona una sala de destino diferente.')
                if not db.execute('SELECT 1 FROM rooms WHERE id=? AND active=1', (to_room,)).fetchone():
                    raise ValueError('La sala de destino no existe.')
                db.execute('''INSERT INTO transfers(book_id,from_room_id,to_room_id,person,notes)
                              VALUES (?,?,?,?,?)''', (book_id, book['room_id'], to_room, person, notes))
                db.execute('UPDATE books SET room_id=? WHERE id=?', (to_room, book_id))
                log('Traslado', f"{book['code']}: sala {book['room_id']} → {to_room}")
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
