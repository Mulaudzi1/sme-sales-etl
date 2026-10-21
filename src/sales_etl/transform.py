from __future__ import annotations

from datetime import datetime

import pandas as pd

from sales_etl.money import to_cents


def parse_when(value) -> datetime:
    if pd.isna(value):
        raise ValueError("missing timestamp")
    if isinstance(value, datetime):
        return value
    ts = pd.to_datetime(value, utc=True, dayfirst=False)
    if pd.isna(ts):
        raise ValueError(f"bad timestamp {value!r}")
    return ts.to_pydatetime()


def date_key(dt: datetime) -> int:
    return int(dt.strftime("%Y%m%d"))


def clean_orders(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    errors = []
    for i, r in df.iterrows():
        try:
            if pd.isna(r.get("order_id")) or pd.isna(r.get("sku")) and pd.isna(r.get("product_name")):
                raise ValueError("order_id and sku/product_name are required")
            when = parse_when(r["ordered_at"])
            qty = float(r["qty"]) if not pd.isna(r.get("qty")) else 1.0
            if qty == 0:
                continue
            unit = to_cents(r["unit_price"]) if not pd.isna(r.get("unit_price")) else None
            discount = to_cents(r["discount"]) if not pd.isna(r.get("discount")) else 0
            tax = to_cents(r["tax"]) if not pd.isna(r.get("tax")) else 0
            if unit is None:
                if pd.isna(r.get("line_total")):
                    raise ValueError("need unit_price or line_total")
                line_total = to_cents(r["line_total"])
                unit = int(round(line_total / qty)) if qty else line_total
            else:
                # SA POS prices are usually VAT-inclusive; the tax column is the VAT portion, not an add-on.
                line_total = int(round(unit * qty)) - discount
                if not pd.isna(r.get("line_total")):
                    line_total = to_cents(r["line_total"])
            sku = str(r["sku"]).strip() if not pd.isna(r.get("sku")) else f"NAME-{str(r['product_name']).strip().lower().replace(' ', '-')[:40]}"
            line_id = f"{r['order_id']}:{sku}:{i}"
            cust_id = str(r["customer_id"]).strip() if not pd.isna(r.get("customer_id")) else (
                str(r["email"]).strip().lower() if not pd.isna(r.get("email")) else None
            )
            rows.append({
                "source_system": r["source_system"],
                "source_order_id": str(r["order_id"]).strip(),
                "line_id": line_id,
                "ordered_at": when,
                "date_key": date_key(when),
                "customer_id": cust_id,
                "customer_name": None if pd.isna(r.get("customer_name")) else str(r["customer_name"]).strip(),
                "email": None if pd.isna(r.get("email")) else str(r["email"]).strip().lower(),
                "phone": None if pd.isna(r.get("phone")) else str(r["phone"]).strip(),
                "city": None if pd.isna(r.get("city")) else str(r["city"]).strip(),
                "sku": sku,
                "product_name": str(r["product_name"]).strip() if not pd.isna(r.get("product_name")) else sku,
                "category": None if pd.isna(r.get("category")) else str(r["category"]).strip(),
                "qty": qty,
                "unit_price_cents": unit,
                "discount_cents": discount,
                "tax_cents": tax,
                "line_total_cents": line_total,
                "currency": (str(r["currency"]).strip().upper() if not pd.isna(r.get("currency")) else "ZAR"),
            })
        except Exception as e:  # noqa: BLE001 — collect row errors for the run report
            errors.append({"row": int(i) if isinstance(i, int) else str(i), "error": str(e)})
    out = pd.DataFrame(rows)
    out.attrs["errors"] = errors
    return out


def clean_payments(df: pd.DataFrame) -> pd.DataFrame:
    rows, errors = [], []
    for i, r in df.iterrows():
        try:
            if pd.isna(r.get("payment_id")) or pd.isna(r.get("amount")):
                raise ValueError("payment_id and amount are required")
            when = parse_when(r["paid_at"])
            amount = to_cents(r["amount"])
            fee = abs(to_cents(r["fee"])) if not pd.isna(r.get("fee")) else 0
            net = to_cents(r["net"]) if not pd.isna(r.get("net")) else amount - fee
            status = str(r["status"]).strip().lower() if not pd.isna(r.get("status")) else "successful"
            # Yoco uses "successful"; normalise a few variants.
            if status in {"success", "complete", "completed", "paid"}:
                status = "successful"
            cust_id = str(r["email"]).strip().lower() if not pd.isna(r.get("email")) else None
            rows.append({
                "source_system": r["source_system"],
                "source_payment_id": str(r["payment_id"]).strip(),
                "paid_at": when,
                "date_key": date_key(when),
                "customer_id": cust_id,
                "customer_name": None if pd.isna(r.get("customer_name")) else str(r["customer_name"]).strip(),
                "email": cust_id,
                "amount_cents": amount,
                "fee_cents": fee,
                "net_cents": net,
                "method": None if pd.isna(r.get("method")) else str(r["method"]).strip(),
                "status": status,
                "currency": (str(r["currency"]).strip().upper() if not pd.isna(r.get("currency")) else "ZAR"),
                "order_ref": None if pd.isna(r.get("order_ref")) else str(r["order_ref"]).strip(),
            })
        except Exception as e:  # noqa: BLE001
            errors.append({"row": int(i) if isinstance(i, int) else str(i), "error": str(e)})
    out = pd.DataFrame(rows)
    out.attrs["errors"] = errors
    return out
