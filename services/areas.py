"""Reglas de áreas y del identificador de ejemplares (área, tipo y consecutivo)."""
from db import log


def identifier_parts(db, area_id, doc_type):
    """Valida área activa y tipo; devuelve el código numérico del área."""
    area = db.execute('SELECT code FROM areas WHERE id=? AND active=1', (area_id,)).fetchone()
    if not area: raise ValueError('Selecciona un área activa.')
    if not db.execute('SELECT 1 FROM doc_types WHERE code=?', (doc_type,)).fetchone():
        raise ValueError('Tipo de documento inválido.')
    return area['code']


def next_identifier(db, area_id, doc_type, room_id):
    """Número libre de la misma sala (liberado por una baja) o, si no hay, el siguiente general."""
    area_code = identifier_parts(db, area_id, doc_type)
    libre = db.execute("""SELECT MIN(b.seq) FROM books b
                          WHERE b.area_id=? AND b.doc_type=? AND b.room_id=? AND b.status='Baja'
                          AND b.seq NOT IN (SELECT seq FROM books
                                            WHERE area_id=? AND doc_type=? AND status!='Baja')""",
                       (area_id, doc_type, room_id, area_id, doc_type)).fetchone()[0]
    seq = libre or db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM books WHERE area_id=? AND doc_type=?',
                              (area_id, doc_type)).fetchone()[0]
    return f'{area_code} {doc_type}-{seq:03d}', seq


def crear_area(db, code, name):
    if not 100 <= code <= 2000: raise ValueError('El código de área debe estar entre 100 y 2000.')
    with db:
        db.execute('INSERT INTO areas(code,name) VALUES (?,?)', (code, name))
        log('Área creada', f'{code} · {name}')


def cambiar_estado_area(db, area_id):
    area = db.execute('SELECT * FROM areas WHERE id=?', (area_id,)).fetchone()
    if not area: raise LookupError('Área no encontrada.')
    new_state = 0 if area['active'] else 1
    with db:
        db.execute('UPDATE areas SET active=? WHERE id=?', (new_state, area_id))
        log('Estado de área', f"{area['code']}: {'activa' if new_state else 'inactiva'}")
    return new_state
