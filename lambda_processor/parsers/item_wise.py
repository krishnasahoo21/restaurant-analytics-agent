"""
parsers/item_wise.py
---------------------
Parses the Item Wise Enterprise report — daily sales quantity
and revenue for every menu item across the month.

FORMAT: Consistent across ALL 13 months (Apr 2025 - Apr 2026).
No version detection needed.

File structure (confirmed against Jul 2025 and Apr 2026):
    Row 0:  Report title
    Row 1:  Generated On timestamp
    Row 2:  blank
    Row 3:  "CONSOLIDATED WISE"
    Row 4:  blank
    Row 5:  Date headers — ('S.No', 'Item', 'Jul 01,2025', None, 'Jul 02,2025'...)
            Dates appear every 2 columns starting from col 2.
            None between dates is the Amt column placeholder.
    Row 6:  Qty/Amt subheaders — (None, None, 'Qty', 'Amt', 'Qty', 'Amt'...)
    Row 7+: Item data rows — (S.No, item_name, qty1, amt1, qty2, amt2...)
    Last:   'Grand Total:' row — stop here

Wide format → Long format transformation:
    Input:  one row per item, one pair of columns per day
    Output: one row per (item, date) where quantity > 0

This is the same logic as load_item_wise_sales() in data_loader.py,
generalised to accept any month's file.

Output DataFrame columns:
    item_name, date, quantity, revenue, day_of_week, day
"""

import pandas as pd
from datetime import datetime


def parse_item_wise(filepath: str, year: str, month: str) -> pd.DataFrame:
    """
    Parses an Item Wise Enterprise xlsx file into long-format DataFrame.

    Args:
        filepath: local path to the downloaded xlsx file
        year:     4-digit year string from filename_parser (e.g. "2025")
        month:    2-digit month string from filename_parser (e.g. "07")

    Returns:
        Long-format DataFrame with columns:
        item_name, date, quantity, revenue, day_of_week, day
        One row per (item, day) where quantity > 0.
    """
    # Use pandas with header=None since row structure is irregular
    df_raw = pd.read_excel(filepath, header=None)

    all_rows = df_raw.values.tolist()

    # ── Step 1: Find the date header row dynamically ───────────────────
    # Don't hardcode Row 5 — the number of metadata rows above the header
    # varies across months (confirmed: Nov 2025, Dec 2025, Apr 2026 differ).
    #
    # Reliable anchor: the header row always has 'S.No' in col 0 and
    # 'Item' in col 1, with date strings starting from col 2.
    # Search all rows for this pattern instead of assuming a fixed index.
    date_row_idx = None
    for i, row in enumerate(all_rows):
        col0 = str(row[0]).strip() if row[0] is not None else ""
        col1 = str(row[1]).strip() if row[1] is not None else ""
        if col0 == "S.No" and col1 == "Item":
            date_row_idx = i
            break

    if date_row_idx is None:
        raise ValueError(
            f"Could not find header row (S.No / Item) in {filepath}. "
            f"File structure may have changed significantly."
        )

    date_row = all_rows[date_row_idx]

    # Two date formats found across 13 months of real data:
    #   "Jul 01,2025"  — format "%b %d,%Y" (Jul 2025 → Oct 2025)
    #   "01-Nov-2025"  — format "%d-%b-%Y" (Nov 2025 onward)
    # Try both formats for each cell — whichever parses wins.
    DATE_FORMATS = ["%b %d,%Y", "%d-%b-%Y"]

    dates = []
    date_col_indices = []

    for col_idx, val in enumerate(date_row[2:], start=2):
        if val is not None and str(val).strip() not in ('', 'nan'):
            val_str = str(val).strip()
            parsed_date = None

            for fmt in DATE_FORMATS:
                try:
                    parsed_date = pd.to_datetime(val_str, format=fmt)
                    break   # stop trying formats once one works
                except (ValueError, TypeError):
                    continue

            if parsed_date is not None and pd.notna(parsed_date):
                dates.append(parsed_date)
                date_col_indices.append(col_idx)

    if not dates:
        raise ValueError(
            f"No dates found in header row {date_row_idx} of {filepath}. "
            f"Row content: {date_row[:6]}. "
            f"Formats tried: {DATE_FORMATS}"
        )

    # ── Step 2: Extract item rows ──────────────────────────────────────
    # Data starts 2 rows after the date header:
    #   date_row_idx + 0 = date header (S.No, Item, Jul 01,2025...)
    #   date_row_idx + 1 = Qty/Amt subheaders
    #   date_row_idx + 2 = first item data row
    # Last row is "Grand Total:" — skip it.
    item_rows = df_raw.iloc[date_row_idx + 2:-1]

    # ── Step 3: Wide → Long transformation ────────────────────────────
    records = []

    for _, row in item_rows.iterrows():
        item_name = str(row.iloc[1]).strip()

        # Skip blank rows, header repetitions, Grand Total
        if not item_name or item_name.lower() in ("nan", "grand total:", "item"):
            continue

        for date, qty_col in zip(dates, date_col_indices):
            amt_col = qty_col + 1   # Amount always immediately follows Qty

            qty = row.iloc[qty_col]
            amt = row.iloc[amt_col]

            # Only record days where something was actually sold
            try:
                qty_val = float(qty)
            except (TypeError, ValueError):
                continue

            if pd.notna(qty) and qty_val > 0:
                records.append({
                    "item_name": item_name,
                    "date":      date,
                    "quantity":  int(qty_val),
                    "revenue":   float(amt) if pd.notna(amt) else 0.0
                })

    if not records:
        raise ValueError(
            f"No sales records found in {filepath}. "
            f"Check that item rows exist between row 7 and the Grand Total."
        )

    # ── Step 4: Build DataFrame, add derived columns ──────────────────
    df = pd.DataFrame(records)
    df["day_of_week"] = df["date"].dt.day_name()
    df["day"]         = df["date"].dt.day

    return df.reset_index(drop=True)
