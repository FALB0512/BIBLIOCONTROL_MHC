


def safe_cell(value):
    """Evita que Excel interprete texto escrito por usuarios como fórmula."""
    if isinstance(value, str) and value and value[0] in '=+-@':
        return "'" + value
    return value


EXPORTS = {
    'inventario': ('''SELECT b.code codigo, b.title titulo, b.author autor, b.category categoria,
                       b.isbn isbn, r.name sala, b.condition estado_fisico, b.status disponibilidad,
                       b.notes observaciones,
                       a.code area_codigo, b.doc_type tipo_documento, b.seq consecutivo
                       FROM books b JOIN rooms r ON r.id=b.room_id LEFT JOIN areas a ON a.id=b.area_id
                       ORDER BY r.name,b.code''', 'inventario'),
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
