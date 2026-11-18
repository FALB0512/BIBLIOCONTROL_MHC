import csv
import hashlib
import io
import os
import secrets
import sqlite3
import time
from datetime import date, datetime
from functools import wraps
from pathlib import Path

import qrcode
import qrcode.image.svg
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   Response, session, url_for)
from xml.sax.saxutils import escape

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).resolve().parent
DB = BASE / 'bibliocontrol.db'
KEYFILE = BASE / '.secret_key'
if not KEYFILE.exists():
    KEYFILE.write_text(secrets.token_hex(32), encoding='utf-8')

app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get('BIBLIO_SECRET_KEY', KEYFILE.read_text(encoding='utf-8').strip()),
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  MAX_CONTENT_LENGTH=2 * 1024 * 1024)


def connection():
    if 'db' not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=5000')
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = connection()
    db.executescript('''
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'admin'
        CHECK(role IN ('admin','bibliotecario','consulta')),
      active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS rooms (
      id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, location TEXT NOT NULL DEFAULT '',
      responsible TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS books (
      id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE,
      title TEXT NOT NULL, author TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT '',
      isbn TEXT NOT NULL DEFAULT '', publisher TEXT NOT NULL DEFAULT '',
      room_id INTEGER NOT NULL REFERENCES rooms(id),
      condition TEXT NOT NULL DEFAULT 'Bueno' CHECK(condition IN ('Bueno','Regular','Deteriorado')),
      status TEXT NOT NULL DEFAULT 'Disponible' CHECK(status IN ('Disponible','Prestado','Baja')),
      notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS loans (
      id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id),
      borrower TEXT NOT NULL, department TEXT NOT NULL DEFAULT '',
      loan_date TEXT NOT NULL, due_date TEXT NOT NULL,
      return_date TEXT, notes TEXT NOT NULL DEFAULT '',
      CHECK(return_date IS NULL OR return_date >= loan_date));
    CREATE UNIQUE INDEX IF NOT EXISTS one_active_loan ON loans(book_id) WHERE return_date IS NULL;
    CREATE TABLE IF NOT EXISTS transfers (
      id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id),
      from_room_id INTEGER NOT NULL REFERENCES rooms(id),
      to_room_id INTEGER NOT NULL REFERENCES rooms(id),
      person TEXT NOT NULL, transferred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      notes TEXT NOT NULL DEFAULT '', CHECK(from_room_id != to_room_id));
    CREATE TABLE IF NOT EXISTS audits (
      id INTEGER PRIMARY KEY, room_id INTEGER NOT NULL REFERENCES rooms(id),
      audited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      auditor TEXT NOT NULL, observations TEXT NOT NULL DEFAULT '');
    CREATE TABLE IF NOT EXISTS audit_items (
      id INTEGER PRIMARY KEY, audit_id INTEGER NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
      book_id INTEGER NOT NULL REFERENCES books(id),
      result TEXT NOT NULL CHECK(result IN ('Encontrado','No encontrado','Novedad')),
      note TEXT NOT NULL DEFAULT '', UNIQUE(audit_id,book_id));
    CREATE TABLE IF NOT EXISTS events (
      id INTEGER PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL,
      detail TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    ''')
    # Migración: bases de datos creadas antes de los roles.
    if 'role' not in [c['name'] for c in db.execute('PRAGMA table_info(users)')]:
        db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'admin' "
                   "CHECK(role IN ('admin','bibliotecario','consulta'))")
    if 'active' not in [c['name'] for c in db.execute('PRAGMA table_info(users)')]:
        db.execute('ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))')
    db.commit()


ROLES = {'admin': 'Administrador', 'bibliotecario': 'Bibliotecario', 'consulta': 'Consulta'}
WRITE_ROLES = {'admin', 'bibliotecario'}


