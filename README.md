# sme-sales-etl

A small ETL that turns everyday South African sales exports into a reporting-ready SQLite star schema.

Supported inputs (auto-detected from the filename and columns, or forced with `--kind`):

| Source | Typical file | What we load |
|---|---|---|
| **POS CSV** | till / Lightspeed / Xero-style line export | `fact_sales` + customer/product dims |
| **Shopify-style** | Admin order CSV (`Lineitem *` columns) | same sales facts |
| **Yoco** | payments / settlements CSV | `fact_payments` (gross, fee, net, status) |

## Star schema

```
dim_date ──┐
dim_customer ──┼── fact_sales
dim_product ───┘

dim_date ──┐
dim_customer ── fact_payments
```

Money is stored as **integer cents**. SA POS prices are treated as **VAT-inclusive**; a `tax`/`vat` column is kept for reporting but not added on top of the line total. Re-runs are idempotent (`INSERT OR IGNORE` on natural keys).

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python -m sales_etl samples/pos_daily.csv samples/shopify_orders.csv samples/yoco_payments.csv --db reporting.db
```

```bash
docker compose run --rm sme-sales-etl
# writes /data/reporting.db inside the volume
```

Example analytics after a load:

```sql
SELECT d.date, SUM(f.line_total_cents)/100.0 AS revenue_zar, COUNT(DISTINCT f.source_order_id) AS orders
FROM fact_sales f JOIN dim_date d USING (date_key)
GROUP BY 1 ORDER BY 1;

SELECT status, COUNT(*), SUM(amount_cents)/100.0, SUM(fee_cents)/100.0
FROM fact_payments GROUP BY 1;
```

## Layout

```
src/sales_etl/
  extract.py     read CSV/Excel, remap messy column names, detect source
  transform.py   validate rows, parse ZA amounts, build clean frames
  load.py        upsert dimensions + facts, etl_runs audit
  pipeline.py    one-file orchestration
  schema.py      DDL
samples/         POS, Shopify and Yoco fixtures (same as the tests)
```

## Licence

MIT. See [LICENSE](LICENSE).
