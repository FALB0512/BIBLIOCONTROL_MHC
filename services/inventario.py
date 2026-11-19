"""Reglas de inventario: registro, edición y baja de ejemplares."""
from db import log
from services.areas import next_identifier

CONDICIONES = ('Bueno', 'Regular', 'Deteriorado')


def registrar_ejemplar(db, room_id, area_id, doc_type, fields, condition, notes):
    if not db.execute('SELECT 1 FROM rooms WHERE id=? AND active=1', (room_id,)).fetchone():
        raise ValueError('La sala seleccionada no existe.')
    if condition not in CONDICIONES: raise ValueError('Estado físico inválido.')
    with db:
        code, seq = next_identifier(db, area_id, doc_type)
        db.execute('''INSERT INTO books(code,title,author,category,isbn,publisher,room_id,condition,notes,
                      area_id,doc_type,seq) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                   (code, *fields, room_id, condition, notes, area_id, doc_type, seq))
        log('Libro registrado', f'{code} · {fields[0]}')
    return code


def editar_ejemplar(db, book_id, fields, area_id=None, doc_type=None):
    """fields: título, autor, categoría, ISBN, editorial, condición y observaciones."""
    if fields[5] not in CONDICIONES: raise ValueError('Estado físico inválido.')
    with db:
        book = db.execute('SELECT * FROM books WHERE id=?', (book_id,)).fetchone()
        if not book: raise LookupError('Ejemplar no encontrado.')
        extra_sql, extra_args, new_code = '', [], None
        if book['area_id'] is None:  # libro anterior al identificador de proceso: se le asigna uno nuevo
            if area_id is None: raise ValueError('Selecciona área y tipo para asignar el nuevo código.')
            new_code, seq = next_identifier(db, area_id, doc_type)
            extra_sql, extra_args = ', code=?, area_id=?, doc_type=?, seq=?', [new_code, area_id, doc_type, seq]
        db.execute(f'''UPDATE books SET title=?,author=?,category=?,isbn=?,publisher=?,condition=?,notes=?{extra_sql}
                       WHERE id=?''', (*fields, *extra_args, book_id))
        log('Libro editado', f"{new_code or book['code']}: {fields[0]}")
    return new_code


def dar_de_baja(db, book_id, motivo, responsable):
    """Da de baja el ejemplar y archiva una copia de sus datos junto con el motivo."""
    if not (motivo or '').strip(): raise ValueError('Indica el motivo de la baja.')
    with db:
        book = db.execute('''SELECT b.*, r.name room_name FROM books b JOIN rooms r ON r.id=b.room_id
                             WHERE b.id=?''', (book_id,)).fetchone()
        if not book: raise LookupError('Ejemplar no encontrado.')
        if book['status'] == 'Prestado': raise ValueError('No se puede dar de baja un ejemplar prestado.')
        if book['status'] == 'Baja': raise ValueError('El ejemplar ya está dado de baja.')
        db.execute('''INSERT INTO bajas(book_id,code,title,author,category,isbn,publisher,condition,notes,
                      room_id,room_name,motivo,responsable)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                   (book_id, book['code'], book['title'], book['author'], book['category'], book['isbn'],
                    book['publisher'], book['condition'], book['notes'], book['room_id'], book['room_name'],
                    motivo.strip(), responsable))
        db.execute("UPDATE books SET status='Baja' WHERE id=?", (book_id,))
        log('Baja de ejemplar', f"{book['code']} · {motivo.strip()}")
    return book['code']
