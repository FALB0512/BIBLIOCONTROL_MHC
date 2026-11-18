from flask import abort, flash, redirect, render_template, request, url_for

from core import app
from db import connection
from services.auditorias import registrar_auditoria
from validators import as_int, val


@app.route('/auditorias', methods=['GET', 'POST'])
def audits():
    db = connection()
    if request.method == 'POST':
        try:
            room_id, auditor, observations = as_int('room_id'), val('auditor', 150, True), val('observations', 1000)
            registrar_auditoria(db, room_id, auditor, observations, request.form)
            flash('Auditoría guardada. Es un registro histórico: no modifica automáticamente el inventario.', 'success')
        except ValueError as ex:
            flash(str(ex), 'danger')
        return redirect(url_for('audits'))
    room_id = request.args.get('room', '')
    rooms_list = db.execute('SELECT * FROM rooms WHERE active=1 ORDER BY name').fetchall()
    selected = int(room_id) if room_id.isdigit() else None
    books_in_room = db.execute("SELECT * FROM books WHERE room_id=? AND status!='Baja' ORDER BY code", (selected,)).fetchall() if selected else []
    history = db.execute('''SELECT a.*,r.name room,
                           (SELECT COUNT(*) FROM audit_items i WHERE i.audit_id=a.id AND result='No encontrado') missing,
                           (SELECT COUNT(*) FROM audit_items i WHERE i.audit_id=a.id AND result='Novedad') issues,
                           (SELECT COUNT(*) FROM audit_items i WHERE i.audit_id=a.id) total
                           FROM audits a JOIN rooms r ON r.id=a.room_id ORDER BY a.id DESC''').fetchall()
    return render_template('audits.html', rooms=rooms_list, selected=selected, books=books_in_room, history=history)


@app.route('/auditorias/<int:audit_id>')
def audit_detail(audit_id):
    db = connection()
    audit = db.execute('SELECT a.*,r.name room FROM audits a JOIN rooms r ON r.id=a.room_id WHERE a.id=?', (audit_id,)).fetchone()
    if not audit: abort(404)
    items = db.execute('''SELECT i.*,b.code,b.title FROM audit_items i
                          JOIN books b ON b.id=i.book_id WHERE i.audit_id=? ORDER BY b.code''',(audit_id,)).fetchall()
    return render_template('audit_detail.html', audit=audit, items=items)
