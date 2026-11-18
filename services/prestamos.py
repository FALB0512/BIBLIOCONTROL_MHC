"""Reglas de préstamos y devoluciones."""
from db import log


def registrar_prestamo(db, book_id, borrower, department, loan_date, due_date, notes):
    if due_date < loan_date: raise ValueError('La fecha límite debe ser igual o posterior a la fecha del préstamo.')
    with db:
        changed = db.execute("UPDATE books SET status='Prestado' WHERE id=? AND status='Disponible'", (book_id,))
        if not changed.rowcount: raise ValueError('El ejemplar no está disponible para préstamo.')
        db.execute('''INSERT INTO loans(book_id,borrower,department,loan_date,due_date,notes)
                      VALUES (?,?,?,?,?,?)''', (book_id, borrower, department, loan_date, due_date, notes))
        log('Préstamo', f'Ejemplar ID {book_id} entregado a {borrower}')


def registrar_devolucion(db, loan_id, returned):
    with db:
        loan = db.execute('SELECT * FROM loans WHERE id=? AND return_date IS NULL', (loan_id,)).fetchone()
        if not loan: raise ValueError('El préstamo ya fue devuelto o no existe.')
        if returned < loan['loan_date']: raise ValueError('La devolución no puede ser anterior al préstamo.')
        db.execute('UPDATE loans SET return_date=? WHERE id=?', (returned, loan_id))
        db.execute("UPDATE books SET status='Disponible' WHERE id=?", (loan['book_id'],))
        log('Devolución', f'Préstamo ID {loan_id} · ejemplar ID {loan["book_id"]}')
