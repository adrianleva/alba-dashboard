# calculations.py
# Pure functions for ALBA Pricing Dashboard
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

HST_RATE = 0.13  # 13% fixed in Ontario
FULL_TIME_DAYS = 5  # baseline for manager allocation

def cad(x: float) -> str:
    x = float(x)
    return f"-C${abs(x):,.2f}" if x < 0 else f"C${x:,.2f}"

@dataclass
class Inputs:
    property_name: str
    property_address: str
    res_units: int
    mode: str  # "target_margin" or "enter_price"
    target_margin_pct: float  # used if mode == target_margin
    fee_per_unit_month: float  # used if mode == enter_price
    manager_salary_annual: float
    manager_days_per_week: float  # allocation days (0..5)
    accounting_fees_annual: float
    head_office_time_annual: float
    fixed_overhead_annual: float
    growth_pct: float  # annual growth for fee, e.g., 0.03 for 3%
    years: int  # projection horizon

def allocated_manager_cost(manager_salary_annual: float, manager_days_per_week: float, baseline_days: float = FULL_TIME_DAYS) -> float:
    frac = 0.0 if baseline_days <= 0 else max(0.0, min(manager_days_per_week / baseline_days, 1.0))
    return manager_salary_annual * frac

def annual_expenses_total(manager_salary_annual: float, manager_days_per_week: float,
                          accounting_fees_annual: float, head_office_time_annual: float, fixed_overhead_annual: float) -> float:
    return (
        allocated_manager_cost(manager_salary_annual, manager_days_per_week)
        + accounting_fees_annual
        + head_office_time_annual
        + fixed_overhead_annual
    )

def required_fee_for_margin(units: int, expenses_annual: float, target_margin_pct: float) -> float:
    """Fee per unit per month required so that (Revenue - Expenses)/Revenue = target_margin."""
    m = max(0.0, min(target_margin_pct / 100.0, 0.95))
    if units <= 0:
        return float("inf")
    required_annual_revenue = expenses_annual / (1.0 - m) if 1.0 - m != 0 else float("inf")
    fee = required_annual_revenue / (units * 12.0)
    return fee

def margin_from_fee(units: int, fee_per_unit_month: float, expenses_annual: float) -> float:
    annual_revenue_subtotal = fee_per_unit_month * units * 12.0
    if annual_revenue_subtotal == 0:
        return 0.0
    profit = annual_revenue_subtotal - expenses_annual
    return (profit / annual_revenue_subtotal) * 100.0

def compute_core(units: int, fee_per_unit_month: float, expenses_annual: float) -> Dict:
    # Revenue (subtotal) billed on all units, HST is pass-through
    monthly_rev_subtotal = fee_per_unit_month * units
    annual_rev_subtotal = monthly_rev_subtotal * 12.0
    monthly_hst = monthly_rev_subtotal * HST_RATE
    annual_hst = annual_rev_subtotal * HST_RATE
    monthly_rev_total = monthly_rev_subtotal + monthly_hst
    annual_rev_total = annual_rev_subtotal + annual_hst

    exp_annual = expenses_annual
    exp_monthly = exp_annual / 12.0

    monthly_profit = monthly_rev_subtotal - exp_monthly
    annual_profit = annual_rev_subtotal - exp_annual
    actual_margin_pct = 0.0 if annual_rev_subtotal == 0 else (annual_profit / annual_rev_subtotal) * 100.0

    return dict(
        monthly_rev_subtotal=monthly_rev_subtotal,
        monthly_hst=monthly_hst,
        monthly_rev_total=monthly_rev_total,
        annual_rev_subtotal=annual_rev_subtotal,
        annual_hst=annual_hst,
        annual_rev_total=annual_rev_total,
        exp_annual=exp_annual,
        exp_monthly=exp_monthly,
        monthly_profit=monthly_profit,
        annual_profit=annual_profit,
        actual_margin_pct=actual_margin_pct,
    )

def projection(units: int, start_fee_per_unit_month: float, years: int, growth_pct: float,
               expenses_annual: float) -> Dict[str, List[float]]:
    """Returns yearly arrays for revenue (subtotal), expenses, and profit. HST excluded here (pass-through)."""
    fees = []
    revenues = []
    expenses = []
    profits = []
    fee = start_fee_per_unit_month
    for yr in range(1, years + 1):
        annual_rev = fee * units * 12.0
        profit = annual_rev - expenses_annual
        fees.append(fee)
        revenues.append(annual_rev)
        expenses.append(expenses_annual)
        profits.append(profit)
        fee = fee * (1.0 + growth_pct)
    return {"fees": fees, "revenues": revenues, "expenses": expenses, "profits": profits}
