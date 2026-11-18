"""Reglas de traslados entre salas."""
from db import log


def trasladar_ejemplar(db, book_id, to_room, person, notes):
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