@app.before_request
def before():
    init_db()
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    if request.method == 'POST' and not secrets.compare_digest(
            session.get('csrf', ''), request.form.get('csrf', '')):
        abort(400, 'Formulario inválido. Actualiza la página y vuelve a intentarlo.')
    allowed = {'setup', 'login', 'static'}
    endpoint = request.endpoint
    if not connection().execute('SELECT 1 FROM users LIMIT 1').fetchone():
        if endpoint not in {'setup', 'static'}:
            return redirect(url_for('setup'))
    elif endpoint not in allowed and not session.get('user_id'):
        return redirect(url_for('login'))
    if session.get('user_id'):
        current = connection().execute('SELECT role, active, password_hash FROM users WHERE id=?',
                                       (session['user_id'],)).fetchone()
        if (not current or not current['active']
                or session.get('pwh') != fingerprint(current['password_hash'])):
            session.clear()
            flash('Tu cuenta no está activa o la sesión expiró. Inicia sesión nuevamente.', 'danger')
            return redirect(url_for('login'))
        session['role'] = current['role']  # los cambios de rol aplican de inmediato
    if (request.method == 'POST' and session.get('user_id') and endpoint != 'logout'
            and session.get('role') not in WRITE_ROLES):
        flash('Tu rol de Consulta no permite modificar datos.', 'danger')
        return redirect(request.referrer or url_for('dashboard'))


@app.context_processor
def context():
    return {'csrf_token': session.get('csrf', ''), 'current_user': session.get('username'),
            'current_role': ROLES.get(session.get('role'), ''), 'is_admin': session.get('role') == 'admin',
            'today': date.today().isoformat()}


def fingerprint(password_hash):
    """Huella del hash de contraseña: si cambia, las sesiones anteriores dejan de ser válidas."""
    return hashlib.sha256(password_hash.encode()).hexdigest()


LOGIN_FAILS = {}  # usuario -> (intentos, inicio de la ventana, bloqueado hasta)
MAX_FAILS, FAIL_WINDOW, LOCK_SECONDS = 5, 900, 900


def login_blocked(username):
    entry = LOGIN_FAILS.get(username)
    return bool(entry) and entry[2] > time.time()


def register_failure(username):
    now = time.time()
    count, since, _ = LOGIN_FAILS.get(username, (0, now, 0))
    if now - since > FAIL_WINDOW:
        count, since = 0, now
    count += 1
    LOGIN_FAILS[username] = (count, since, now + LOCK_SECONDS if count >= MAX_FAILS else 0)


def safe_cell(value):
    """Evita que Excel interprete texto escrito por usuarios como fórmula."""
    if isinstance(value, str) and value[:1] in '=+-@':
        return "'" + value
    return value


def log(action, detail):
    connection().execute('INSERT INTO events(actor, action, detail) VALUES (?,?,?)',
                         (session.get('username', 'sistema'), action, detail))


def val(name, maxlen=255, required=False):
    text = (request.form.get(name) or '').strip()
    if required and not text:
        raise ValueError(f'El campo «{name}» es obligatorio.')
    if len(text) > maxlen:
        raise ValueError(f'El campo «{name}» supera {maxlen} caracteres.')
    return text


def dateval(name):
    text = val(name, 10, True)
    try:
        date.fromisoformat(text)
    except ValueError:
        raise ValueError(f'Fecha inválida: {name}')
    return text


def as_int(name):
    try:
        return int(request.form.get(name, ''))
    except (ValueError, TypeError):
        raise ValueError(f'Identificador inválido: {name}')


