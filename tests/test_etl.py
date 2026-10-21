from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from sales_etl.extract import detect_source, extract_orders, extract_payments, read_table
from sales_etl.load import connect, revenue_by_day
from sales_etl.money import to_cents
from sales_etl.pipeline import run_file
from sales_etl.transform import clean_orders, clean_payments

FIX = Path(__file__).parent / "fixtures"


def test_to_cents_parses_za_and_us_formats():
    assert to_cents("R 1 234,56") == 123456
    assert to_cents("1,234.56") == 123456
    assert to_cents(89.0) == 8900
    assert to_cents("89") == 8900
    with pytest.raises(ValueError):
        to_cents("")


def test_detects_source_from_columns_and_filename():
    assert detect_source(FIX / "pos_daily.csv", read_table(FIX / "pos_daily.csv")) == "pos_csv"
    assert detect_source(FIX / "shopify_orders.csv", read_table(FIX / "shopify_orders.csv")) == "shopify"
    assert detect_source(FIX / "yoco_payments.csv", read_table(FIX / "yoco_payments.csv")) == "yoco"


def test_clean_orders_handles_za_currency_and_missing_customer():
    _, frame = extract_orders(FIX / "pos_daily.csv")
    clean = clean_orders(frame)
    assert len(clean) == 4
    potjie = clean[clean["sku"] == "POT-3"].iloc[0]
    assert potjie["unit_price_cents"] == 89900
    assert potjie["discount_cents"] == 5000
    guest = clean[clean["source_order_id"] == "R-1003"].iloc[0]
    assert guest["customer_id"] is None


def test_pipeline_loads_star_schema_idempotently(tmp_path: Path):
    db = tmp_path / "reporting.db"
    a = run_file(FIX / "pos_daily.csv", db)
    b = run_file(FIX / "pos_daily.csv", db)  # second run must not duplicate
    assert a["rows_loaded"] == 4
    assert b["rows_loaded"] == 0

    run_file(FIX / "shopify_orders.csv", db)
    run_file(FIX / "yoco_payments.csv", db)

    conn = connect(db)
    sales = conn.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
    pays = conn.execute("SELECT COUNT(*) FROM fact_payments").fetchone()[0]
    products = conn.execute("SELECT COUNT(*) FROM dim_product").fetchone()[0]
    assert sales == 7  # 4 POS + 3 Shopify
    assert pays == 4
    assert products >= 6

    # Tea appears in both POS and Shopify — one product dimension row.
    tea = conn.execute("SELECT COUNT(*) FROM dim_product WHERE sku='TEA-ROOIBOS'").fetchone()[0]
    assert tea == 1

    rev = revenue_by_day(conn)
    assert rev[0][0] == "2026-10-01"
    assert rev[0][1] == 2 * 8900 + 13900 + (89900 - 5000)
    # Successful Yoco volume for the day
    yoco = conn.execute(
        "SELECT SUM(amount_cents) FROM fact_payments WHERE status='successful' AND date_key=20261001"
    ).fetchone()[0]
    assert yoco == 31700 + 84900

    runs = conn.execute("SELECT COUNT(*) FROM etl_runs WHERE status LIKE 'ok%'").fetchone()[0]
    assert runs == 4  # 2× pos + shopify + yoco
    conn.close()


def test_yoco_failed_payment_is_kept_with_status(tmp_path: Path):
    db = tmp_path / "p.db"
    run_file(FIX / "yoco_payments.csv", db)
    conn = sqlite3.connect(db)
    status = conn.execute("SELECT status FROM fact_payments WHERE source_payment_id='pay_04'").fetchone()[0]
    assert status == "failed"
