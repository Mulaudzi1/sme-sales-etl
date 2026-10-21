from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def to_cents(value) -> int:
    """Accepts 12.5, 'R 1 234,56', '1,234.56', '1234' → integer cents."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        raise ValueError("amount is missing")
    if isinstance(value, (int,)):
        return int(value) * 100 if abs(value) < 10_000_000 else int(value)  # bare rands vs already-cents heuristic avoided; ints are rands
    if isinstance(value, float):
        return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    s = str(value).strip()
    s = re.sub(r"[Rr]|ZAR|\s", "", s)
    if not s:
        raise ValueError("amount is empty")
    # 1.234,56 or 1234,56 → European
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # 1234,56 → decimal; 1,234 → thousands (no cents)
        if re.search(r",\d{2}$", s):
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    try:
        return int((Decimal(s) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation as e:
        raise ValueError(f"bad amount {value!r}") from e
