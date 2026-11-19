"""Resumen de un ejemplar que se codifica en su etiqueta QR (se lee con cualquier lector de códigos)."""

MAX_CARACTERES = 900


def construir_resumen(datos):
    """datos: dict con los campos del ejemplar (código, título, autor, ...)."""
    lineas = [f"MHC {datos['code']}", f"Título: {datos['title']}"]
    campos = [('Autor', 'author'), ('ISBN', 'isbn'), ('Editorial', 'publisher'), ('Categoría', 'category'),
              ('Sala', 'room'), ('Estado físico', 'condition'), ('Observaciones', 'notes')]
    for etiqueta, clave in campos:
        valor = (datos.get(clave) or '').strip()
        if valor:
            lineas.append(f'{etiqueta}: {valor}')
    return '\n'.join(lineas)[:MAX_CARACTERES]
