"""
filename_parser.py
-------------------
Extracts year, month, and report_type from any POS export filename.
Handles both old and new naming conventions used by the client's
POS system across Jul 2025 - May 2026.
"""

import re


def parse_filename(filename: str) -> dict:
    """
    Extracts metadata from a POS export filename.

    Args:
        filename: the raw filename (with or without path)

    Returns:
        dict with keys: year, month, report_type, period_start

    Raises:
        ValueError: if report_type or date cannot be determined
    """
    # Strip any path, work with just the filename
    fname = filename.split("/")[-1]
    fname_lower = fname.lower()

    # ── Step 1: Detect report type from filename ───────────────────────
    if "menu_mix" in fname_lower or "menu mix" in fname_lower:
        report_type = "menu-mix"
    elif "item_wise" in fname_lower or "item wise" in fname_lower:
        report_type = "item-wise"
    elif "online_orders" in fname_lower or "online order" in fname_lower:
        report_type = "online-orders"
    elif "daily_sales" in fname_lower or "daily sales" in fname_lower:
        report_type = "daily-sales"
    else:
        raise ValueError(f"Cannot determine report_type from filename: {fname}")

    # ── Step 2: Extract period start date ───────────────────────────────
    # Three known date patterns in the wild:
    #   (2025.07.01--2025.07.31)        YYYY.MM.DD  (year-first, 4-digit year)
    #   (2026-04-01 -- 2026-04-30)      YYYY-MM-DD  (year-first, 4-digit year)
    #   Report01.04.2026-30.04.20261    DD.MM.YYYY  (day-first, CSV special case)
    #
    # IMPORTANT: We anchor on a 4-DIGIT YEAR to disambiguate. Without this,
    # a day-first pattern like "01.04.2026" can be mismatched against a
    # year-first regex and silently produce garbage (e.g. reading "30" as
    # a month). We try year-first FIRST since it's unambiguous (4 digits
    # only appear in the year position), then fall back to day-first.

    # Pattern A: YYYY.MM.DD or YYYY-MM-DD or YYYY_MM_DD — 4-digit year first.
    # The separator must be IDENTICAL across both gaps (use a backreference),
    # otherwise the regex can stitch together fragments from two different
    # dates sitting next to each other in the filename (e.g. "...2026-30.04"
    # from "01.04.2026-30.04.2026" — wrong: mixes '-' and '.' across dates).
    pattern_year_first = r'(?<!\d)(\d{4})([.\-_])(\d{2})\2(\d{2})(?!\d)'
    match = re.search(pattern_year_first, fname)

    if match:
        year, _, month, day = match.groups()
        return {
            "year": year,
            "month": month,
            "report_type": report_type,
            "period_start": f"{year}-{month}-{day}"
        }

    # Pattern B: DD.MM.YYYY or DD_MM_YYYY — day-first, only checked if
    # year-first failed. Matches both:
    #   "01.04.2026-30.04.20261"   (dot separator, original CSV)
    #   "01_04_2026-30_04_20261"   (underscore separator, actual S3 filename)
    # We take the FIRST match (= period start), not the second (= period end).
    pattern_day_first = r'(?<!\d)(\d{2})[._](\d{2})[._](\d{4})(?!\d)'
    match = re.search(pattern_day_first, fname)

    if match:
        day, month, year = match.groups()
        return {
            "year": year,
            "month": month,
            "report_type": report_type,
            "period_start": f"{year}-{month}-{day}"
        }

    raise ValueError(f"Cannot extract date from filename: {fname}")
