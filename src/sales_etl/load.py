from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from sales_etl.schema import DDL


def connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(DDL)
    return conn


def _upsert_date(conn: sqlite3.Connection, dt: datetime) -> int:
    key = int(dt.strftime("%Y%m%d"))
    conn.execute(
        """INSERT OR IGNORE INTO dim_date (date_key, date, year, month, day, weekday, week)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (key, dt.date().isoformat(), dt.year, dt.month, dt.day, dt.strftime("%A"), int(dt.strftime("%V"))),
    )
    return key


def _upsert_customer(conn: sqlite3.Connection, *, customer_id: str | None, name, email, phone, city, source: str) -> int | None:
    if not customer_id:
        return None
    conn.execute(
        """INSERT INTO dim_customer (customer_id, name, email, phone, city, source_system)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(customer_id) DO UPDATE SET
             name=COALESCE(excluded.name, dim_customer.name),
             email=COALESCE(excluded.email, dim_customer.email),
             phone=COALESCE(excluded.phone, dim_customer.phone),
             city=COALESCE(excluded.city, dim_customer.city)""",
        (customer_id, name, email, phone, city, source),
    )
    return conn.execute("SELECT customer_key FROM dim_customer WHERE customer_id = ?", (customer_id,)).fetchone()[0]


def _upsert_product(conn: sqlite3.Connection, *, sku: str, name: str, category, source: str) -> int:
    conn.execute(
        """INSERT INTO dim_product (sku, name, category, source_system)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(sku) DO UPDATE SET
             name=excluded.name,
             category=COALESCE(excluded.category, dim_product.category)""",
        (sku, name, category, source),
    )
    return conn.execute("SELECT product_key FROM dim_product WHERE sku = ?", (sku,)).fetchone()[0]


def load_orders(conn: sqlite3.Connection, clean: pd.DataFrame) -> int:
    loaded = 0
    for r in clean.to_dict(orient="records"):
        _upsert_date(conn, r["ordered_at"])
        cust = _upsert_customer(
            conn, customer_id=r["customer_id"], name=r["customer_name"], email=r["email"],
            phone=r["phone"], city=r["city"], source=r["source_system"],
        )
        prod = _upsert_product(conn, sku=r["sku"], name=r["product_name"], category=r["category"], source=r["source_system"])
        cur = conn.execute(
            """INSERT OR IGNORE INTO fact_sales
               (source_system, source_order_id, line_id, date_key, customer_key, product_key,
                qty, unit_price_cents, discount_cents, tax_cents, line_total_cents, currency)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r["source_system"], r["source_order_id"], r["line_id"], r["date_key"], cust, prod,
             r["qty"], r["unit_price_cents"], r["discount_cents"], r["tax_cents"], r["line_total_cents"], r["currency"]),
        )
        loaded += cur.rowcount
    return loaded


def load_payments(conn: sqlite3.Connection, clean: pd.DataFrame) -> int:
    loaded = 0
    for r in clean.to_dict(orient="records"):
        _upsert_date(conn, r["paid_at"])
        cust = _upsert_customer(
            conn, customer_id=r["customer_id"], name=r["customer_name"], email=r["email"],
            phone=None, city=None, source=r["source_system"],
        )
        cur = conn.execute(
            """INSERT OR IGNORE INTO fact_payments
               (source_system, source_payment_id, date_key, customer_key, amount_cents, fee_cents,
                net_cents, method, status, currency, order_ref)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r["source_system"], r["source_payment_id"], r["date_key"], cust, r["amount_cents"], r["fee_cents"],
             r["net_cents"], r["method"], r["status"], r["currency"], r["order_ref"]),
        )
        loaded += cur.rowcount
    return loaded


def record_run(conn: sqlite3.Connection, *, source: str, path: str, rows_in: int, rows_loaded: int, status: str, message: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO etl_runs (started_at, finished_at, source_system, input_path, rows_in, rows_loaded, status, message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (now, now, source, path, rows_in, rows_loaded, status, message),
    )


def revenue_by_day(conn: sqlite3.Connection) -> list[tuple]:
    return conn.execute(
        """SELECT d.date, SUM(f.line_total_cents) AS revenue_cents, COUNT(DISTINCT f.source_order_id) AS orders
           FROM fact_sales f JOIN dim_date d ON d.date_key = f.date_key
           GROUP BY d.date ORDER BY d.date"""
    ).fetchall()
