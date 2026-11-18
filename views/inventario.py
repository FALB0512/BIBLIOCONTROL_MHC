import sqlite3

import qrcode
import qrcode.image.svg
from flask import abort, flash, redirect, render_template, request, url_for

from core import app
from db import connection, log
from validators import as_int, val
from views.areas import next_identifier


@app.route('/libros', methods=['GET', 'POST'])
def books():
    db = connection()
    if request.method == 'POST':
        try:
            room_id = as_int('room_id')
            if not db.execute('SELECT 1 FROM rooms WHERE id=? AND active=1', (room_id,)).fetchone():
                raise ValueError('La sala seleccionada no existe.')
            area_id, doc_type = as_int('area_id'), val('doc_type', 5, True)
            fields = [val('title', 200, True), val('author', 150),
                      val('category', 80), val('isbn', 30), val('publisher', 100)]
            condition, notes = val('condition', 20), val('notes', 500)
            if condition not in ('Bueno','Regular','Deteriorado'): raise ValueError('Estado físico inválido.')
            with db:
                code, seq = next_identifier(db, area_id, doc_type)
                db.execute('''INSERT INTO books(code,title,author,category,isbn,publisher,room_id,condition,notes,
                              area_id,doc_type,seq) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                           (code, *fields, room_id, condition, notes, area_id, doc_type, seq))
                log('Libro registrado', f'{code} · {fields[0]}')
            flash(f'Ejemplar registrado con código {code}.', 'success')
        except (ValueError, sqlite3.IntegrityError) as ex:
            flash('No se pudo generar el código, intenta de nuevo.' if isinstance(ex, sqlite3.IntegrityError) else str(ex), 'danger')
        return redirect(url_for('books'))
    q = request.args.get('q', '').strip()[:100]
    room = request.args.get('room', '').strip()
    sql = '''SELECT b.*,r.name room FROM books b JOIN rooms r ON r.id=b.room_id WHERE 1=1'''
    args = []
    if q:
        sql += ' AND (b.code LIKE ? OR b.title LIKE ? OR b.author LIKE ?)'
        args += [f'%{q}%'] * 3
    if room.isdigit():
        sql += ' AND b.room_id=?'; args.append(int(room))
    sql += ' ORDER BY b.id DESC'
    return render_template('books.html', items=db.execute(sql, args).fetchall(),
                           rooms=db.execute('SELECT * FROM rooms WHERE active=1 ORDER BY name').fetchall(), q=q, chosen_room=room,
                           areas=db.execute('SELECT * FROM areas WHERE active=1 ORDER BY code').fetchall(),
                           types=db.execute('SELECT * FROM doc_types ORDER BY rowid').fetchall())


@app.get('/libros/<int:book_id>/qr')
def book_qr(book_id):
    book = connection().execute('''SELECT b.*, r.name room FROM books b JOIN rooms r ON r.id=b.room_id
                                   WHERE b.id=?''', (book_id,)).fetchone()
    if not book: abort(404)
    svg = qrcode.make(book['code'], image_factory=qrcode.image.svg.SvgPathImage,
                      box_size=10, border=2).to_string(encoding='unicode')
    return render_template('book_qr.html', book=book, svg=svg)


@app.post('/libros/<int:book_id>/editar')
def edit_book(book_id):
    db = connection()
    try:
        fields = (val('title', 200, True), val('author', 150), val('category', 80),
                  val('isbn', 30), val('publisher', 100), val('condition', 20), val('notes', 500))
        if fields[5] not in ('Bueno','Regular','Deteriorado'): raise ValueError('Estado físico inválido.')
        with db:
            book = db.execute('SELECT * FROM books WHERE id=?', (book_id,)).fetchone()
            if not book: abort(404)
            extra_sql, extra_args, new_code = '', [], None
            if book['area_id'] is None:  # libro anterior al identificador de proceso: se le asigna uno nuevo
                if not request.form.get('area_id'): raise ValueError('Selecciona área y tipo para asignar el nuevo código.')
                area_id, doc_type = as_int('area_id'), val('doc_type', 5, True)
                new_code, seq = next_identifier(db, area_id, doc_type)
                extra_sql, extra_args = ', code=?, area_id=?, doc_type=?, seq=?', [new_code, area_id, doc_type, seq]
            db.execute(f'''UPDATE books SET title=?,author=?,category=?,isbn=?,publisher=?,condition=?,notes=?{extra_sql}
                           WHERE id=?''', (*fields, *extra_args, book_id))
            log('Libro editado', f"{new_code or book['code']}: {fields[0]}")
        flash(f'Datos actualizados. Nuevo código: {new_code}.' if new_code else 'Datos bibliográficos actualizados.', 'success')
    except (ValueError, sqlite3.IntegrityError) as ex:
        flash('No se pudo generar el código, intenta de nuevo.' if isinstance(ex, sqlite3.IntegrityError) else str(ex), 'danger')
    return redirect(url_for('books'))


@app.post('/libros/<int:book_id>/baja')
def disable_book(book_id):
    db = connection()
    try:
        with db:
            book = db.execute('SELECT * FROM books WHERE id=?', (book_id,)).fetchone()
            if not book: abort(404)
            if book['status'] == 'Prestado': raise ValueError('No se puede dar de baja un ejemplar prestado.')
            next_status = 'Disponible' if book['status'] == 'Baja' else 'Baja'
            db.execute('UPDATE books SET status=? WHERE id=?', (next_status, book_id))
            log('Cambio de estado', f"{book['code']}: {next_status}")
        flash('Estado actualizado.', 'success')
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('books'))