@app.route('/configuracion', methods=['GET', 'POST'])
def setup():
    if connection().execute('SELECT 1 FROM users LIMIT 1').fetchone():
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = val('username', 40, True)
        password = request.form.get('password', '')
        if len(password) < 10:
            flash('La contraseña debe tener al menos 10 caracteres.', 'danger')
        else:
            connection().execute("INSERT INTO users(username,password_hash,role) VALUES (?,?,'admin')",
                                 (username, generate_password_hash(password)))
            connection().commit()
            flash('Administrador creado. Inicia sesión.', 'success')
            return redirect(url_for('login'))
    return render_template('setup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = val('username', 40)
        key = username.lower()
        if login_blocked(key):
            flash('Demasiados intentos fallidos. Espera 15 minutos e inténtalo de nuevo.', 'danger')
            return render_template('login.html')
        user = connection().execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if user and user['active'] and check_password_hash(user['password_hash'], request.form.get('password', '')):
            LOGIN_FAILS.pop(key, None)
            session.clear()
            session.update(user_id=user['id'], username=user['username'], role=user['role'],
                           pwh=fingerprint(user['password_hash']), csrf=secrets.token_urlsafe(32))
            return redirect(url_for('dashboard'))
        register_failure(key)
        flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')


@app.post('/salir')
def logout():
    session.clear()
    return redirect(url_for('login'))


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


@app.route('/salas', methods=['GET', 'POST'])
def rooms():
    db = connection()
    if request.method == 'POST':
        try:
            name, location, responsible = val('name', 100, True), val('location', 150), val('responsible', 120)
            with db:
                db.execute('INSERT INTO rooms(name,location,responsible) VALUES (?,?,?)', (name, location, responsible))
                log('Sala creada', name)
            flash('Sala registrada correctamente.', 'success')
        except (ValueError, sqlite3.IntegrityError) as ex:
            flash(str(ex), 'danger')
        return redirect(url_for('rooms'))
    items = db.execute('''SELECT r.*, COUNT(b.id) total FROM rooms r
                          LEFT JOIN books b ON b.room_id=r.id GROUP BY r.id ORDER BY r.name''').fetchall()
    return render_template('rooms.html', items=items)


@app.post('/salas/<int:room_id>/editar')
def edit_room(room_id):
    db = connection()
    try:
        name, location, responsible = val('name', 100, True), val('location', 150), val('responsible', 120)
        with db:
            cur = db.execute('UPDATE rooms SET name=?,location=?,responsible=? WHERE id=?',
                             (name, location, responsible, room_id))
            if not cur.rowcount: abort(404)
            log('Sala editada', name)
        flash('Sala actualizada.', 'success')
    except (ValueError, sqlite3.IntegrityError) as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('rooms'))


@app.route('/libros', methods=['GET', 'POST'])
def books():
    db = connection()
    if request.method == 'POST':
        try:
            room_id = as_int('room_id')
            if not db.execute('SELECT 1 FROM rooms WHERE id=? AND active=1', (room_id,)).fetchone():
                raise ValueError('La sala seleccionada no existe.')
            fields = [val('code', 40, True), val('title', 200, True), val('author', 150),
                      val('category', 80), val('isbn', 30), val('publisher', 100)]
            condition, notes = val('condition', 20), val('notes', 500)
            if condition not in ('Bueno','Regular','Deteriorado'): raise ValueError('Estado físico inválido.')
            with db:
                db.execute('''INSERT INTO books(code,title,author,category,isbn,publisher,room_id,condition,notes)
                              VALUES (?,?,?,?,?,?,?,?,?)''', (*fields, room_id, condition, notes))
                log('Libro registrado', f'{fields[0]} · {fields[1]}')
            flash('Ejemplar agregado al inventario.', 'success')
        except (ValueError, sqlite3.IntegrityError) as ex:
            flash(str(ex), 'danger')
        return redirect(url_for('books'))
    q = request.args.get('q', '').strip()[:100]
    room = request.args.get('room', '').strip()
    sql = '''SELECT b.*,r.name room FROM books b JOIN rooms r ON r.id=b.room_id WHERE 1=1'''
    args = []
    if q:
        sql += ' AND (b.code LIKE ? OR b.title LIKE ? OR b.author LIKE ?)'
        args += [f'%{q}%'] * 3
    if room.isdigit():
        sql += ' AND b.room_id=?'; args.append(int(room))
    sql += ' ORDER BY b.id DESC'
    return render_template('books.html', items=db.execute(sql, args).fetchall(),
                           rooms=db.execute('SELECT * FROM rooms WHERE active=1 ORDER BY name').fetchall(), q=q, chosen_room=room)


