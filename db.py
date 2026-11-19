import sqlite3

from flask import g, session

from core import DB, app


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
    CREATE TABLE IF NOT EXISTS areas (
      id INTEGER PRIMARY KEY, code INTEGER NOT NULL UNIQUE CHECK(code BETWEEN 100 AND 2000),
      name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS doc_types (code TEXT PRIMARY KEY, name TEXT NOT NULL);
    INSERT OR IGNORE INTO doc_types(code,name) VALUES
      ('L','Libro'),('N','Norma'),('DT','Documento técnico'),('DI','Diccionario'),
      ('M','Manual'),('RE','Revista'),('G','Guía'),('CA','Catálogo');
    CREATE TABLE IF NOT EXISTS bajas (
      id INTEGER PRIMARY KEY, book_id INTEGER REFERENCES books(id),
      code TEXT NOT NULL, title TEXT NOT NULL, author TEXT NOT NULL DEFAULT '',
      category TEXT NOT NULL DEFAULT '', isbn TEXT NOT NULL DEFAULT '', publisher TEXT NOT NULL DEFAULT '',
      condition TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
      room_id INTEGER NOT NULL REFERENCES rooms(id), room_name TEXT NOT NULL,
      motivo TEXT NOT NULL, responsable TEXT NOT NULL,
      fecha_baja TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reactivado_en TEXT);
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
    existing = [c['name'] for c in db.execute('PRAGMA table_info(books)')]
    for column, ddl in [('area_id', 'INTEGER REFERENCES areas(id)'), ('doc_type', 'TEXT REFERENCES doc_types(code)'),
                        ('seq', 'INTEGER')]:
        if column not in existing:
            db.execute(f'ALTER TABLE books ADD COLUMN {column} {ddl}')
    db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS book_identifier ON books(area_id, doc_type, seq)
                  WHERE area_id IS NOT NULL''')
    # Bajas hechas antes del archivo de bajas: se registran con los datos disponibles.
    db.execute('''INSERT INTO bajas(book_id,code,title,author,category,isbn,publisher,condition,notes,
                  room_id,room_name,motivo,responsable)
                  SELECT b.id,b.code,b.title,b.author,b.category,b.isbn,b.publisher,b.condition,b.notes,
                         b.room_id,r.name,'Baja anterior al archivo de bajas (motivo no registrado)','No registrado'
                  FROM books b JOIN rooms r ON r.id=b.room_id
                  WHERE b.status='Baja' AND NOT EXISTS (SELECT 1 FROM bajas x WHERE x.book_id=b.id)''')
    db.commit()


def log(action, detail):
    connection().execute('INSERT INTO events(actor, action, detail) VALUES (?,?,?)',
                         (session.get('username', 'sistema'), action, detail))
