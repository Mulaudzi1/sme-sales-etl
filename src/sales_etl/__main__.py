from __future__ import annotations

import argparse
import json
from pathlib import Path

from sales_etl.pipeline import run_file, run_paths


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Load POS / Yoco / Shopify-style exports into a reporting SQLite database.")
    p.add_argument("inputs", nargs="+", type=Path, help="CSV/Excel export files")
    p.add_argument("--db", type=Path, default=Path("reporting.db"))
    p.add_argument("--kind", choices=["pos_csv", "shopify", "yoco", "payments"], default=None,
                   help="Force source system (otherwise auto-detected from filename/columns)")
    args = p.parse_args(argv)
    if args.kind and len(args.inputs) == 1:
        result = [run_file(args.inputs[0], args.db, kind=args.kind)]
    else:
        result = run_paths(args.inputs, args.db)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
