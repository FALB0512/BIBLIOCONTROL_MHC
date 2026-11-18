from datetime import date

from flask import render_template

from core import app
from db import connection


@app.route('/')
def dashboard():
    db = connection()
    metrics = dict(rooms=db.execute('SELECT count(*) FROM rooms WHERE active=1').fetchone()[0],
                   total=db.execute('SELECT count(*) FROM books').fetchone()[0],
                   available=db.execute("SELECT count(*) FROM books WHERE status='Disponible'").fetchone()[0],
                   loaned=db.execute("SELECT count(*) FROM books WHERE status='Prestado'").fetchone()[0],
                   overdue=db.execute('SELECT count(*) FROM loans WHERE return_date IS NULL AND due_date < ?',
                                      (date.today().isoformat(),)).fetchone()[0])
    per_room = db.execute('''SELECT r.name, count(b.id) total,
       sum(CASE WHEN b.status='Disponible' THEN 1 ELSE 0 END) available
       FROM rooms r LEFT JOIN books b ON b.room_id=r.id WHERE r.active=1
       GROUP BY r.id ORDER BY r.name''').fetchall()
    recent = db.execute('''SELECT e.* FROM events e ORDER BY id DESC LIMIT 8''').fetchall()
    return render_template('dashboard.html', metrics=metrics, per_room=per_room, recent=recent)
