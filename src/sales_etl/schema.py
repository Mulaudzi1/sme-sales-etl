"""Reporting-ready star schema for SME sales analytics."""
from __future__ import annotations

DDL = """
CREATE TABLE IF NOT EXISTS dim_date (
  date_key INTEGER PRIMARY KEY,  -- YYYYMMDD
  date TEXT NOT NULL,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  day INTEGER NOT NULL,
  weekday TEXT NOT NULL,
  week INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS dim_customer (
  customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id TEXT NOT NULL UNIQUE,
  name TEXT,
  email TEXT,
  phone TEXT,
  city TEXT,
  source_system TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dim_product (
  product_key INTEGER PRIMARY KEY AUTOINCREMENT,
  sku TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  category TEXT,
  source_system TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fact_sales (
  sale_key INTEGER PRIMARY KEY AUTOINCREMENT,
  source_system TEXT NOT NULL,
  source_order_id TEXT NOT NULL,
  line_id TEXT NOT NULL,
  date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
  customer_key INTEGER REFERENCES dim_customer(customer_key),
  product_key INTEGER NOT NULL REFERENCES dim_product(product_key),
  qty REAL NOT NULL,
  unit_price_cents INTEGER NOT NULL,
  discount_cents INTEGER NOT NULL DEFAULT 0,
  tax_cents INTEGER NOT NULL DEFAULT 0,
  line_total_cents INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'ZAR',
  UNIQUE (source_system, source_order_id, line_id)
);
CREATE TABLE IF NOT EXISTS fact_payments (
  payment_key INTEGER PRIMARY KEY AUTOINCREMENT,
  source_system TEXT NOT NULL,
  source_payment_id TEXT NOT NULL UNIQUE,
  date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
  customer_key INTEGER REFERENCES dim_customer(customer_key),
  amount_cents INTEGER NOT NULL,
  fee_cents INTEGER NOT NULL DEFAULT 0,
  net_cents INTEGER NOT NULL,
  method TEXT,
  status TEXT NOT NULL,
  currency TEXT NOT NULL DEFAULT 'ZAR',
  order_ref TEXT
);
CREATE TABLE IF NOT EXISTS etl_runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  source_system TEXT NOT NULL,
  input_path TEXT NOT NULL,
  rows_in INTEGER NOT NULL,
  rows_loaded INTEGER NOT NULL,
  status TEXT NOT NULL,
  message TEXT
);
"""
