# pdf_utils.py
# Build branded PDF using ReportLab; charts passed in as PNG bytes
from __future__ import annotations
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import inch

from calculations import cad

ALBA_BLUE = colors.HexColor("#1E4B87")
ALBA_TEXT = colors.HexColor("#0F2544")
ALBA_SOFT = colors.HexColor("#F6FAFF")
ALBA_BORDER = colors.HexColor("#E5ECF6")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="HeadingBrand", parent=styles["Heading1"], textColor=ALBA_TEXT, spaceAfter=6))
styles.add(ParagraphStyle(name="Muted", parent=styles["Normal"], textColor=colors.HexColor("#6B7280")))

def _boxed_table(rows, col_widths=None):
    t = Table(rows, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, ALBA_BORDER),
        ("BACKGROUND", (0,0), (-1,0), ALBA_SOFT),
        ("TEXTCOLOR", (0,0), (-1,0), ALBA_TEXT),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BOTTOMPADDING", (0,0), (-1,0), 6),
    ]))
    return t

def build_pdf(buffer, logo_path, as_of, prop_name, prop_addr, kpis, pl_rows, charts):
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story = []
    # Header
    row = []
    try:
        if logo_path:
            logo = Image(logo_path, width=120, height=120*0.33)
            row = [[logo, Paragraph("<b>ALBA Property Management</b><br/>Pricing & Profit Summary", styles["HeadingBrand"])]]
            story.append(Table(row, colWidths=[120, doc.width-120]))
        else:
            story.append(Paragraph("ALBA Property Management — Pricing & Profit Summary", styles["HeadingBrand"]))
    except Exception:
        story.append(Paragraph("ALBA Property Management — Pricing & Profit Summary", styles["HeadingBrand"]))
    story.append(Paragraph(f"{prop_name} — {prop_addr}", styles["Muted"]))
    story.append(Paragraph(f"As of: {as_of}", styles["Muted"]))
    # brand bar
    story.append(Table([[Paragraph("")]], colWidths=[doc.width], rowHeights=[3],
                       style=[("BACKGROUND", (0,0), (-1,-1), ALBA_BLUE)]))
    story.append(Spacer(1, 8))

    # KPI box
    story.append(Paragraph("Key Metrics", styles["Heading2"]))
    story.append(_boxed_table([["Metric", "Value"]] + kpis, col_widths=[240, 240]))
    story.append(Spacer(1, 8))

    # P&L
    story.append(Paragraph("Profit & Loss (Monthly vs Annual)", styles["Heading2"]))
    story.append(_boxed_table([["Line item", "Monthly", "Annual"]] + pl_rows, col_widths=[220, 130, 130]))
    story.append(Spacer(1, 8))

    # Charts
    if charts:
        from reportlab.platypus import Image as RLImage
        import io
        imgs = []
        for key in ["expense_donut.png", "profit_projection.png"]:
            if key in charts:
                bio = io.BytesIO(charts[key])
                im = RLImage(bio)
                im._restrictSize(doc.width/2-6, doc.width/2-6)
                imgs.append(im)
        if imgs:
            if len(imgs) == 1:
                story.append(imgs[0])
            else:
                story.append(Table([[imgs[0], imgs[1]]], colWidths=[doc.width/2-6, doc.width/2-6]))
            story.append(Spacer(1, 6))

    story.append(Paragraph("HST (13%) is shown separately and excluded from profit/margin (pass-through).", styles["Muted"]))
    doc.build(story)
    buffer.seek(0)
