"""
parsers/daily_sales.py
------------------------
Parses the "Daily Sales" report — despite the name, this is actually a
MONTHLY KPI SUMMARY, not day-by-day data. No daily breakdown exists in
this file; it's the same kind of data you previously hardcoded in
data_loader.py's load_monthly_summary() for March and April.

Handles TWO format variants found in the client's 12 months of data:

  v1 (xlsx, Jul 2025 - Mar 2026):
      Row 0: restaurant name
      Row 2: report title
      KPI block starts around row 7

  v2 (xlsx, Apr 2026+, "Daily_Sales_Summary_Detailed_Report..."):
      Row 1: "DEPLOYMENT" + restaurant name (no separating space)
      Row 2: "Period From ... To ..."
      KPI block starts around row 4
      Adds a new channel: "Magic Pin"
      Adds "Item Discount" as a separate line above Subtotal Discount

DESIGN DECISION: rather than hardcoding row numbers (which shift between
versions), this parser searches for known SECTION LABELS in column 0
(e.g. "Net Sales", "Order Type", "Super Category Tracking"). These labels
are IDENTICAL text across both format versions — only their row position
changes. Label-based search means this parser works for both versions
without needing version detection at all, and is more resilient to
future format drift than offset-based parsing.

Output: a single standardised dict per month:
    {
        "net_sales": float,
        "total_revenue": float,
        "total_orders": int,            # = total Checks across order types
        "avg_order_value": float,
        "total_discounts": float,
        "total_items_sold": int,
        "channel_split": {channel: {"revenue", "orders", "share_pct"}},
        "category_split": {category: {"items", "revenue"}},
    }
"""

import openpyxl


def _row_index_by_label(all_rows: list, label: str, col: int = 0) -> int:
    """
    Finds the row index where the given column contains an exact label.
    Returns None if not found.
    """
    for i, row in enumerate(all_rows):
        if row[col] is not None and str(row[col]).strip() == label:
            return i
    return None


def _parse_section_table(all_rows: list, header_label: str, label_is_header: bool = False) -> list:
    """
    Parses a labelled section table into a list of row dicts.

    This report uses TWO different section layouts:

      Layout A (label_is_header=False) — used by "Super Category Tracking",
      "Section Tracking", "Collection Break-up":
          Row N:    [Section Label]                  <- label alone, rest blank
          Row N+1:  [col_name_1, col_name_2, ...]     <- separate header row
          Row N+2..:[value_1, value_2, ...]           <- data rows

      Layout B (label_is_header=True) — used by "Order Type", "Order Source":
          Row N:    [Order Type, Net Sales, % Of Total, Checks, ...]
                    ^ the label IS column 0's header; rest of row N is
                      also header text (column names), not section title
          Row N+1..:[Online Delivery, 282752.59, 82.0, ..., 374, ...]

    Both layouts stop at a blank first-cell row or a "Total" row.

    Args:
        all_rows:        full sheet as list of row tuples
        header_label:    section label text to search for in column 0
        label_is_header: True for Layout B, False (default) for Layout A
    """
    section_start = _row_index_by_label(all_rows, header_label)
    if section_start is None:
        return []

    if label_is_header:
        # Row N itself contains the column headers (col 0 = the label
        # we searched for, e.g. "Order Type", which doubles as a header)
        headers = [str(h).strip() if h is not None else "" for h in all_rows[section_start]]
        data_start = section_start + 1
    else:
        # Row N is just the label; Row N+1 has the real headers
        header_row = all_rows[section_start + 1]
        headers = [str(h).strip() if h is not None else "" for h in header_row]
        data_start = section_start + 2

    records = []
    i = data_start
    while i < len(all_rows):
        row = all_rows[i]
        first_cell = row[0]

        # Stop at blank row or "Total" row
        if first_cell is None:
            break
        if str(first_cell).strip() == "Total":
            break

        row_dict = dict(zip(headers, row))
        # Also keep raw positional values — dict(zip(headers, row)) silently
        # collapses duplicate header names (e.g. "% Of Total" appears 3x
        # in Order Type/Order Source tables) to the last occurrence, which
        # loses data. Callers needing a specific duplicated-name column
        # must index _row_values positionally instead of by name.
        row_dict["_row_values"] = list(row)
        records.append(row_dict)
        i += 1

    return records


