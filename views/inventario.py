import sqlite3

import qrcode
import qrcode.image.svg
from flask import abort, flash, redirect, render_template, request, session, url_for

from core import app
from db import connection
from services.inventario import dar_de_baja, editar_ejemplar, registrar_ejemplar
from resumen import construir_resumen
from validators import as_int, val


@app.route('/libros', methods=['GET', 'POST'])
def books():
    db = connection()
    if request.method == 'POST':
        try:
            room_id = as_int('room_id')
            area_id, doc_type = as_int('area_id'), val('doc_type', 5, True)
            fields = [val('title', 200, True), val('author', 150),
                      val('category', 80), val('isbn', 30), val('publisher', 100)]
            condition, notes = val('condition', 20), val('notes', 500)
            code = registrar_ejemplar(db, room_id, area_id, doc_type, fields, condition, notes)
            flash(f'Ejemplar registrado con código {code}.', 'success')
        except (ValueError, sqlite3.IntegrityError) as ex:
            flash('No se pudo generar el código, intenta de nuevo.' if isinstance(ex, sqlite3.IntegrityError) else str(ex), 'danger')
        return redirect(url_for('books'))
    q = request.args.get('q', '').strip()[:100]
    room = request.args.get('room', '').strip()
    sql = '''SELECT b.*,r.name room FROM books b JOIN rooms r ON r.id=b.room_id WHERE b.status != ?'''
    args = ['Baja']  # los ejemplares dados de baja no aparecen en el inventario
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
    svg = qrcode.make(construir_resumen(dict(book)), image_factory=qrcode.image.svg.SvgPathImage,
                      box_size=10, border=2).to_string(encoding='unicode')
    copias = min(max(request.args.get('copias', type=int) or 1, 1), 21)
    return render_template('book_qr.html', book=book, svg=svg, copias=copias)


@app.post('/libros/<int:book_id>/editar')
def edit_book(book_id):
    try:
        fields = (val('title', 200, True), val('author', 150), val('category', 80),
                  val('isbn', 30), val('publisher', 100), val('condition', 20), val('notes', 500))
        area_id = doc_type = None
        if request.form.get('area_id'):  # solo llega si el libro aún no tiene identificador de proceso
            area_id, doc_type = as_int('area_id'), val('doc_type', 5, True)
        new_code = editar_ejemplar(connection(), book_id, fields, area_id, doc_type)
        flash(f'Datos actualizados. Nuevo código: {new_code}.' if new_code else 'Datos bibliográficos actualizados.', 'success')
    except LookupError:
        abort(404)
    except (ValueError, sqlite3.IntegrityError) as ex:
        flash('No se pudo generar el código, intenta de nuevo.' if isinstance(ex, sqlite3.IntegrityError) else str(ex), 'danger')
    return redirect(url_for('books'))


@app.post('/libros/<int:book_id>/baja')
def disable_book(book_id):
    try:
        dar_de_baja(connection(), book_id, val('motivo', 300, True), session['username'])
        flash('Ejemplar dado de baja. Queda archivado en el módulo Bajas.', 'success')
    except LookupError:
        abort(404)
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('books'))
