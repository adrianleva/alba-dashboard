# streamlit_app.py
# ALBA Pricing & Profit — final build with mode toggle, manager days allocation, fixed HST 13%, charts, and PDF export
from __future__ import annotations
from datetime import datetime
from io import BytesIO
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go

from calculations import (
    cad, Inputs, FULL_TIME_DAYS, HST_RATE,
    allocated_manager_cost, annual_expenses_total,
    required_fee_for_margin, margin_from_fee,
    compute_core, projection
)
from pdf_utils import build_pdf

# ──────────────────────────────────────────────────────────────────────────────
# Page setup & style (Poppins + ALBA vibe)
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="ALBA Pricing & Profit", page_icon="🏢", layout="centered")

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root{
    --alba-blue:#1E4B87; --alba-text:#0F2544; --alba-bg:#FFFFFF; --soft:#F6FAFF; --border:#E5ECF6;
  }
  html, body, [data-testid="stAppViewContainer"]{
    background:var(--alba-bg)!important; color:var(--alba-text)!important;
    font-family: Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  }
  [data-testid="stHeader"]{background:var(--alba-bg)!important;border-bottom:none}
  .block-container{max-width:1100px}
  .brand-title{font-weight:800;font-size:28px;margin:6px 0 4px}
  .brand-bar{height:5px;background:var(--alba-blue);margin:6px 0 16px;border-radius:2px}
  .card{border:1px solid var(--border); border-radius:14px; background:#fff;
        box-shadow:0 2px 8px rgba(17,38,146,0.06); padding:14px 16px; }
  .kpi-value{font-size:28px;font-weight:800;margin-top:2px}
  .bad{color:#B00020} .good{color:#1E7D4F}
  .section-title{font-weight:800;margin:10px 0 8px}
  table.pl{width:100%;border-collapse:collapse;border:1px solid var(--border);border-radius:12px;overflow:hidden;background:#fff}
  table.pl th, table.pl td{padding:10px 12px;border-bottom:1px solid #EEF2F8;text-align:left}
  table.pl th{background:#F6FAFF;color:#22314D}
  table.pl tr:last-child td{border-bottom:none}
  .muted{color:#6B7280;font-size:12px}
  .stButton>button{background:var(--alba-blue)!important;border-color:var(--alba-blue)!important;color:#fff!important}
</style>
""", unsafe_allow_html=True)

ASSETS = Path("assets")
LOGO = ASSETS / "logo.png"

# ──────────────────────────────────────────────────────────────────────────────
# Header (logo + title)
# ──────────────────────────────────────────────────────────────────────────────
left, right = st.columns([3,1], vertical_alignment="center")
with left:
    st.markdown("<div class='brand-title'>ALBA Property Management — Pricing & Profit</div>", unsafe_allow_html=True)
    st.markdown("<div class='brand-bar'></div>", unsafe_allow_html=True)
with right:
    if LOGO.exists():
        st.image(str(LOGO), use_column_width=True)
    else:
        st.caption("Upload assets/logo.png to show your logo.")

# ──────────────────────────────────────────────────────────────────────────────
# Inputs
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Inputs</div>", unsafe_allow_html=True)
with st.form("inputs_form"):
    c1, c2 = st.columns(2)
    with c1:
        prop_name = st.text_input("Property name", "Sample Property")
    with c2:
        prop_addr = st.text_input("Address", "123 Example St, City, Province")

    res_units = st.number_input("Residential units", min_value=0, step=1, value=100)

    # Mode toggle
    mode = st.radio("Primary input mode", ["Target Margin % → Calculate Fee", "Price per Unit → Calculate Margin"],
                    index=0, horizontal=True)
    is_target_mode = mode.startswith("Target")

    if is_target_mode:
        target_margin = st.number_input("Target profit margin (%)", min_value=0.0, max_value=95.0, step=0.5, value=20.0)
        fee_input = None
    else:
        fee_input = st.number_input("Management fee $/unit/month (pre-tax)", min_value=0.0, step=5.0, format="%.2f", value=75.0)
        target_margin = None

    st.markdown("**Manager & Overhead (annual)**")
    r1, r2 = st.columns(2)
    with r1:
        manager_salary = st.number_input("Manager salary (annual)", min_value=0.0, step=1000.0, format="%.2f", value=90000.0)
    with r2:
        manager_days = st.slider("Manager days on-site per week (0–5)", min_value=0, max_value=5, value=5)

    o1, o2 = st.columns(2)
    with o1:
        accounting = st.number_input("Accounting fees (annual)", min_value=0.0, step=500.0, format="%.2f", value=12000.0)
    with o2:
        head_office = st.number_input("Head office team time (annual)", min_value=0.0, step=500.0, format="%.2f", value=18000.0)

    fixed_overhead = st.number_input("Fixed overhead (annual)", min_value=0.0, step=500.0, format="%.2f", value=30000.0)

    st.markdown("**Projection Controls**")
    g1, g2 = st.columns(2)
    with g1:
        growth_pct = st.number_input("Annual fee increase %", min_value=0.0, max_value=20.0, step=0.5, value=3.0)
    with g2:
        years = st.number_input("Projection years", min_value=1, max_value=10, step=1, value=5)

    submitted = st.form_submit_button("Apply Changes", use_container_width=True)

# Compute expenses
exp_annual = annual_expenses_total(manager_salary, manager_days, accounting, head_office, fixed_overhead)

# Determine fee/margin according to mode
if is_target_mode:
    required_fee = required_fee_for_margin(res_units, exp_annual, target_margin or 0.0)
    fee = required_fee
    actual_margin = margin_from_fee(res_units, fee, exp_annual)
else:
    fee = fee_input or 0.0
    actual_margin = margin_from_fee(res_units, fee, exp_annual)
    required_fee = None  # not used in this mode

# Core monthly/annual rollups (HST fixed at 13% via calculations module)
core = compute_core(res_units, fee, exp_annual)

# ──────────────────────────────────────────────────────────────────────────────
# Outputs — KPI cards
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Outputs</div>", unsafe_allow_html=True)
k1, k2, k3 = st.columns(3)
with k1:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.caption("Break-even $/unit/month (pre-tax)")
    # Break-even here is the fee needed for 0% profit (i.e., margin 0)
    fee_zero_margin = required_fee_for_margin(res_units, exp_annual, 0.0)
    st.markdown(f"<div class='kpi-value'>{cad(fee_zero_margin)}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
with k2:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    if is_target_mode:
        st.caption("Required fee to hit target margin")
        st.markdown(f"<div class='kpi-value'>{cad(required_fee)}</div>", unsafe_allow_html=True)
    else:
        st.caption("Resulting margin at entered fee")
        cls = "good" if actual_margin >= 0 else "bad"
        st.markdown(f"<div class='kpi-value {cls}'>{actual_margin:.2f}%</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
with k3:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.caption("Monthly Profit / Annual Profit (pre-tax revenue basis)")
    st.markdown(f"<div class='kpi-value'>{cad(core['monthly_profit'])} / {cad(core['annual_profit'])}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Charts — Expense donut & Profit projection
# ──────────────────────────────────────────────────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    labels = ["Manager (allocated)", "Accounting", "Head office", "Fixed overhead"]
    manager_alloc = allocated_manager_cost(manager_salary, manager_days)
    values = [manager_alloc, accounting, head_office, fixed_overhead]
    pie = go.Figure(go.Pie(labels=labels, values=values, hole=0.55))
    pie.update_layout(title_text="Expense Breakdown (%)", height=320, margin=dict(l=10,r=10,t=50,b=10))
    st.plotly_chart(pie, use_container_width=True, theme="streamlit")

with c2:
    proj = projection(res_units, fee, years=int(years), growth_pct=(growth_pct/100.0), expenses_annual=exp_annual)
    xs = [f"Year {i}" for i in range(1, int(years)+1)]
    line = go.Figure()
    line.add_trace(go.Scatter(x=xs, y=proj["profits"], mode="lines+markers", name="Profit"))
    line.update_layout(title_text=f"Profit Projection ({growth_pct:.1f}% annual fee increase)", height=320, margin=dict(l=10,r=10,t=50,b=10))
    st.plotly_chart(line, use_container_width=True, theme="streamlit")

# ──────────────────────────────────────────────────────────────────────────────
# Unified P&L
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Profit & Loss (Monthly vs Annual)</div>", unsafe_allow_html=True)
pl_rows = [
    ("REVENUE (pre-tax)", "", ""),
    ("Subtotal fees", core["monthly_rev_subtotal"], core["annual_rev_subtotal"]),
    ("HST 13% (pass-through)", core["monthly_hst"], core["annual_hst"]),
    ("Total billed (with HST)", core["monthly_rev_total"], core["annual_rev_total"]),
    ("", "", ""),
    ("EXPENSES", "", ""),
    ("Manager (allocated)", manager_alloc/12, manager_alloc),
    ("Accounting", accounting/12, accounting),
    ("Head office", head_office/12, head_office),
    ("Fixed overhead", fixed_overhead/12, fixed_overhead),
    ("Total operating expenses", core["exp_monthly"], core["exp_annual"]),
    ("", "", ""),
    ("PROFIT / (LOSS)", core["monthly_profit"], core["annual_profit"]),
]

html = ["<table class='pl'>", "<tr><th>Line item</th><th>Monthly</th><th>Annual</th></tr>"]
for name, mv, av in pl_rows:
    mv_str = cad(mv) if mv != "" else ""
    av_str = cad(av) if av != "" else ""
    html.append(f"<tr><td><strong>{name}</strong></td><td>{mv_str}</td><td>{av_str}</td></tr>")
html.append("</table>")
st.markdown("\n".join(html), unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Export PDF — mirror UI
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Export</div>", unsafe_allow_html=True)
st.caption("Branded one-pager PDF (logo, KPIs, P&L, charts).")

def _fig_to_png(fig):
    return fig.to_image(format="png", width=1200, height=700, scale=2)

charts_png = {
    "expense_donut.png": pie.to_image(format="png", width=1000, height=600, scale=2),
    "profit_projection.png": line.to_image(format="png", width=1000, height=600, scale=2),
}

kpi_rows = []
if is_target_mode:
    kpi_rows.append(["Required fee to hit target margin", cad(required_fee)])
else:
    kpi_rows.append(["Resulting margin at entered fee", f"{actual_margin:.2f}%"])
kpi_rows.extend([
    ["Break-even $/unit/month (pre-tax)", cad(fee_zero_margin)],
    ["Monthly Profit / Annual Profit", f"{cad(core['monthly_profit'])} / {cad(core['annual_profit'])}"],
])

pl_rows_pdf = []
for name, mv, av in pl_rows:
    mv_str = cad(mv) if mv != "" else ""
    av_str = cad(av) if av != "" else ""
    pl_rows_pdf.append([name, mv_str, av_str])

pdf_buffer = BytesIO()
build_pdf(
    buffer=pdf_buffer,
    logo_path=str(LOGO) if LOGO.exists() else None,
    as_of=datetime.now().strftime("%Y-%m-%d"),
    prop_name=prop_name, prop_addr=prop_addr,
    kpis=kpi_rows,
    pl_rows=pl_rows_pdf,
    charts=charts_png,
)
st.download_button(
    "Download Summary (PDF)",
    data=pdf_buffer.getvalue(),
    file_name=f"ALBA_Pricing_Summary_{datetime.now().strftime('%Y%m%d')}.pdf",
    mime="application/pdf",
    use_container_width=True,
)
