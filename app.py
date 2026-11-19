"""Punto de entrada de BIBLIOCONTROL MHC."""
from core import app  # noqa: F401
import hooks  # noqa: F401  registra revisiones de sesión y permisos
import views.acceso, views.panel, views.salas, views.areas  # noqa: F401
import views.inventario, views.prestamos, views.traslados, views.auditorias  # noqa: F401
import views.reportes, views.usuarios, views.actividad, views.bajas  # noqa: F401
from db import init_db


if __name__ == '__main__':
    with app.app_context(): init_db()
    app.run(host='127.0.0.1', port=5000, debug=False)