@app.get('/libros/<int:book_id>/qr')
def book_qr(book_id):
    book = connection().execute('''SELECT b.*, r.name room FROM books b JOIN rooms r ON r.id=b.room_id
                                   WHERE b.id=?''', (book_id,)).fetchone()
    if not book: abort(404)
    svg = qrcode.make(book['code'], image_factory=qrcode.image.svg.SvgPathImage,
                      box_size=10, border=2).to_string(encoding='unicode')
    return render_template('book_qr.html', book=book, svg=svg)


@app.post('/libros/<int:book_id>/editar')
def edit_book(book_id):
    db = connection()
    try:
        fields = (val('title', 200, True), val('author', 150), val('category', 80),
                  val('isbn', 30), val('publisher', 100), val('condition', 20), val('notes', 500))
        if fields[5] not in ('Bueno','Regular','Deteriorado'): raise ValueError('Estado físico inválido.')
        with db:
            cur = db.execute('''UPDATE books SET title=?,author=?,category=?,isbn=?,publisher=?,condition=?,notes=?
                                WHERE id=?''', (*fields, book_id))
            if not cur.rowcount: abort(404)
            log('Libro editado', f'ID {book_id}: {fields[0]}')
        flash('Datos bibliográficos actualizados.', 'success')
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('books'))


@app.post('/libros/<int:book_id>/baja')
def disable_book(book_id):
    db = connection()
    try:
        with db:
            book = db.execute('SELECT * FROM books WHERE id=?', (book_id,)).fetchone()
            if not book: abort(404)
            if book['status'] == 'Prestado': raise ValueError('No se puede dar de baja un ejemplar prestado.')
            next_status = 'Disponible' if book['status'] == 'Baja' else 'Baja'
            db.execute('UPDATE books SET status=? WHERE id=?', (next_status, book_id))
            log('Cambio de estado', f"{book['code']}: {next_status}")
        flash('Estado actualizado.', 'success')
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('books'))


@app.route('/prestamos', methods=['GET', 'POST'])
def loans():
    db = connection()
    if request.method == 'POST':
        try:
            book_id = as_int('book_id')
            borrower = val('borrower', 150, True)
            department, loan_date, due_date, notes = val('department', 100), dateval('loan_date'), dateval('due_date'), val('notes', 500)
            if due_date < loan_date: raise ValueError('La fecha límite debe ser igual o posterior a la fecha del préstamo.')
            with db:
                changed = db.execute("UPDATE books SET status='Prestado' WHERE id=? AND status='Disponible'", (book_id,))
                if not changed.rowcount: raise ValueError('El ejemplar no está disponible para préstamo.')
                db.execute('''INSERT INTO loans(book_id,borrower,department,loan_date,due_date,notes)
                              VALUES (?,?,?,?,?,?)''', (book_id, borrower, department, loan_date, due_date, notes))
                log('Préstamo', f'Ejemplar ID {book_id} entregado a {borrower}')
            flash('Préstamo registrado.', 'success')
        except (ValueError, sqlite3.IntegrityError) as ex:
            flash(str(ex), 'danger')
        return redirect(url_for('loans'))
    items = db.execute('''SELECT l.*, b.code, b.title, r.name room FROM loans l
                           JOIN books b ON b.id=l.book_id JOIN rooms r ON r.id=b.room_id
                           ORDER BY (l.return_date IS NULL) DESC, l.id DESC''').fetchall()
    available = db.execute("SELECT id,code,title FROM books WHERE status='Disponible' ORDER BY title").fetchall()
    return render_template('loans.html', items=items, available=available)


