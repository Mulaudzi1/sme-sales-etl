from __future__ import annotations

import json
from pathlib import Path

from sales_etl.extract import detect_source, extract_orders, extract_payments, read_table
from sales_etl.load import connect, load_orders, load_payments, record_run, revenue_by_day
from sales_etl.transform import clean_orders, clean_payments


def run_file(path: Path, db_path: Path, *, kind: str | None = None) -> dict:
    path = Path(path)
    raw = read_table(path)
    source = kind or detect_source(path, raw)
    conn = connect(db_path)
    try:
        if source == "yoco" or kind == "payments":
            source, frame = extract_payments(path, source="yoco")
            clean = clean_payments(frame)
            loaded = load_payments(conn, clean)
        else:
            source, frame = extract_orders(path, source=source)
            clean = clean_orders(frame)
            loaded = load_orders(conn, clean)
        errors = clean.attrs.get("errors", [])
        status = "ok" if not errors else "ok_with_row_errors"
        record_run(conn, source=source, path=str(path), rows_in=len(frame), rows_loaded=loaded,
                   status=status, message=json.dumps(errors[:20]))
        conn.commit()
        return {
            "source": source, "rows_in": len(frame), "rows_loaded": loaded,
            "row_errors": len(errors), "db": str(db_path),
            "revenue_by_day": [{"date": d, "revenue_cents": r, "orders": o} for d, r, o in revenue_by_day(conn)],
        }
    finally:
        conn.close()


def run_paths(paths: list[Path], db_path: Path) -> list[dict]:
    return [run_file(p, db_path) for p in paths]
