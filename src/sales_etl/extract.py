from __future__ import annotations

from pathlib import Path

import pandas as pd

# Column aliases we accept from messy POS / export files.
ORDER_ALIASES = {
    "order_id": ["order_id", "order id", "order number", "order_number", "id", "name", "receipt", "receipt_number"],
    "ordered_at": ["ordered_at", "order_date", "created_at", "date", "datetime", "paid_at", "timestamp"],
    "customer_id": ["customer_id", "customer id", "cust_id", "client_id"],
    "customer_name": ["customer_name", "customer", "client", "buyer", "name_customer"],
    "email": ["email", "customer_email", "email_address"],
    "phone": ["phone", "customer_phone", "mobile", "cell"],
    "city": ["city", "billing_city", "shipping_city"],
    "sku": ["sku", "product_id", "variant_id", "item_code", "barcode"],
    "product_name": ["product_name", "product", "title", "item", "description", "lineitem_name"],
    "category": ["category", "product_type", "type"],
    "qty": ["qty", "quantity", "lineitem_quantity", "units"],
    "unit_price": ["unit_price", "price", "unit price", "lineitem_price", "amount"],
    "discount": ["discount", "lineitem_discount", "discount_amount"],
    "tax": ["tax", "vat", "lineitem_tax", "tax_amount"],
    "line_total": ["line_total", "total", "lineitem_total", "gross"],
    "currency": ["currency", "currency_code"],
}

PAYMENT_ALIASES = {
    "payment_id": ["payment_id", "id", "transaction_id", "checkout_id"],
    "paid_at": ["paid_at", "created_at", "date", "datetime", "timestamp"],
    "amount": ["amount", "gross", "amount_gross", "total"],
    "fee": ["fee", "amount_fee", "fees", "processing_fee"],
    "net": ["net", "amount_net", "net_amount"],
    "method": ["method", "payment_method", "card_brand", "type"],
    "status": ["status", "payment_status", "state"],
    "order_ref": ["order_ref", "order_id", "m_payment_id", "reference", "metadata_order"],
    "customer_name": ["customer_name", "name", "payer"],
    "email": ["email", "customer_email"],
    "currency": ["currency", "currency_code"],
}


def _norm(col: str) -> str:
    return col.strip().lower().replace("-", "_").replace(" ", "_")


def remap(df: pd.DataFrame, aliases: dict[str, list[str]]) -> pd.DataFrame:
    lookup = {_norm(c): c for c in df.columns}
    out = pd.DataFrame(index=df.index)
    for dest, options in aliases.items():
        for opt in options:
            key = _norm(opt)
            if key in lookup:
                out[dest] = df[lookup[key]]
                break
        else:
            out[dest] = pd.NA
    return out


def read_table(path: Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    # Sniff delimiter: Shopify exports are commas; some POS dumps are semicolons.
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    sep = ";" if sample.count(";") > sample.count(",") else ","
    return pd.read_csv(path, sep=sep)


def detect_source(path: Path, df: pd.DataFrame) -> str:
    name = path.name.lower()
    cols = {_norm(c) for c in df.columns}
    if "yoco" in name or {"checkout_id", "amount_fee"} & cols or ("fee" in cols and "status" in cols and "payment" in name):
        return "yoco"
    if "shopify" in name or {"lineitem_name", "lineitem_quantity", "lineitem_price"} & cols:
        return "shopify"
    if {"sku", "qty"} <= cols or {"product", "quantity"} <= {_norm(c) for c in df.columns}:
        return "pos_csv"
    # Fallback: payments-shaped vs orders-shaped.
    if {"amount", "status"} <= cols and "sku" not in cols:
        return "yoco"
    return "pos_csv"


def extract_orders(path: Path, source: str | None = None) -> tuple[str, pd.DataFrame]:
    raw = read_table(path)
    source = source or detect_source(path, raw)
    if source == "yoco":
        raise ValueError(f"{path} looks like a Yoco payments export; use the payments loader.")
    df = remap(raw, ORDER_ALIASES)
    df["source_system"] = source
    df["source_path"] = str(path)
    return source, df


def extract_payments(path: Path, source: str | None = None) -> tuple[str, pd.DataFrame]:
    raw = read_table(path)
    source = source or detect_source(path, raw)
    if source not in {"yoco", "payments"}:
        # Still try — user may have forced it.
        source = "yoco"
    df = remap(raw, PAYMENT_ALIASES)
    df["source_system"] = source
    df["source_path"] = str(path)
    return source, df
