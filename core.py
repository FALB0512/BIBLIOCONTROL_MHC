import os
import secrets
from pathlib import Path

from flask import Flask


BASE = Path(__file__).resolve().parent
DB = BASE / 'bibliocontrol.db'
KEYFILE = BASE / '.secret_key'
if not KEYFILE.exists():
    KEYFILE.write_text(secrets.token_hex(32), encoding='utf-8')

app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get('BIBLIO_SECRET_KEY', KEYFILE.read_text(encoding='utf-8').strip()),
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  MAX_CONTENT_LENGTH=2 * 1024 * 1024)


ROLES = {'admin': 'Administrador', 'bibliotecario': 'Bibliotecario', 'consulta': 'Consulta'}
WRITE_ROLES = {'admin', 'bibliotecario'}
# Acciones de escritura que solo puede hacer el Administrador (el Bibliotecario las tiene prohibidas).
# Se identifican por el nombre de la función de la ruta.
ADMIN_ONLY_POST = {
    'books', 'disable_book',                                  # alta de ejemplares y bajas
    'rooms', 'toggle_room', 'delete_room',                    # salas: crear, desactivar, eliminar
    'areas', 'toggle_area', 'delete_area', 'create_type',     # áreas y tipos: crear, desactivar, eliminar
}
