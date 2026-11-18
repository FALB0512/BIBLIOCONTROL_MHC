"""Reglas de auditorías por sala. Son registros históricos: no cambian el inventario."""
from db import log

RESULTADOS = ('Encontrado', 'No encontrado', 'Novedad')


def registrar_auditoria(db, room_id, auditor, observations, form):
    """form: datos enviados (result_<id> y note_<id> por ejemplar)."""
    books_in_room = db.execute('SELECT id FROM books WHERE room_id=? AND status != ?', (room_id, 'Baja')).fetchall()
    if not db.execute('SELECT 1 FROM rooms WHERE id=?', (room_id,)).fetchone():
        raise ValueError('La sala no existe.')
    states = []
    for book in books_in_room:
        result = form.get(f'result_{book["id"]}')
        if result not in RESULTADOS: raise ValueError('Verifica todos los resultados de la auditoría.')
        note = (form.get(f'note_{book["id"]}') or '').strip()[:500]
        states.append((book['id'], result, note))
    with db:
        cur = db.execute('INSERT INTO audits(room_id,auditor,observations) VALUES (?,?,?)',
                         (room_id, auditor, observations))
        db.executemany('INSERT INTO audit_items(audit_id,book_id,result,note) VALUES (?,?,?,?)',
                       [(cur.lastrowid, *state) for state in states])
        log('Auditoría', f'Sala ID {room_id}: {len(states)} ejemplares verificados')
