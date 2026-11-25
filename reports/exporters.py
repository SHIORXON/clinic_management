import io
import os
from datetime import datetime

from django.http import HttpResponse

XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def to_xlsx(title, cols, rows, summary, subtitle=""):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append([title])
    ws["A1"].font = Font(bold=True, size=14, color="132A2E")
    ws.append([subtitle])
    ws.append([])
    head_row = 4
    ws.append([h for _, h in cols])
    for c in ws[head_row]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="132A2E")
        c.alignment = Alignment(vertical="center", wrap_text=True)
    for r in rows:
        ws.append([_safe(r.get(k, "")) for k, _ in cols])
    ws.append([])
    for k, v in summary.items():
        ws.append([k, v])
        ws.cell(ws.max_row, 1).font = Font(bold=True)
    for i, (k, h) in enumerate(cols, 1):
        width = max([len(h)] + [len(str(r.get(k, ""))) for r in rows[:500]]) + 2
        ws.column_dimensions[get_column_letter(i)].width = min(max(width, 10), 50)
    ws.freeze_panes = ws.cell(head_row + 1, 1)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _safe(v):
    # Excel formulasi sifatida bajarilmasligi uchun (CSV/formula injection)
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") and len(v) > 1 and v != "-":
        return "'" + v
    return v


_FONT = None


def _register_font():
    global _FONT
    if _FONT:
        return _FONT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pairs = [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    for reg, bold in pairs:
        if os.path.exists(reg) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("AppFont", reg))
            pdfmetrics.registerFont(TTFont("AppFont-Bold", bold))
            _FONT = ("AppFont", "AppFont-Bold")
            return _FONT
    _FONT = ("Helvetica", "Helvetica-Bold")
    return _FONT


def to_pdf(title, cols, rows, summary, subtitle=""):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    reg, bold = _register_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24, title=title)
    h1 = ParagraphStyle("h1", fontName=bold, fontSize=15, textColor=colors.HexColor("#132A2E"), spaceAfter=4)
    sub = ParagraphStyle("sub", fontName=reg, fontSize=9, textColor=colors.HexColor("#555555"), spaceAfter=8)
    cell = ParagraphStyle("cell", fontName=reg, fontSize=8, leading=10)
    head = ParagraphStyle("head", fontName=bold, fontSize=8, leading=10, textColor=colors.white)
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    data = [[Paragraph(esc(h), head) for _, h in cols]]
    for r in rows:
        data.append([Paragraph(esc(r.get(k, "")), cell) for k, _ in cols])
    if not rows:
        data.append([Paragraph("Ma'lumot topilmadi", cell)] + [""] * (len(cols) - 1))
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#132A2E")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F2EB")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8D2C4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    summ = "   |   ".join(f"{k}: {v}" for k, v in summary.items())
    doc.build([
        Paragraph(esc(title), h1), Paragraph(esc(subtitle), sub), t, Spacer(1, 10),
        Paragraph(esc(summ), ParagraphStyle("s", fontName=bold, fontSize=9)),
        Paragraph("Yaratildi: " + datetime.now().strftime("%d.%m.%Y %H:%M"), sub),
    ])
    return buf.getvalue()


def export_response(kind, fmt, title, cols, rows, summary, subtitle):
    name = f"hisobot_{kind}_{datetime.now():%Y%m%d}"
    if fmt == "xlsx":
        resp = HttpResponse(to_xlsx(title, cols, rows, summary, subtitle), content_type=XLSX_CT)
    else:
        resp = HttpResponse(to_pdf(title, cols, rows, summary, subtitle), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{name}.{fmt}"'
    return resp