@app.post('/prestamos/<int:loan_id>/devolver')
def return_book(loan_id):
    db = connection()
    try:
        returned = dateval('return_date')
        with db:
            loan = db.execute('SELECT * FROM loans WHERE id=? AND return_date IS NULL', (loan_id,)).fetchone()
            if not loan: raise ValueError('El préstamo ya fue devuelto o no existe.')
            if returned < loan['loan_date']: raise ValueError('La devolución no puede ser anterior al préstamo.')
            db.execute('UPDATE loans SET return_date=? WHERE id=?', (returned, loan_id))
            db.execute("UPDATE books SET status='Disponible' WHERE id=?", (loan['book_id'],))
            log('Devolución', f'Préstamo ID {loan_id} · ejemplar ID {loan["book_id"]}')
        flash('Devolución registrada.', 'success')
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('loans'))


@app.route('/traslados', methods=['GET','POST'])
def transfers():
    db = connection()
    if request.method == 'POST':
        try:
            book_id, to_room = as_int('book_id'), as_int('to_room_id')
            person, notes = val('person', 150, True), val('notes', 500)
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
            flash('Traslado registrado.', 'success')
        except ValueError as ex:
            flash(str(ex), 'danger')
        return redirect(url_for('transfers'))
    items = db.execute('''SELECT t.*,b.code,b.title, a.name source, z.name destination
                           FROM transfers t JOIN books b ON b.id=t.book_id
                           JOIN rooms a ON a.id=t.from_room_id JOIN rooms z ON z.id=t.to_room_id
                           ORDER BY t.id DESC''').fetchall()
    available = db.execute("SELECT id,code,title,room_id FROM books WHERE status='Disponible' ORDER BY title").fetchall()
    rooms_list = db.execute('SELECT id,name FROM rooms WHERE active=1 ORDER BY name').fetchall()
    return render_template('transfers.html', items=items, available=available, rooms=rooms_list)


@app.route('/auditorias', methods=['GET','POST'])
def audits():
    db = connection()
    if request.method == 'POST':
        try:
            room_id, auditor, observations = as_int('room_id'), val('auditor', 150, True), val('observations', 1000)
            books_in_room = db.execute('SELECT id FROM books WHERE room_id=? AND status != ?', (room_id, 'Baja')).fetchall()
            if not db.execute('SELECT 1 FROM rooms WHERE id=?', (room_id,)).fetchone():
                raise ValueError('La sala no existe.')
            states = []
            for book in books_in_room:
                result = request.form.get(f'result_{book["id"]}')
                if result not in ('Encontrado','No encontrado','Novedad'):
                    raise ValueError('Verifica todos los resultados de la auditoría.')
                note = (request.form.get(f'note_{book["id"]}') or '').strip()[:500]
                states.append((book['id'],result,note))
            with db:
                cur = db.execute('INSERT INTO audits(room_id,auditor,observations) VALUES (?,?,?)',
                                 (room_id, auditor, observations))
                db.executemany('''INSERT INTO audit_items(audit_id,book_id,result,note) VALUES (?,?,?,?)''',
                               [(cur.lastrowid, *state) for state in states])
                log('Auditoría', f'Sala ID {room_id}: {len(states)} ejemplares verificados')
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


EXPORTS = {
    'inventario': ('''SELECT b.code codigo, b.title titulo, b.author autor, b.category categoria,
                       b.isbn isbn, r.name sala, b.condition estado_fisico, b.status disponibilidad,
                       b.notes observaciones FROM books b JOIN rooms r ON r.id=b.room_id ORDER BY r.name,b.code''', 'inventario'),
    'prestamos': ('''SELECT b.code codigo, b.title titulo, l.borrower prestatario, l.department dependencia,
                      l.loan_date fecha_prestamo, l.due_date fecha_limite, l.return_date fecha_devolucion,
                      l.notes observaciones FROM loans l JOIN books b ON b.id=l.book_id ORDER BY l.id DESC''', 'prestamos'),
    'traslados': ('''SELECT b.code codigo, a.name sala_origen, z.name sala_destino, t.person responsable,
                       t.transferred_at fecha, t.notes observaciones FROM transfers t
                       JOIN books b ON b.id=t.book_id JOIN rooms a ON a.id=t.from_room_id
                       JOIN rooms z ON z.id=t.to_room_id ORDER BY t.id DESC''', 'traslados'),
    'auditorias': ('''SELECT a.id auditoria, r.name sala, a.audited_at fecha, a.auditor auditor,
                        b.code codigo, b.title titulo, i.result resultado, i.note detalle
                        FROM audit_items i JOIN audits a ON a.id=i.audit_id
                        JOIN rooms r ON r.id=a.room_id JOIN books b ON b.id=i.book_id
                        ORDER BY a.id DESC,b.code''', 'auditorias')
}


