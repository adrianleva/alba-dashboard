# streamlit_app.py — ALBA Pricing & Profit (final UI tweaks)
# - Headings in ALBA blue, rounded cards, Poppins font
# - Mode toggle (blue radios), 13% HST fixed
# - Manager days as 1–5 numeric box (salary prorated)
# - Doughnut chart on white; projection = bar chart with clear axes
# - Unified Monthly & Annual P&L

from __future__ import annotations
from datetime import datetime
import os
import streamlit as st
import plotly.graph_objects as go

# ──────────────────────────────────────────────────────────────────────────────
# Page + Brand theme
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="ALBA Pricing & Profit", page_icon="🏢", layout="wide")

BRAND_BLUE = "#1E4B87"
BRAND_TEXT = "#0F2544"
CARD_BG = "#FFFFFF"
CARD_BORDER = "#E5ECF6"
CARD_SOFT = "#F6FAFF"

st.markdown(
    f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap');
      html, body, [data-testid="stAppViewContainer"] {{
        background: #FFFFFF !important;
        color: {BRAND_TEXT} !important;
        font-family: Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif !important;
      }}
      [data-testid="stHeader"] {{
        background: #FFFFFF !important; border-bottom: none !important;
      }}
      .container {{ max-width: 1200px; margin: 0 auto; }}
      .brand-title {{
        color: {BRAND_TEXT}; font-weight: 800; font-size: 30px; margin: 2px 0 0;
      }}
      .brand-bar {{ height: 5px; background: {BRAND_BLUE}; margin: 8px 0 16px; border-radius: 2px; }}
      .section-title {{
        color: {BRAND_BLUE}; font-weight: 800; margin: 8px 0 8px; font-size: 18px;
      }}
      .card {{
        border: 1px solid {CARD_BORDER}; background: {CARD_BG};
        border-radius: 14px; padding: 14px 16px; box-shadow: 0 2px 8px rgba(17,38,146,0.06);
      }}
      .kpi-value {{ font-size: 28px; font-weight: 800; margin-top: 2px; }}
      .good {{ color: #1E7D4F }} .bad {{ color: #B00020 }}
      table.pl {{ width:100%; border-collapse: collapse; border:1px solid {CARD_BORDER};
                 border-radius:12px; overflow:hidden; background:#fff; }}
      table.pl th, table.pl td {{ padding:10px 12px; border-bottom:1px solid #EEF2F8; text-align:left }}
      table.pl th {{ background:{CARD_SOFT}; color:{BRAND_TEXT} }}
      table.pl tr:last-child td {{ border-bottom:none }}
      .muted {{ color:#6B7280; font-size:12px }}

      /* Blue radios with white interior */
      input[type="radio"] {{
        accent-color: {BRAND_BLUE} !important;
        background-color: #FFFFFF !important;
      }}
      /* Primary buttons */
      .stButton > button {{
        background: {BRAND_BLUE} !important;
        border-color: {BRAND_BLUE} !important;
        color: #fff !important;
        font-weight: 700;
        border-radius: 10px;
      }}
      /* Inputs on white */
      .stTextInput>div>div>input, .stNumberInput>div>div>input {{
        background: #fff !important;
        color: {BRAND_TEXT} !important;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def cad(x: float) -> str:
    x = float(x)
    return f"-C${abs(x):,.2f}" if x < 0 else f"C${x:,.2f}"

HST_RATE = 0.13  # Fixed 13% (Ontario)

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
    """Compute $/unit/month fee to hit a target profit margin on pre-tax revenue."""
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
    # Revenue (pre-tax)
    a_rev_sub = fee_per_unit_month * units * 12.0
    # Expenses
    manager_alloc = manager_salary_annual * (manager_days_per_week / 5.0)
    a_exp = manager_alloc + accounting_fees_annual + head_office_annual + fixed_overhead_annual
    a_profit = a_rev_sub - a_exp
    return 0.0 if a_rev_sub == 0 else (a_profit / a_rev_sub) * 100.0

# ──────────────────────────────────────────────────────────────────────────────
# Header with logo
# ──────────────────────────────────────────────────────────────────────────────
logo_path = os.path.join("assets", "logo.png")
left, right = st.columns([3, 1], vertical_alignment="center")
with left:
    st.markdown("<div class='brand-title'>ALBA Property Management — Pricing & Profit</div>", unsafe_allow_html=True)
    st.markdown("<div class='brand-bar'></div>", unsafe_allow_html=True)
with right:
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

st.caption("Primary input mode")
mode = st.radio(
    "Choose what you enter:",
    ["Target Margin % → Calculate Fee", "Price per unit → Calculate Margin"],
    label_visibility="collapsed",
    index=0,
)

# Mode-specific inputs
fee_input = None
target_margin = None
if "Target Margin" in mode:
    target_margin = st.number_input("Target profit margin (%)", min_value=0.0, max_value=95.0, step=0.5, format="%.2f", value=20.0)
else:
    fee_input = st.number_input("Management fee $/unit/month (pre-tax)", min_value=0.0, step=5.0, format="%.2f", value=75.0)

st.markdown("**Manager & Overhead (annual)**")
g1, g2 = st.columns(2)
with g1:
    manager_salary = st.number_input("Manager salary (annual)", min_value=0.0, step=1000.0, format="%.2f", value=90000.0)
with g2:
    # Numeric box 1–5 (no slider)
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
# Calculations (depending on mode)
# ──────────────────────────────────────────────────────────────────────────────
if "Target Margin" in mode:
    fee_calc = required_fee_for_margin(
        target_margin, units, manager_salary, manager_days, accounting, head_office, fixed_overhead
    )
    fee_to_use = fee_calc
    margin_calc = margin_from_fee(
        fee_to_use, units, manager_salary, manager_days, accounting, head_office, fixed_overhead
    )
else:
    fee_to_use = fee_input
    margin_calc = margin_from_fee(
        fee_to_use, units, manager_salary, manager_days, accounting, head_office, fixed_overhead
    )
    fee_calc = None  # not applicable

M = compute_metrics(units, fee_to_use, manager_salary, manager_days, accounting, head_office, fixed_overhead)

# Break-even fee (margin = 0)
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
# Outputs — KPI row
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Outputs</div>", unsafe_allow_html=True)
k1, k2, k3 = st.columns([1, 1, 2])
with k1:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.caption("Break-even $/unit/month (pre-tax)")
    st.markdown(f"<div class='kpi-value'>{cad(break_even_fee)}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with k2:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    if "Target Margin" in mode:
        st.caption("Required price (to hit target)")
        st.markdown(f"<div class='kpi-value'>{cad(fee_to_use)}</div>", unsafe_allow_html=True)
    else:
        cls = "good" if margin_calc >= 0 else "bad"
        st.caption("Resulting margin")
        st.markdown(f"<div class='kpi-value {cls}'>{margin_calc:.2f}%</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with k3:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.caption("Profit (Monthly / Annual)")
    st.markdown(f"<div class='kpi-value'>{cad(M['m_profit'])} / {cad(M['a_profit'])}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Charts — Doughnut (expenses) + Bar projection
# ──────────────────────────────────────────────────────────────────────────────
cA, cB = st.columns(2)

with cA:
    # Expense doughnut — brand colors on white
    labels = ["Manager (allocated)", "Fixed overhead", "Head office", "Accounting"]
    vals = [M["manager_alloc"], fixed_overhead, head_office, accounting]
    colors = [BRAND_BLUE, "#7FB3FF", "#A5C8FF", "#D6E6FF"]
    pie = go.Figure(go.Pie(labels=labels, values=vals, hole=0.55, marker=dict(colors=colors)))
    pie.update_layout(
        title_text="Expense Breakdown (%)",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        margin=dict(l=10, r=10, t=40, b=40),
        height=340,
    )
    st.plotly_chart(pie, use_container_width=True, theme=None)

with cB:
    # Profit projection bar chart using editable growth rate
    years_labels = [f"Year {i}" for i in range(1, int(years) + 1)]
    profits = []
    fee_year = fee_to_use
    for _ in years_labels:
        # Compute profit for this year with current fee_year; expenses assumed flat
        m_rev_sub_y = fee_year * units
        a_rev_sub_y = m_rev_sub_y * 12
        a_profit_y = a_rev_sub_y - M["a_exp"]
        profits.append(a_profit_y)
        fee_year *= (1 + float(growth_rate) / 100.0)

    bar = go.Figure(go.Bar(x=years_labels, y=profits, marker_color=BRAND_BLUE, text=[cad(p) for p in profits], textposition="outside"))
    bar.update_layout(
        title_text=f"Profit Projection ({growth_rate:.1f}% annual fee increase)",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        yaxis=dict(title="Annual Profit (CAD)", tickprefix="C$", showgrid=True, gridcolor="#EEF2F8"),
        xaxis=dict(title="Year"),
        margin=dict(l=10, r=10, t=40, b=60),
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
    (f"HST 13% (pass-through)", M["m_hst"], M["a_hst"]),
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
# Export (print-friendly HTML → Save as PDF)
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Export</div>", unsafe_allow_html=True)
st.caption("Use your browser’s **Print → Save as PDF** to export the one-pager.")

summary_html = f"""
<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<title>ALBA Pricing Summary</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap');
  body {{ font-family: Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; color: {BRAND_TEXT}; background:#fff; margin:24px; }}
  h1 {{ margin:0 0 6px 0; color:{BRAND_TEXT}; }}
  .muted {{ color:#6b7280; font-size:12px; }}
  .bar {{ height:4px; background:{BRAND_BLUE}; margin:8px 0 12px; }}
  table {{ width:100%; border-collapse:collapse; margin:12px 0; }}
  th, td {{ border:1px solid #e5e7eb; padding:8px; text-align:left; }}
  th {{ background:{CARD_SOFT}; }}
  .kpis {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
  .card {{ border:1px solid #e5e7eb; padding:10px 12px; border-radius:10px; }}
  .big {{ font-size:18px; font-weight:800; }}
  @media print {{ @page {{ size:A4; margin:14mm; }} }}
</style>
</head>
<body>
  <h1>ALBA Property Management — Pricing & Profit</h1>
  <div class='muted'>{property_name} — {property_address} — {datetime.now().strftime('%Y-%m-%d')}</div>
  <div class='bar'></div>

  <div class='kpis'>
    <div class='card'><div>Break-even $/unit/month</div><div class='big'>{cad(break_even_fee)}</div></div>
    <div class='card'><div>{"Required price (to hit target)" if "Target Margin" in mode else "Resulting margin"}</div><div class='big'>{cad(fee_to_use) if "Target Margin" in mode else f"{margin_calc:.2f}%"} </div></div>
  </div>

  <h3 style="color:{BRAND_BLUE};">Profit & Loss (Monthly vs Annual)</h3>
  <table>
    <tr><th>Line item</th><th>Monthly</th><th>Annual</th></tr>
    {''.join([f"<tr><td><strong>{n}</strong></td><td>{cad(mv) if mv!='' else ''}</td><td>{cad(av) if av!='' else ''}</td></tr>" for (n,mv,av) in rows])}
  </table>

  <div class='muted'>HST fixed at 13% (Ontario). HST is pass-through and excluded from profit/margin.</div>
</body>
</html>
"""

st.download_button(
    "Download Print Summary (HTML)",
    data=summary_html.encode("utf-8"),
    file_name=f"ALBA_Pricing_Summary_{datetime.now().strftime('%Y%m%d')}.html",
    mime="text/html",
    use_container_width=True,
)
