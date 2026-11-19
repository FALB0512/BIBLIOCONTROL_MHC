from flask import render_template, request

from core import app
from db import connection


@app.route('/bajas')
def bajas():
    db = connection()
    sala = request.args.get('sala', '').strip()
    sql, args = 'SELECT * FROM bajas', []
    if sala.isdigit():
        sql += ' WHERE room_id=?'
        args.append(int(sala))
    sql += ' ORDER BY room_name, fecha_baja DESC, id DESC'
    groups = {}
    for row in db.execute(sql, args).fetchall():
        groups.setdefault(row['room_name'], []).append(row)
    return render_template('bajas.html', groups=groups, chosen=sala,
                           rooms=db.execute('SELECT id,name FROM rooms ORDER BY name').fetchall())
