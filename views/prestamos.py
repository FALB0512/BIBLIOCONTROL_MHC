import sqlite3

from flask import flash, redirect, render_template, request, url_for

from core import app
from db import connection, log
from validators import as_int, dateval, val


@app.route('/prestamos', methods=['GET', 'POST'])
def loans():
    db = connection()
    if request.method == 'POST':
        try:
            book_id = as_int('book_id')
            borrower = val('borrower', 150, True)
            department, loan_date, due_date, notes = val('department', 100), dateval('loan_date'), dateval('due_date'), val('notes', 500)
            if due_date < loan_date: raise ValueError('La fecha límite debe ser igual o posterior a la fecha del préstamo.')
            with db:
                changed = db.execute("UPDATE books SET status='Prestado' WHERE id=? AND status='Disponible'", (book_id,))
                if not changed.rowcount: raise ValueError('El ejemplar no está disponible para préstamo.')
                db.execute('''INSERT INTO loans(book_id,borrower,department,loan_date,due_date,notes)
                              VALUES (?,?,?,?,?,?)''', (book_id, borrower, department, loan_date, due_date, notes))
                log('Préstamo', f'Ejemplar ID {book_id} entregado a {borrower}')
            flash('Préstamo registrado.', 'success')
        except (ValueError, sqlite3.IntegrityError) as ex:
            flash(str(ex), 'danger')
        return redirect(url_for('loans'))
    items = db.execute('''SELECT l.*, b.code, b.title, r.name room FROM loans l
                           JOIN books b ON b.id=l.book_id JOIN rooms r ON r.id=b.room_id
                           ORDER BY (l.return_date IS NULL) DESC, l.id DESC''').fetchall()
    available = db.execute("SELECT id,code,title FROM books WHERE status='Disponible' ORDER BY title").fetchall()
    return render_template('loans.html', items=items, available=available)


@app.post('/prestamos/<int:loan_id>/devolver')
def return_book(loan_id):
    db = connection()
    try:
        returned = dateval('return_date')
        with db:
            loan = db.execute('SELECT * FROM loans WHERE id=? AND return_date IS NULL', (loan_id,)).fetchone()
            if not loan: raise ValueError('El préstamo ya fue devuelto o no existe.')
            if returned < loan['loan_date']: raise ValueError('La devolución no puede ser anterior al préstamo.')
            db.execute('UPDATE loans SET return_date=? WHERE id=?', (returned, loan_id))
            db.execute("UPDATE books SET status='Disponible' WHERE id=?", (loan['book_id'],))
            log('Devolución', f'Préstamo ID {loan_id} · ejemplar ID {loan["book_id"]}')
        flash('Devolución registrada.', 'success')
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('loans'))
