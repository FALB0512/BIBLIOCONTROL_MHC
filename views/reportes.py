import csv
import io
from datetime import date
from xml.sax.saxutils import escape

from flask import Response, abort, render_template
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core import BASE, app
from db import connection
from exports import EXPORTS, safe_cell


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