@app.route('/reportes')
def reports():
    return render_template('reports.html')


@app.route('/reportes/<kind>.csv')
def download_csv(kind):
    if kind not in EXPORTS: abort(404)
    query, filename = EXPORTS[kind]
    cur = connection().execute(query)
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    writer.writerow([x[0] for x in cur.description])
    writer.writerows([[safe_cell(v) for v in row] for row in cur.fetchall()])
    return Response(output.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename={filename}_{date.today().isoformat()}.csv'})


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Solo un Administrador puede gestionar usuarios.', 'danger')
            return redirect(url_for('dashboard'))
        return view(*args, **kwargs)
    return wrapper


def other_active_admins(user_id):
    return connection().execute("SELECT count(*) FROM users WHERE role='admin' AND active=1 AND id<>?",
                                (user_id,)).fetchone()[0]


@app.route('/usuarios')
@admin_required
def users():
    items = connection().execute('SELECT id, username, role, active, created_at FROM users ORDER BY username').fetchall()
    return render_template('usuarios.html', items=items, roles=ROLES, me=session['user_id'])


@app.post('/usuarios/nuevo')
@admin_required
def create_user():
    db = connection()
    try:
        username, role = val('username', 40, True), val('role', 20, True)
        password = request.form.get('password', '')
        if role not in ROLES: raise ValueError('Rol inválido.')
        if len(password) < 10: raise ValueError('La contraseña debe tener al menos 10 caracteres.')
        with db:
            db.execute('INSERT INTO users(username,password_hash,role) VALUES (?,?,?)',
                       (username, generate_password_hash(password), role))
            log('Usuario creado', f'{username} · {ROLES[role]}')
        flash('Usuario creado.', 'success')
    except (ValueError, sqlite3.IntegrityError) as ex:
        flash('Ese nombre de usuario ya existe.' if isinstance(ex, sqlite3.IntegrityError) else str(ex), 'danger')
    return redirect(url_for('users'))


@app.post('/usuarios/<int:user_id>/rol')
@admin_required
def change_role(user_id):
    db = connection()
    user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not user: abort(404)
    try:
        role = val('role', 20, True)
        if role not in ROLES: raise ValueError('Rol inválido.')
        if user_id == session['user_id']: raise ValueError('No puedes cambiar tu propio rol.')
        if user['role'] == 'admin' and role != 'admin' and not other_active_admins(user_id):
            raise ValueError('Debe quedar al menos un Administrador activo.')
        with db:
            db.execute('UPDATE users SET role=? WHERE id=?', (role, user_id))
            log('Rol cambiado', f"{user['username']}: {ROLES[role]}")
        flash('Rol actualizado.', 'success')
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('users'))


@app.post('/usuarios/<int:user_id>/estado')
@admin_required
def toggle_user(user_id):
    db = connection()
    user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not user: abort(404)
    try:
        if user_id == session['user_id']: raise ValueError('No puedes desactivar tu propia cuenta.')
        if user['active'] and user['role'] == 'admin' and not other_active_admins(user_id):
            raise ValueError('Debe quedar al menos un Administrador activo.')
        new_state = 0 if user['active'] else 1
        with db:
            db.execute('UPDATE users SET active=? WHERE id=?', (new_state, user_id))
            log('Estado de usuario', f"{user['username']}: {'activo' if new_state else 'inactivo'}")
        flash('Estado actualizado.', 'success')
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('users'))


