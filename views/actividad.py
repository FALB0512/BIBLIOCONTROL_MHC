from flask import render_template

from core import app
from db import connection


@app.route('/actividad')
def activity():
    items = connection().execute('SELECT * FROM events ORDER BY id DESC LIMIT 300').fetchall()
    return render_template('activity.html', items=items)
