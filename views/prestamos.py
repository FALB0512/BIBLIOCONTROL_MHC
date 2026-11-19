import sqlite3

from flask import flash, redirect, render_template, request, url_for

from core import app
from db import connection
from services.prestamos import registrar_devolucion, registrar_prestamo
from validators import as_int, dateval, val


@app.route('/prestamos', methods=['GET', 'POST'])
def loans():
    db = connection()
    if request.method == 'POST':
        try:
            book_id = as_int('book_id')
            borrower = val('borrower', 150, True)
            department, loan_date, due_date, notes = val('department', 100), dateval('loan_date'), dateval('due_date'), val('notes', 500)
            registrar_prestamo(db, book_id, borrower, department, loan_date, due_date, notes)
            flash('Préstamo registrado.', 'success')
        except (ValueError, sqlite3.IntegrityError) as ex:
            flash(str(ex), 'danger')
        return redirect(url_for('loans'))
    items = db.execute('''SELECT l.*, b.code, b.title, r.name room FROM loans l
                           JOIN books b ON b.id=l.book_id JOIN rooms r ON r.id=b.room_id
                           ORDER BY (l.return_date IS NULL) DESC, l.id DESC''').fetchall()
    rooms_list = db.execute('SELECT id,name FROM rooms WHERE active=1 ORDER BY name').fetchall()
    return render_template('loans.html', items=items, rooms=rooms_list)


@app.post('/prestamos/<int:loan_id>/devolver')
def return_book(loan_id):
    try:
        registrar_devolucion(connection(), loan_id, dateval('return_date'))
        flash('Devolución registrada.', 'success')
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('loans'))