@app.post('/usuarios/<int:user_id>/clave')
@admin_required
def reset_password(user_id):
    db = connection()
    user = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not user: abort(404)
    try:
        password = request.form.get('password', '')
        if len(password) < 10: raise ValueError('La contraseña debe tener al menos 10 caracteres.')
        new_hash = generate_password_hash(password)
        with db:
            db.execute('UPDATE users SET password_hash=? WHERE id=?', (new_hash, user_id))
            log('Contraseña restablecida', user['username'])
        if user_id == session['user_id']:
            session['pwh'] = fingerprint(new_hash)  # mantiene la sesión propia tras cambiar su clave
        flash('Contraseña actualizada. Las sesiones abiertas de esa cuenta se cerrarán.', 'success')
    except ValueError as ex:
        flash(str(ex), 'danger')
    return redirect(url_for('users'))


@app.route('/reportes/<kind>.xlsx')
def download_xlsx(kind):
    if kind not in EXPORTS: abort(404)
    query, filename = EXPORTS[kind]
    cur = connection().execute(query)
    headers = [x[0] for x in cur.description]
    wb = Workbook()
    ws = wb.active
    ws.title = filename
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='C61827')
    for row in cur.fetchall():
        ws.append(list(row))
        for cell in ws[ws.max_row]:
            # Texto que empiece por = + - @ se guarda como texto, no como fórmula.
            if isinstance(cell.value, str) and cell.value[:1] in '=+-@':
                cell.data_type = 's'
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    for idx, title in enumerate(headers, 1):
        longest = max([len(str(title))] + [len(str(ws.cell(r, idx).value or '')) for r in range(2, min(ws.max_row, 300) + 1)])
        ws.column_dimensions[get_column_letter(idx)].width = min(max(longest + 2, 10), 50)
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(),
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f'attachment; filename={filename}_{date.today().isoformat()}.xlsx'})


@app.route('/reportes/<kind>.pdf')
def download_pdf(kind):
    if kind not in EXPORTS: abort(404)
    query, filename = EXPORTS[kind]
    cur = connection().execute(query)
    headers = [x[0] for x in cur.description]
    rows = cur.fetchall()
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle('cell', parent=styles['Normal'], fontSize=7.5, leading=9)
    head_style = ParagraphStyle('head', parent=cell_style, fontName='Helvetica-Bold', textColor=colors.white)
    text = lambda value: escape('' if value is None else str(value))
    story = [RLImage(str(BASE / 'static' / 'img' / 'logo.jpg'), width=120, height=120 * 96 / 255),
             Spacer(1, 8),
             Paragraph(f'Reporte: {text(filename.capitalize())}', styles['Heading2']),
             Paragraph(f'Generado el {date.today().isoformat()} · {len(rows)} registros', cell_style),
             Spacer(1, 10)]
    if rows:
        data = [[Paragraph(text(h), head_style) for h in headers]]
        data += [[Paragraph(text(v), cell_style) for v in row] for row in rows]
        width = (landscape(A4)[0] - 56) / len(headers)
        table = Table(data, colWidths=[width] * len(headers), repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#C61827')),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#BDBDBD')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F6F6F6')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story.append(table)
    else:
        story.append(Paragraph('Sin registros.', cell_style))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=28, rightMargin=28,
                            topMargin=28, bottomMargin=28, title=f'Reporte {filename}', author='BIBLIOCONTROL MHC')
    doc.build(story)
    return Response(buf.getvalue(), mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename={filename}_{date.today().isoformat()}.pdf'})


@app.route('/actividad')
def activity():
    items = connection().execute('SELECT * FROM events ORDER BY id DESC LIMIT 300').fetchall()
    return render_template('activity.html', items=items)


if __name__ == '__main__':
    with app.app_context(): init_db()
    app.run(host='127.0.0.1', port=5000, debug=False)
