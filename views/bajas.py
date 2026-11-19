from flask import render_template, request

from core import app
from db import connection


@app.route('/bajas')
def bajas():
    db = connection()
    groups = {}
    for row in db.execute('SELECT * FROM bajas ORDER BY room_name, fecha_baja DESC, id DESC').fetchall():
        groups.setdefault((row['room_id'], row['room_name']), []).append(row)
    return render_template('bajas.html', groups=groups,
                           rooms=db.execute('SELECT id,name FROM rooms ORDER BY name').fetchall())
