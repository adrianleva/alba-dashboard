# streamlit_app.py — ALBA Pricing & Profit Planner (final)
# - Poppins font, ALBA blue headings, soft card UI
# - Mode toggle: Target Margin → Fee OR Fee → Margin
# - Manager salary prorated by 1–5 days/week
# - HST fixed at 13% (Ontario)
# - Big KPIs, readable charts, real PDF export (ReportLab + Plotly/Kaleido)

from __future__ import annotations
from datetime import datetime
from io import BytesIO
import os

import streamlit as st
import plotly.graph_objects as go

# PDF bits
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors

# ──────────────────────────────────────────────────────────────────────────────
# Page + Brand theme
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="ALBA Pricing & Profit Planner", page_icon="🏢", layout="wide")

BRAND_BLUE = "#1E4B87"
BRAND_TEXT = "#0F2544"
CARD_BG = "#FFFFFF"
CARD_SOFT = "#F6FAFF"
CARD_BORDER = "#E5ECF6"

st.markdown(
    f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap');

      :root {{ color-scheme: light !important; }}

      html, body, [data-testid="stAppViewContainer"] {{
        background:#FFFFFF !important;
        color:{BRAND_TEXT} !important;
        font-family:Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif !important;
      }}
      [data-testid="stHeader"] {{ background:#FFFFFF !important; border-bottom:none !important; }}

      /* Headings */
      h1, h2, h3, h4, h5, h6, label, .stMarkdown p, .stCaption {{ color:{BRAND_TEXT} !important; }}
      .brand-title {{ color:{BRAND_TEXT}; font-weight:800; font-size:30px; margin:2px 0 0; }}
      .brand-bar {{ height:5px; background:{BRAND_BLUE}; margin:8px 0 16px; border-radius:8px; }}
      .section-title {{ color:{BRAND_BLUE}; font-weight:800; margin:12px 0 8px; font-size:18px; }}
      .field-label {{ color:{BRAND_BLUE}; font-weight:700; margin:6px 0 4px; }}

      /* Cards (KPI) */
      .card {{
        border:1px solid {CARD_BORDER}; background:#fff;
        border-radius:16px; padding:16px 18px; box-shadow:0 6px 20px rgba(30,75,135,0.06);
        min-height:110px;
      }}
      .kpi-label {{ font-size:13px; color:#6B7280; margin-bottom:4px; }}
      .kpi-value {{ font-size:34px; font-weight:800; line-height:1.1; }}
      .good {{ color:#1E7D4F }} .bad {{ color:#B00020 }}

      /* P&L table */
      table.pl {{ width:100%; border-collapse:collapse; border:1px solid {CARD_BORDER}; border-radius:14px; overflow:hidden; background:#fff; }}
      table.pl th, table.pl td {{ padding:10px 12px; border-bottom:1px solid #EEF2F8; text-align:left }}
      table.pl th {{ background:{CARD_SOFT}; color:{BRAND_TEXT}; font-weight:700 }}
      table.pl tr:last-child td {{ border-bottom:none }}
      .muted {{ color:#6B7280; font-size:12px }}

      /* Radios */
      input[type="radio"] {{ accent-color:{BRAND_BLUE} !important; background:#FFFFFF !important; }}
      div[role="radiogroup"] * {{ color:{BRAND_TEXT} !important; }}

      /* INPUT SIZING: keep inputs compact so they don't span full width */
      .stTextInput, .stNumberInput {{ max-width: 320px !important; }}

      /* Newer Streamlit input core */
      div[data-baseweb="input"] {{
        background:#FFFFFF !important;
        border:2px solid {BRAND_BLUE} !important;
        border-radius:12px !important;
      }}
      div[data-baseweb="input"] input {{
        font-family:Poppins, sans-serif !important;
        font-size:22px !important; font-weight:700 !important; color:{BRAND_TEXT} !important;
        height:56px !important; padding:10px 12px !important; text-align:right !important;
        background:#FFFFFF !important; box-shadow:none !important;
      }}

      /* Legacy wrappers (cover some hosts) */
      .stTextInput>div>div>input, .stNumberInput>div>div>input {{
        background:#FFFFFF !important; color:{BRAND_TEXT} !important;
        font-family:Poppins, sans-serif !important; font-size:22px !important; font-weight:700 !important;
        height:56px !important; padding:10px 12px !important; text-align:right !important;
        border:2px solid {BRAND_BLUE} !important; border-radius:12px !important; box-shadow:none !important;
      }}
      input:invalid {{ border-color:{BRAND_BLUE} !important; box-shadow:none !important; }}

      /* Unit chips (prefix/suffix) that visually attach to inputs */
      .chip {{
        display:flex; align-items:center; justify-content:center;
        height:56px; padding:0 10px; background:#F6FAFF; color:{BRAND_TEXT};
        border:2px solid {BRAND_BLUE}; font-weight:700; font-family:Poppins, sans-serif;
      }}
      .chip-left  {{ border-right:0; border-radius:12px 0 0 12px; }}
      .chip-right {{ border-left:0;  border-radius:0 12px 12px 0; }}

      /* Buttons */
      .stButton > button, .stDownloadButton > button {{
        background:{BRAND_BLUE} !important; color:#fff !important; border-color:{BRAND_BLUE} !important;
        font-weight:700; border-radius:10px; height:48px;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def money_input(label: str, value: float, key: str, step: float = 1.0, suffix: str | None = None) -> float:
    """Renders a compact input with a left 'C$' chip and optional right unit chip."""
    st.markdown(f"<div class='field-label'>{label}</div>", unsafe_allow_html=True)
    col_l, col_mid, col_r = st.columns([0.18, 0.64, 0.18], vertical_alignment="center")
    with col_l:
        st.markdown("<div class='chip chip-left'>C$</div>", unsafe_allow_html=True)
    with col_mid:
        val = st.number_input(label="", key=key, value=float(value), step=step, format="%.2f", label_visibility="collapsed")
    with col_r:
        if suffix:
            st.markdown(f"<div class='chip chip-right'>{suffix}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div></div>", unsafe_allow_html=True)
    return float(val)
def cad(x: float) -> str:
    x = float(x)
    return f"-C${abs(x):,.2f}" if x < 0 else f"C${x:,.2f}"

HST_RATE = 0.13  # fixed 13% (Ontario)

def compute_metrics(
    units: int,
    fee_per_unit_month: float,
    manager_salary_annual: float,
    manager_days_per_week: int,  # 1..5
    accounting_fees_annual: float,
    head_office_annual: float,
    fixed_overhead_annual: float,
):
    units = max(0, int(units))
    # Revenue (pre-tax)
    m_rev_sub = fee_per_unit_month * units
    a_rev_sub = m_rev_sub * 12
    # HST (pass-through)
    m_hst, a_hst = m_rev_sub * HST_RATE, a_rev_sub * HST_RATE
    m_rev_tot, a_rev_tot = m_rev_sub + m_hst, a_rev_sub + a_hst
    # Expenses (manager salary prorated by days/5)
    manager_alloc = manager_salary_annual * (manager_days_per_week / 5.0)
    a_exp = manager_alloc + accounting_fees_annual + head_office_annual + fixed_overhead_annual
    m_exp = a_exp / 12.0
    # Profits (pre-tax revenue basis)
    a_profit, m_profit = a_rev_sub - a_exp, m_rev_sub - m_exp
    return {
        "m_rev_sub": m_rev_sub, "a_rev_sub": a_rev_sub,
        "m_hst": m_hst, "a_hst": a_hst,
        "m_rev_tot": m_rev_tot, "a_rev_tot": a_rev_tot,
        "manager_alloc": manager_alloc,
        "a_exp": a_exp, "m_exp": m_exp,
        "a_profit": a_profit, "m_profit": m_profit,
    }

def required_fee_for_margin(
    target_margin_pct: float,
    units: int,
    manager_salary_annual: float,
    manager_days_per_week: int,
    accounting_fees_annual: float,
    head_office_annual: float,
    fixed_overhead_annual: float,
):
    if units <= 0:
        return float("inf")
    manager_alloc = manager_salary_annual * (manager_days_per_week / 5.0)
    a_exp = manager_alloc + accounting_fees_annual + head_office_annual + fixed_overhead_annual
    m = max(0.0, min(0.95, target_margin_pct / 100.0))
    if 1.0 - m == 0:
        return float("inf")
    req_a_rev = a_exp / (1.0 - m)               # pre-tax revenue needed
    fee = req_a_rev / (units * 12.0)            # $/unit/month
    return fee

def margin_from_fee(
    fee_per_unit_month: float,
    units: int,
    manager_salary_annual: float,
    manager_days_per_week: int,
    accounting_fees_annual: float,
    head_office_annual: float,
    fixed_overhead_annual: float,
):
    if units <= 0:
        return 0.0
    a_rev_sub = fee_per_unit_month * units * 12.0
    manager_alloc = manager_salary_annual * (manager_days_per_week / 5.0)
    a_exp = manager_alloc + accounting_fees_annual + head_office_annual + fixed_overhead_annual
    a_profit = a_rev_sub - a_exp
    return 0.0 if a_rev_sub == 0 else (a_profit / a_rev_sub) * 100.0

# ──────────────────────────────────────────────────────────────────────────────
# Header (logo + title)
# ──────────────────────────────────────────────────────────────────────────────
logo_path = os.path.join("assets", "logo.png")
lcol, rcol = st.columns([3, 1], vertical_alignment="center")
with lcol:
    st.markdown("<div class='brand-title'>ALBA Pricing & Profit Planner</div>", unsafe_allow_html=True)
    st.markdown("<div class='brand-bar'></div>", unsafe_allow_html=True)
with rcol:
    if os.path.exists(logo_path):
        st.image(logo_path, use_column_width=True)

# ──────────────────────────────────────────────────────────────────────────────
# Inputs
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Inputs</div>", unsafe_allow_html=True)

c1, c2 = st.columns([3, 2])
with c1:
    property_name = st.text_input("Property name", "Sample Property")
with c2:
    property_address = st.text_input("Address", "123 Example St, City, Province")

units = st.number_input("Residential units", min_value=0, step=1, value=100)

# Make this readable (blue) without changing your layout logic
st.markdown("<div class='field-label'>Primary input mode</div>", unsafe_allow_html=True)
mode = st.radio(
    "Choose what you enter:",
    ["Target Margin % → Calculate Fee", "Price per unit → Calculate Margin"],
    label_visibility="collapsed",
    index=0,
)

if "Target Margin" in mode:
    target_margin = st.number_input("Target profit margin (%)", min_value=0.0, max_value=95.0, step=0.5, format="%.2f", value=20.0)
    fee_input = None
else:
fee_input = money_input("Management fee (pre-tax)", 75.0, key="fee_input", step=5.0, suffix="/unit/month")    target_margin = None

st.markdown("**Manager & Overhead (annual)**")
g1, g2 = st.columns(2)
with g1:
    manager_salary = st.number_input("Manager salary (annual)", min_value=0.0, step=1000.0, format="%.2f", value=90000.0)
with g2:
    manager_days = st.number_input("Manager days on-site per week (1–5)", min_value=1, max_value=5, step=1, value=2)

h1, h2 = st.columns(2)
with h1:
    accounting = st.number_input("Accounting fees (annual)", min_value=0.0, step=500.0, format="%.2f", value=12000.0)
with h2:
    head_office = st.number_input("Head office team time (annual)", min_value=0.0, step=500.0, format="%.2f", value=18000.0)

fixed_overhead = st.number_input("Fixed overhead (annual)", min_value=0.0, step=500.0, format="%.2f", value=30000.0)

st.markdown("**Projection Controls**")
proj1, proj2 = st.columns(2)
with proj1:
    growth_rate = st.number_input("Annual fee increase %", min_value=0.0, max_value=25.0, step=0.5, format="%.2f", value=3.0)
with proj2:
    years = st.number_input("Projection years", min_value=1, max_value=10, step=1, value=5)

st.button("Apply Changes", use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────────
# Compute based on mode
# ──────────────────────────────────────────────────────────────────────────────
if "Target Margin" in mode:
    fee = required_fee_for_margin(target_margin, units, manager_salary, manager_days, accounting, head_office, fixed_overhead)
    margin = target_margin
else:
    fee = float(fee_input or 0.0)
    margin = margin_from_fee(fee, units, manager_salary, manager_days, accounting, head_office, fixed_overhead)

M = compute_metrics(units, fee, manager_salary, manager_days, accounting, head_office, fixed_overhead)

# Break-even fee (0% margin)
break_even_fee = required_fee_for_margin(
    target_margin_pct=0.0,
    units=units,
    manager_salary_annual=manager_salary,
    manager_days_per_week=manager_days,
    accounting_fees_annual=accounting,
    head_office_annual=head_office,
    fixed_overhead_annual=fixed_overhead,
)

# ──────────────────────────────────────────────────────────────────────────────
# KPI row (big numbers)
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Outputs</div>", unsafe_allow_html=True)
k1, k2, k3 = st.columns([1, 1, 2])
with k1:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='kpi-label'>Price per Unit (pre-tax)</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='kpi-value'>{cad(fee)}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
with k2:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='kpi-label'>Margin</div>", unsafe_allow_html=True)
    cls = "good" if margin >= 0 else "bad"
    st.markdown(f"<div class='kpi-value {cls}'>{margin:.2f}%</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
with k3:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='kpi-label'>Profit (Monthly / Annual)</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='kpi-value'>{cad(M['m_profit'])} / {cad(M['a_profit'])}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Charts — Expense doughnut + Profit projection bar
# ──────────────────────────────────────────────────────────────────────────────
cA, cB = st.columns(2)

with cA:
    labels = ["Manager (allocated)", "Fixed overhead", "Head office", "Accounting"]
    vals = [M["manager_alloc"], fixed_overhead, head_office, accounting]
    colors_pie = [BRAND_BLUE, "#7FB3FF", "#A5C8FF", "#D6E6FF"]
    pie = go.Figure(go.Pie(labels=labels, values=vals, hole=0.6, marker=dict(colors=colors_pie)))
    pie.update_layout(
        title_text="Expense Breakdown (%)",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Poppins", color=BRAND_TEXT),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        margin=dict(l=10, r=10, t=40, b=40),
        height=340,
    )
    st.plotly_chart(pie, use_container_width=True, theme=None)

with cB:
    years_labels = [f"Year {i}" for i in range(1, int(years) + 1)]
    profits = []
    fee_year = fee
    for _ in years_labels:
        a_rev = (fee_year * units) * 12.0
        a_profit = a_rev - M["a_exp"]
        profits.append(a_profit)
        fee_year *= (1 + float(growth_rate) / 100.0)

    bar = go.Figure(go.Bar(
        x=years_labels, y=profits, marker_color=BRAND_BLUE,
        text=[cad(p) for p in profits], textposition="outside"
    ))
    bar.update_layout(
        title_text=f"Profit Projection ({growth_rate:.1f}% annual fee increase)",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Poppins", color=BRAND_TEXT),
        yaxis=dict(title="Annual Profit (CAD)", tickprefix="C$", showgrid=True, gridcolor="#EEF2F8"),
        xaxis=dict(title="Year", showgrid=False),
        margin=dict(l=10, r=10, t=50, b=60),
        height=340,
    )
    st.plotly_chart(bar, use_container_width=True, theme=None)

# ──────────────────────────────────────────────────────────────────────────────
# Unified P&L (Monthly vs Annual)
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Profit & Loss (Monthly vs Annual)</div>", unsafe_allow_html=True)
rows = [
    ("REVENUE (pre-tax)", "", ""),
    ("Subtotal fees", M["m_rev_sub"], M["a_rev_sub"]),
    ("HST 13% (pass-through)", M["m_hst"], M["a_hst"]),
    ("Total billed (with HST)", M["m_rev_tot"], M["a_rev_tot"]),
    ("", "", ""),
    ("EXPENSES", "", ""),
    ("Manager (allocated)", M["manager_alloc"]/12.0, M["manager_alloc"]),
    ("Accounting fees", accounting/12.0, accounting),
    ("Head office team time", head_office/12.0, head_office),
    ("Fixed overhead", fixed_overhead/12.0, fixed_overhead),
    ("Total operating expenses", M["m_exp"], M["a_exp"]),
    ("", "", ""),
    ("PROFIT / (LOSS)", M["m_profit"], M["a_profit"]),
]
html = ["<table class='pl'>", "<tr><th>Line item</th><th>Monthly</th><th>Annual</th></tr>"]
for name, mv, av in rows:
    mv_str = cad(mv) if mv != "" else ""
    av_str = cad(av) if av != "" else ""
    html.append(f"<tr><td><strong>{name}</strong></td><td>{mv_str}</td><td>{av_str}</td></tr>")
html.append("</table>")
st.markdown("\n".join(html), unsafe_allow_html=True)

if M["a_profit"] < 0:
    st.error("Negative margin detected. Increase fee or reduce costs.")

# ──────────────────────────────────────────────────────────────────────────────
# PDF Export (ReportLab) – one page with logo, KPIs, table, and charts
# ──────────────────────────────────────────────────────────────────────────────
def fig_to_png_bytes(fig) -> bytes:
    # Requires kaleido
    return fig.to_image(format="png", scale=2, engine="kaleido")

def build_pdf() -> bytes:
    # Render charts to PNG
    pie_png = fig_to_png_bytes(pie)
    bar_png = fig_to_png_bytes(bar)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    margin = 36
    y = H - margin

    # Header with logo + title
    if os.path.exists(logo_path):
        try:
            c.drawImage(ImageReader(logo_path), margin, y-40, width=120, height=40, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    c.setFillColor(colors.HexColor(BRAND_TEXT))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin + 140, y-18, "ALBA Pricing & Profit Planner")
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawString(margin + 140, y-34, f"{property_name} — {property_address} — {datetime.now():%Y-%m-%d}")

    # Blue divider
    c.setFillColor(colors.HexColor(BRAND_BLUE))
    c.rect(margin, y-50, W - 2*margin, 3, stroke=0, fill=1)

    # KPI boxes
    c.setFillColor(colors.white); c.setStrokeColor(colors.HexColor(CARD_BORDER))
    box_w = (W - 2*margin - 20) / 3
    for i in range(3):
        c.roundRect(margin + i*(box_w+10), y-120, box_w, 55, 8, stroke=1, fill=1)

    c.setFillColor(colors.HexColor("#6B7280")); c.setFont("Helvetica", 9)
    c.drawString(margin+10, y-68, "Price per Unit (pre-tax)")
    c.drawString(margin+10+box_w+10, y-68, "Margin")
    c.drawString(margin+10+2*(box_w+10), y-68, "Profit (Monthly / Annual)")

    c.setFillColor(colors.HexColor(BRAND_TEXT)); c.setFont("Helvetica-Bold", 16)
    c.drawString(margin+10, y-88, cad(fee))
    c.drawString(margin+10+box_w+10, y-88, f"{margin:.2f}%")
    c.drawString(margin+10+2*(box_w+10), y-88, f"{cad(M['m_profit'])} / {cad(M['a_profit'])}")

    # P&L table (compact)
    c.setFont("Helvetica-Bold", 11); c.setFillColor(colors.HexColor(BRAND_BLUE))
    c.drawString(margin, y-140, "Profit & Loss (Monthly vs Annual)")
    c.setFont("Helvetica", 9); c.setFillColor(colors.HexColor(BRAND_TEXT))

    ty = y-155
    col2 = margin + 260
    col3 = margin + 420
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, ty, "Line item"); c.drawString(col2, ty, "Monthly"); c.drawString(col3, ty, "Annual")
    c.setStrokeColor(colors.HexColor(CARD_BORDER))
    c.line(margin, ty-2, W-margin, ty-2)
    c.setFont("Helvetica", 9)

    ty -= 14
    for name, mv, av in rows:
        mv_str = cad(mv) if mv != "" else ""
        av_str = cad(av) if av != "" else ""
        c.drawString(margin, ty, name)
        c.drawRightString(col2+120, ty, mv_str)
        c.drawRightString(W-margin, ty, av_str)
        ty -= 14
        if ty < 220:  # stop before charts
            break

    # Charts row
    chart_h = 180; chart_w = (W - 2*margin - 10) / 2
    try:
        c.drawImage(ImageReader(BytesIO(pie_png)), margin, 80, width=chart_w, height=chart_h, preserveAspectRatio=True, mask='auto')
    except Exception:
        pass
    try:
        c.drawImage(ImageReader(BytesIO(bar_png)), margin + chart_w + 10, 80, width=chart_w, height=chart_h, preserveAspectRatio=True, mask='auto')
    except Exception:
        pass

    # Footer
    c.setFont("Helvetica", 8); c.setFillColor(colors.HexColor("#6B7280"))
    c.drawString(margin, 60, "HST fixed at 13% (Ontario). HST is pass-through and excluded from profit/margin.")
    c.drawRightString(W - margin, 60, "ALBA Property Management")

    c.showPage(); c.save()
    buf.seek(0)
    return buf.getvalue()

st.markdown("<div class='section-title'>Export</div>", unsafe_allow_html=True)
pdf_bytes = build_pdf()
st.download_button(
    "Download Summary (PDF)",
    data=pdf_bytes,
    file_name=f"ALBA_Pricing_Summary_{datetime.now():%Y%m%d}.pdf",
    mime="application/pdf",
    use_container_width=True,
)
