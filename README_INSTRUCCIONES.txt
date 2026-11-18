BIBLIOCONTROL MHC | Versión inicial funcional 1.0
==============================================

TECNOLOGÍA
Python 3.10 o superior, Flask 3.x y SQLite (integrado en Python).
No requiere servicios externos ni servidor de base de datos.

PUESTA EN MARCHA EN TU PC PERSONAL (WINDOWS)
1. Descomprime todo el ZIP en una carpeta de tu computador personal.
2. Instala Python 3 desde python.org si todavía no lo tienes. Activa PATH.
3. Haz doble clic en INICIAR_WINDOWS.bat; creará el entorno virtual e instalará Flask.
4. Abre http://127.0.0.1:5000 en el navegador.
5. En el primer inicio, crea tu usuario administrador (contraseña >=10 caracteres).
6. Registra primero las salas y después los ejemplares.
7. Para detener el servidor presiona Ctrl+C en la ventana negra.

FORMA MANUAL (WINDOWS / MAC / LINUX)
python -m venv .venv
Windows: .venv\Scripts\activate
macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py

MÓDULOS OPERATIVOS
- Acceso con contraseña cifrada mediante hash, configuración inicial.
- Panel con indicadores generales y préstamos vencidos.
- Salas de reunión: crear, actualizar y activar/desactivar (solo si no tienen ejemplares).
- Inventario: registrar, consultar, editar, dar de baja o reactivar.
- Préstamos: registrar y devolver; no permite doble préstamo.
- Traslados: registra origen, destino y responsable; bloquea ejemplares no disponibles.
- Auditorías: verificación por sala con resultados encontrados, faltantes y novedades.
- Reportes en XLSX y PDF, y CSV compatibles con Excel: inventario, préstamos, traslados y auditorías.
- Historial básico de operaciones.
- Usuarios con roles: Administrador (gestiona usuarios), Bibliotecario (opera) y Consulta (solo lectura).
- Etiquetas QR por ejemplar, imprimibles desde el inventario.

IMPORTANTE
- La base de datos bibliocontrol.db se crea automáticamente junto a app.py.
- Haz copia de bibliocontrol.db CON EL SERVIDOR DETENIDO y guárdala en un lugar seguro.
- La clave secreta de sesión se guarda en .secret_key. No la compartas.
- No almacenes contraseñas en hojas de cálculo ni publiques el proyecto con datos reales.
- Servidor configurado únicamente para 127.0.0.1:5000, es decir, acceso local.
- No publiques el servidor Flask directamente en Internet ni en la red corporativa.
- Para uso empresarial multiusuario se requiere revisión de TI, despliegue con servidor
  WSGI, control de acceso, copias de seguridad programadas y evaluación de SQLite.
- Los permisos por rol se validan en el servidor; Consulta no puede modificar datos.
- Los registros de auditoría NO alteran automáticamente el estado de los libros.
- Se trabaja por EJEMPLAR, no por título: cada copia tiene código único.
- Las fechas de vencimiento se comparan con la fecha local de la máquina.
- Para incorporar documentos confidenciales o nombres reales, solicita autorización.

SIGUIENTE VERSIÓN PROPUESTA
Historial de cambios detallado, impresión de actas, respaldo automatizado,
exportaciones filtradas y despliegue controlado por TI.