def parse_daily_sales(filepath: str) -> dict:
    """
    Main entry point — parses a Daily Sales (monthly KPI summary) report.
    Works for both v1 (old) and v2 (new) format via label-based search.

    Args:
        filepath: local path to the downloaded xlsx file

    Returns:
        dict with monthly KPI summary, channel_split, and category_split
        (same shape as data_loader.py's load_monthly_summary() entries)
    """
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    all_rows = list(ws.iter_rows(values_only=True))
    wb.close()

    # ── Top-level KPIs ───────────────────────────────────────────────────
    net_sales_row   = all_rows[_row_index_by_label(all_rows, "Net Sales")]
    revenue_row     = all_rows[_row_index_by_label(all_rows, "Total Revenue")]
    discounts_row   = all_rows[_row_index_by_label(all_rows, "Total Discounts")]

    net_sales      = float(net_sales_row[1])
    total_revenue  = float(revenue_row[1])
    total_discounts = float(discounts_row[1])

    # ── Order Type section → total checks = total_orders ───────────────
    order_type_rows = _parse_section_table(all_rows, "Order Type", label_is_header=True)
    total_orders = sum(int(r.get("Checks", 0) or 0) for r in order_type_rows)

    avg_order_value = round(net_sales / total_orders, 2) if total_orders > 0 else 0

    # ── Order Source section → channel_split ────────────────────────────
    # This section has the per-platform breakdown we need (Swiggy/Zomato/
    # POS/Magic Pin), unlike Order Type which is delivery-mode based.
    # NOTE: label_is_header=True means the channel name itself is the
    # value under the "Order Source" key (since that label doubles as
    # the column-0 header), not a separate field.
    order_source_rows = _parse_section_table(all_rows, "Order Source", label_is_header=True)

    channel_split = {}
    for r in order_source_rows:
        channel = r.get("Order Source")
        if channel is None:
            continue
        revenue = float(r.get("Net Sales", 0) or 0)
        orders  = int(r.get("Checks", 0) or 0)
        # NOTE: "% Of Total" appears THREE times in this table's headers
        # (revenue %, guest %, checks %). dict(zip(headers, row)) silently
        # collapses duplicate keys to the LAST occurrence — which is the
        # Tables % column (always 0), not the revenue share % we want.
        # We must read it positionally instead: it's always the column
        # immediately after "Net Sales" (index 2, right after Order
        # Source=0 and Net Sales=1).
        share = float(r.get("_row_values", [0, 0, 0])[2] or 0)
        channel_split[channel] = {
            "revenue": revenue,
            "orders": orders,
            "share_pct": share
        }

    # ── Super Category Tracking → category_split ────────────────────────
    category_rows = _parse_section_table(all_rows, "Super Category Tracking")

    category_split = {}
    total_items_sold = 0
    for r in category_rows:
        category = r.get("Particulars")
        # Skip non-category rows mixed into this section
        # (Service Charge, GST@5% appear here too)
        if category in (None, "Service Charge") or "GST" in str(category):
            continue
        items   = int(float(r.get("Items", 0) or 0))
        revenue = float(r.get("Amount", 0) or 0)
        category_split[category] = {"items": items, "revenue": revenue}
        total_items_sold += items

    return {
        "net_sales":         round(net_sales, 2),
        "total_revenue":     round(total_revenue, 2),
        "total_orders":      total_orders,
        "avg_order_value":   avg_order_value,
        "total_discounts":   round(total_discounts, 2),
        "total_items_sold":  total_items_sold,
        "channel_split":     channel_split,
        "category_split":    category_split,
    }
