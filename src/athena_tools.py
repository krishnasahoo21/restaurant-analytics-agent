"""
athena_tools.py
---------------
All 14 agent tool functions backed by AWS Athena.

Drop-in replacement for tools.py — identical function signatures
and return dict shapes. Claude and the agent loop see no difference.

Key improvements over tools.py:
  - 13 months of data (Jul 2025 → May 2026) vs 2 months hardcoded
  - Cross-year queries supported via year parameter
  - New: get_discount_breakdown() for Q8/Q10 type questions
  - New: get_item_components() for combo/recipe questions
  - get_channel_performance() now handles cross-month comparison
    (replaces separate compare_channels_across_months tool)
  - get_top_items() now supports category filter

All tools:
  - Return error dict on failure, never raise exceptions
  - Accept month as name ("april") or number ("04")
  - Default year to "2026" for backward compatibility with eval tests
  - Use Athena for live data, MATERIAL_LOGIC/item_master for business logic

Tool Categories:
  1. Monthly Performance    — KPIs, categories, channels, discounts
  2. Menu Analysis          — top items, low performers
  3. Time Analysis          — daily trends, day patterns, peak hours
  4. Customer Analysis      — repeat customers
  5. Operations             — material requirements, raw ingredients
  6. Item Knowledge         — components, recipe lookup
"""

import json
import pandas as pd
from pathlib import Path
from typing import Optional

from src.athena_client import run_query, to_float, to_int, to_str


# ── Month name → number mapping ────────────────────────────────────────────
MONTH_MAP = {
    "january": "01",  "february": "02",  "march":     "03",
    "april":   "04",  "may":      "05",  "june":      "06",
    "july":    "07",  "august":   "08",  "september": "09",
    "october": "10",  "november": "11",  "december":  "12",
}

MONTH_NAME = {v: k.title() for k, v in MONTH_MAP.items()}


def _norm_month(month: str) -> str:
    """Converts month name or number to zero-padded string: 'april' → '04'"""
    m = month.strip().lower()
    return MONTH_MAP.get(m, m.zfill(2))


def _month_label(year: str, month_num: str) -> str:
    """Returns human readable label: '2026', '04' → 'April 2026'"""
    name = MONTH_NAME.get(month_num, month_num)
    return f"{name} {year}"


def _check_error(rows) -> Optional[dict]:
    """Returns error dict if query failed, None if results are usable."""
    if isinstance(rows, dict) and "error" in rows:
        return rows
    return None


# ── Business logic data (local for now, S3 in Phase 5) ────────────────────
# Imported here so tools can access MATERIAL_LOGIC and item_master data
# without re-loading on every call

_BUSINESS_LOGIC_LOADED = False
_MATERIAL_LOGIC  = {}
_RAW_INGREDIENTS = {}
_ITEM_MASTER_DF  = None


def _load_business_logic():
    """Loads MATERIAL_LOGIC, RAW_INGREDIENTS, and item_master once."""
    global _BUSINESS_LOGIC_LOADED, _MATERIAL_LOGIC, _RAW_INGREDIENTS
    global _ITEM_MASTER_DF

    if _BUSINESS_LOGIC_LOADED:
        return

    try:
        from src.data_loader import (
            MATERIAL_LOGIC,
            RAW_INGREDIENTS,
            load_item_master
        )
        _MATERIAL_LOGIC  = MATERIAL_LOGIC
        _RAW_INGREDIENTS = RAW_INGREDIENTS
        _ITEM_MASTER_DF  = load_item_master()
        _BUSINESS_LOGIC_LOADED = True
    except Exception as e:
        print(f"⚠️  Business logic load failed: {e}")


# ══════════════════════════════════════════════════════════════════════════
# CATEGORY 1 — MONTHLY PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════

def get_monthly_kpis(month: str, year: str = "2026") -> dict:
    """
    Returns key performance indicators for a specific month.

    Args:
        month: month name ("april") or number ("04")
        year:  4-digit year string (default "2026")

    Returns:
        dict with net_sales, total_orders, avg_order_value,
        total_discounts, discount_pct, total_items_sold,
        channel_split, category_split
    """
    month_num = _norm_month(month)

    rows = run_query(f"""
        SELECT
            net_sales,
            total_revenue,
            total_orders,
            avg_order_value,
            total_discounts,
            total_items_sold,
            channel_split,
            category_split
        FROM tunday_kababi.daily_sales
        WHERE year  = '{year}'
          AND month = '{month_num}'
    """)

    err = _check_error(rows)
    if err:
        return err
    if not rows:
        return {
            "error": (
                f"No data found for {month} {year}. "
                f"Available: Jul 2025 → May 2026"
            )
        }

    row           = rows[0]
    net_sales     = to_float(row["net_sales"])
    total_revenue = to_float(row["total_revenue"])
    total_disc    = to_float(row["total_discounts"])

    return {
        "month":            _month_label(year, month_num),
        "net_sales":        round(net_sales, 2),
        "total_revenue":    round(total_revenue, 2),
        "total_orders":     to_int(row["total_orders"]),
        "avg_order_value":  round(to_float(row["avg_order_value"]), 2),
        "total_discounts":  round(total_disc, 2),
        "discount_pct":     round(
            total_disc / total_revenue * 100, 2
        ) if total_revenue > 0 else 0,
        "total_items_sold": to_int(row["total_items_sold"]),
        "channel_split":    json.loads(row["channel_split"] or "{}"),
        "category_split":   json.loads(row["category_split"] or "{}"),
    }


def get_category_performance(
    month: str = "april",
    year:  str = "2026"
) -> dict:
    """
    Returns revenue and quantity breakdown by food category.

    Args:
        month: month name or number (default "april")
        year:  4-digit year string (default "2026")

    Returns:
        dict with categories list sorted by revenue,
        top_category, lowest_category
    """
    month_num = _norm_month(month)

    rows = run_query(f"""
        SELECT category_split
        FROM   tunday_kababi.daily_sales
        WHERE  year  = '{year}'
          AND  month = '{month_num}'
    """)

    err = _check_error(rows)
    if err:
        return err
    if not rows:
        return {"error": f"No data for {month} {year}"}

    cat_split = json.loads(rows[0]["category_split"] or "{}")
    total_rev = sum(v["revenue"] for v in cat_split.values())

    categories = sorted(
        [
            {
                "category":    cat,
                "items_sold":  vals["items"],
                "revenue":     vals["revenue"],
                "revenue_pct": round(
                    vals["revenue"] / total_rev * 100, 2
                ) if total_rev > 0 else 0
            }
            for cat, vals in cat_split.items()
        ],
        key=lambda x: x["revenue"],
        reverse=True
    )

    return {
        "month":           _month_label(year, month_num),
        "categories":      categories,
        "top_category":    categories[0]["category"] if categories else None,
        "lowest_category": categories[-1]["category"] if categories else None,
    }


def get_channel_performance(
    month:         str = "april",
    year:          str = "2026",
    compare_month: str = None,
    compare_year:  str = None,
) -> dict:
    """
    Returns performance by sales channel (Swiggy, Zomato, POS, Magic Pin).
    Optionally compares against a second month when compare_month is given.

    Args:
        month:         primary month to analyse
        year:          year for primary month (default "2026")
        compare_month: optional second month for comparison
        compare_year:  year for comparison month (default same as year)

    Returns:
        dict with channels list, top_channel, insights.
        If compare_month given: adds comparison dict with growth_pct per channel.

    Examples:
        get_channel_performance("april", "2026")
        get_channel_performance("april", "2026", compare_month="march")
    """
    month_num = _norm_month(month)

    def _fetch_channels(yr, mo):
        rows = run_query(f"""
            SELECT net_sales, channel_split
            FROM   tunday_kababi.daily_sales
            WHERE  year  = '{yr}'
              AND  month = '{mo}'
        """)
        if _check_error(rows) or not rows:
            return None, None
        net_sales    = to_float(rows[0]["net_sales"])
        channel_data = json.loads(rows[0]["channel_split"] or "{}")
        return net_sales, channel_data

    net_sales, channel_data = _fetch_channels(year, month_num)
    if channel_data is None:
        return {"error": f"No data for {month} {year}"}

    channels = sorted(
        [
            {
                "channel":         ch,
                "revenue":         vals["revenue"],
                "orders":          vals["orders"],
                "share_pct":       vals["share_pct"],
                "avg_order_value": round(
                    vals["revenue"] / vals["orders"], 2
                ) if vals["orders"] > 0 else 0
            }
            for ch, vals in channel_data.items()
        ],
        key=lambda x: x["revenue"],
        reverse=True
    )

    online_rev = sum(
        c["revenue"] for c in channels
        if c["channel"] in ("Swiggy", "Zomato")
    )
    online_pct = round(online_rev / net_sales * 100, 2) if net_sales else 0

    result = {
        "month":       _month_label(year, month_num),
        "channels":    channels,
        "top_channel": channels[0]["channel"] if channels else None,
        "insights": [
            f"{channels[0]['channel']} leads with "
            f"₹{channels[0]['revenue']:,} ({channels[0]['share_pct']}%)",
            f"Online (Swiggy + Zomato) = {online_pct}% of total revenue"
        ]
    }

    # ── Optional cross-month comparison ───────────────────────────────
    if compare_month:
        comp_month_num = _norm_month(compare_month)
        comp_year      = compare_year or year
        _, comp_data   = _fetch_channels(comp_year, comp_month_num)

        if comp_data:
            all_channels = set(channel_data.keys()) | set(comp_data.keys())
            comparison   = []

            for ch in sorted(all_channels):
                curr = channel_data.get(ch, {"revenue": 0, "orders": 0})
                prev = comp_data.get(ch,   {"revenue": 0, "orders": 0})
                rev_change = round(curr["revenue"] - prev["revenue"], 2)
                growth_pct = round(
                    (curr["revenue"] - prev["revenue"]) /
                    prev["revenue"] * 100, 2
                ) if prev["revenue"] > 0 else None

                comparison.append({
                    "channel":              ch,
                    "current_revenue":      curr["revenue"],
                    "comparison_revenue":   prev["revenue"],
                    "revenue_change":       rev_change,
                    "growth_pct":           growth_pct,
                    "current_orders":       curr["orders"],
                    "comparison_orders":    prev["orders"],
                    "trend": "🟢 grew" if rev_change > 0 else "🔴 declined"
                })

            result["comparison_month"] = _month_label(
                comp_year, comp_month_num
            )
            result["channel_comparison"] = sorted(
                comparison,
                key=lambda x: x["current_revenue"],
                reverse=True
            )

    return result


def get_discount_breakdown(
    month: str = "april",
    year:  str = "2026"
) -> dict:
    """
    Returns discount type breakdown for a month — which discount
    campaigns ran, how many orders used each, and total amounts.

    Useful for: discount strategy analysis, Swiggy vs other discount
    comparison, month-on-month discount change analysis.

    Args:
        month: month name or number
        year:  4-digit year string (default "2026")

    Returns:
        dict with total_discounts, discount_types list,
        swiggy_discount_total, avg_discount_per_order
    """
    month_num = _norm_month(month)

    # Discount detail lives in the channel_split and category_split
    # of daily_sales. For transaction-level discount types, we need
    # to query online_orders which has per-order discount amounts.
    rows = run_query(f"""
        SELECT
            order_source,
            COUNT(DISTINCT order_key)           AS orders,
            SUM(net_amount)                     AS net_revenue,
            SUM(net_amount + total_discount
                - packaging_charges)            AS gross_amount,
            SUM(total_discount)                 AS total_discount
        FROM tunday_kababi.online_orders
        WHERE year  = '{year}'
          AND month = '{month_num}'
        GROUP BY order_source
        ORDER BY total_discount DESC
    """)

    err = _check_error(rows)
    if err:
        return err
    if not rows:
        return {"error": f"No online order data for {month} {year}"}

    # Also get monthly total discounts from daily_sales for full picture
    kpi_rows = run_query(f"""
        SELECT total_discounts, total_revenue, net_sales
        FROM   tunday_kababi.daily_sales
        WHERE  year  = '{year}'
          AND  month = '{month_num}'
    """)

    total_disc   = 0
    total_rev    = 0
    if not _check_error(kpi_rows) and kpi_rows:
        total_disc = to_float(kpi_rows[0]["total_discounts"])
        total_rev  = to_float(kpi_rows[0]["total_revenue"])

    breakdown = []
    for row in rows:
        gross  = to_float(row["gross_amount"])
        disc   = to_float(row["total_discount"])
        orders = to_int(row["orders"])
        breakdown.append({
            "channel":              to_str(row["order_source"]),
            "orders":               orders,
            "net_revenue":          round(to_float(row["net_revenue"]), 2),
            "total_discount":       round(disc, 2),
            "avg_discount_order":   round(disc / orders, 2) if orders > 0 else 0,
            "discount_pct":         round(
                disc / gross * 100, 2
            ) if gross > 0 else 0,
        })

    online_disc = sum(b["total_discount"] for b in breakdown)

    return {
        "month":                   _month_label(year, month_num),
        "total_discounts_all":     round(total_disc, 2),
        "total_discounts_online":  round(online_disc, 2),
        "discount_pct_of_revenue": round(
            total_disc / total_rev * 100, 2
        ) if total_rev > 0 else 0,
        "by_channel":              breakdown,
        "note": (
            "Discounts are primarily Swiggy platform promotions. "
            "POS and Magic Pin orders typically carry zero discount."
        )
    }


# ══════════════════════════════════════════════════════════════════════════
# CATEGORY 2 — MENU ANALYSIS
# ══════════════════════════════════════════════════════════════════════════

def get_top_items(
    month:           str = "april",
    year:            str = "2026",
    n:               int = 10,
    sort_by:         str = "revenue",
    category_filter: str = None,
) -> dict:
    """
    Returns top selling menu items ranked by revenue or quantity.

    Args:
        month:           month name or number (default "april")
        year:            4-digit year string (default "2026")
        n:               number of items to return (default 10)
        sort_by:         "revenue" or "quantity" (default "revenue")
        category_filter: optional — filter to one category only
                         e.g. "Rolls", "Biryani", "Kabab and Roasted"
                         Use this when asked about best items within
                         a specific food category.

    Returns:
        dict with items list ranked by chosen metric
    """
    month_num  = _norm_month(month)
    sort_col   = "net_amount" if sort_by == "revenue" else "qty"
    cat_clause = (
        f"AND LOWER(category) = LOWER('{category_filter}')"
        if category_filter else ""
    )

    rows = run_query(f"""
        SELECT
            item_name,
            category,
            qty,
            amount,
            net_amount,
            percentage_of_sales
        FROM   tunday_kababi.menu_mix
        WHERE  year  = '{year}'
          AND  month = '{month_num}'
          {cat_clause}
        ORDER BY {sort_col} DESC
        LIMIT  {n}
    """)

    err = _check_error(rows)
    if err:
        return err
    if not rows:
        return {"error": f"No menu data for {month} {year}"}

    return {
        "month":   _month_label(year, month_num),
        "sort_by": sort_by,
        "category_filter": category_filter,
        "items": [
            {
                "rank":          i + 1,
                "item_name":     to_str(row["item_name"]),
                "category":      to_str(row["category"]),
                "quantity":      to_int(row["qty"]),
                "gross_revenue": round(to_float(row["amount"]), 2),
                "net_revenue":   round(to_float(row["net_amount"]), 2),
                "pct_of_sales":  round(
                    to_float(row["percentage_of_sales"]), 2
                ),
            }
            for i, row in enumerate(rows)
        ]
    }


def get_low_performing_items(
    month:             str   = "april",
    year:              str   = "2026",
    revenue_threshold: float = 5000,
    qty_threshold:     int   = 10,
) -> dict:
    """
    Identifies underperforming menu items with low sales or revenue.
    Use for menu optimisation, items to consider removing, slow movers.

    Args:
        month:             month name or number (default "april")
        year:              4-digit year string (default "2026")
        revenue_threshold: flag items below this net revenue (default ₹5000)
        qty_threshold:     flag items below this quantity (default 10)

    Returns:
        dict with low_revenue_items, low_qty_items, recommendation
    """
    month_num = _norm_month(month)

    low_rev_rows = run_query(f"""
        SELECT item_name, category, qty, net_amount
        FROM   tunday_kababi.menu_mix
        WHERE  year       = '{year}'
          AND  month      = '{month_num}'
          AND  net_amount < {revenue_threshold}
        ORDER BY net_amount ASC
    """)

    low_qty_rows = run_query(f"""
        SELECT item_name, category, qty, net_amount
        FROM   tunday_kababi.menu_mix
        WHERE  year  = '{year}'
          AND  month = '{month_num}'
          AND  qty   < {qty_threshold}
        ORDER BY qty ASC
    """)

    if _check_error(low_rev_rows):
        return low_rev_rows
    if _check_error(low_qty_rows):
        return low_qty_rows

    def _parse_rows(rows):
        return [
            {
                "item_name":  to_str(r["item_name"]),
                "category":   to_str(r["category"]),
                "quantity":   to_int(r["qty"]),
                "net_amount": round(to_float(r["net_amount"]), 2),
            }
            for r in (rows or [])
        ]

    low_rev = _parse_rows(low_rev_rows)
    low_qty = _parse_rows(low_qty_rows)

    return {
        "month":             _month_label(year, month_num),
        "revenue_threshold": revenue_threshold,
        "qty_threshold":     qty_threshold,
        "low_revenue_items": low_rev,
        "low_qty_items":     low_qty,
        "recommendation": (
            f"{len(low_rev)} items below ₹{revenue_threshold:,} revenue. "
            f"{len(low_qty)} items sold fewer than {qty_threshold} units. "
            f"Consider reviewing these for menu optimisation."
        )
    }


# ══════════════════════════════════════════════════════════════════════════
# CATEGORY 3 — TIME ANALYSIS
# ══════════════════════════════════════════════════════════════════════════

def get_daily_trends(
    month: str = "april",
    year:  str = "2026",
) -> dict:
    """
    Returns day-by-day revenue and quantity for a specific month.
    Use for identifying best/worst days, daily patterns, specific dates.

    Args:
        month: month name or number (default "april")
        year:  4-digit year string (default "2026")

    Returns:
        dict with daily list, best_day, worst_day, avg_daily_revenue
    """
    month_num = _norm_month(month)

    rows = run_query(f"""
        SELECT
            CAST(date AS VARCHAR)   AS date_str,
            day_of_week,
            day,
            SUM(quantity)           AS total_qty,
            SUM(revenue)            AS total_revenue
        FROM   tunday_kababi.item_wise
        WHERE  year  = '{year}'
          AND  month = '{month_num}'
        GROUP BY date, day_of_week, day
        ORDER BY date
    """)

    err = _check_error(rows)
    if err:
        return err
    if not rows:
        return {"error": f"No daily data for {month} {year}"}

    daily_list = [
        {
            "date":        to_str(row["date_str"])[:10],
            "day":         to_int(row["day"]),
            "day_of_week": to_str(row["day_of_week"]),
            "quantity":    to_int(row["total_qty"]),
            "revenue":     round(to_float(row["total_revenue"]), 2),
        }
        for row in rows
    ]

    best  = max(daily_list, key=lambda x: x["revenue"])
    worst = min(daily_list, key=lambda x: x["revenue"])
    avg   = round(
        sum(d["revenue"] for d in daily_list) / len(daily_list), 2
    )

    return {
        "month":               _month_label(year, month_num),
        "daily":               daily_list,
        "best_day":            best,
        "worst_day":           worst,
        "avg_daily_revenue":   avg,
        "total_days_analysed": len(daily_list),
    }


def get_day_of_week_analysis(
    month: str = None,
    year:  str = None,
) -> dict:
    """
    Analyses which days of the week perform best on average.
    Use for staffing planning, identifying weekend vs weekday patterns.

    Args:
        month: optional — filter to one month. If None, uses all data.
        year:  optional — filter to one year. If None, uses all data.

    Returns:
        dict with by_day list, best_day_of_week, worst_day_of_week
    """
    where_parts = []
    if year:
        where_parts.append(f"year = '{year}'")
    if month:
        where_parts.append(f"month = '{_norm_month(month)}'")

    where = "WHERE " + " AND ".join(where_parts) if where_parts else ""

    rows = run_query(f"""
        SELECT
            day_of_week,
            SUM(quantity)           AS total_quantity,
            SUM(revenue)            AS total_revenue,
            COUNT(DISTINCT date)    AS num_days
        FROM   tunday_kababi.item_wise
        {where}
        GROUP BY day_of_week
    """)

    err = _check_error(rows)
    if err:
        return err
    if not rows:
        return {"error": "No data found"}

    day_order = [
        "Monday","Tuesday","Wednesday","Thursday",
        "Friday","Saturday","Sunday"
    ]

    day_list = []
    for row in rows:
        num_days = to_int(row["num_days"])
        total_rev = to_float(row["total_revenue"])
        day_list.append({
            "day_of_week":       to_str(row["day_of_week"]),
            "total_revenue":     round(total_rev, 2),
            "avg_daily_revenue": round(
                total_rev / num_days, 2
            ) if num_days > 0 else 0,
            "total_quantity":    to_int(row["total_quantity"]),
            "occurrences":       num_days,
        })

    day_list.sort(
        key=lambda x: day_order.index(x["day_of_week"])
        if x["day_of_week"] in day_order else 99
    )

    best  = max(day_list, key=lambda x: x["avg_daily_revenue"])
    worst = min(day_list, key=lambda x: x["avg_daily_revenue"])

    return {
        "by_day":            day_list,
        "best_day_of_week":  best["day_of_week"],
        "worst_day_of_week": worst["day_of_week"],
        "period":            f"{year or 'all years'} {month or 'all months'}",
    }


def get_peak_hours(
    month: str = "april",
    year:  str = "2026",
) -> dict:
    """
    Analyses online order patterns by hour of day.
    Use for peak ordering times, staffing windows, kitchen scheduling.

    Args:
        month: month name or number (default "april")
        year:  4-digit year string (default "2026")

    Returns:
        dict with by_hour list, peak_hour, peak_window, quiet_hours
    """
    month_num = _norm_month(month)

    rows = run_query(f"""
        SELECT
            hour,
            COUNT(DISTINCT order_key)   AS orders,
            SUM(net_amount)             AS revenue
        FROM   tunday_kababi.online_orders
        WHERE  year  = '{year}'
          AND  month = '{month_num}'
          AND  hour  IS NOT NULL
        GROUP BY hour
        ORDER BY hour
    """)

    err = _check_error(rows)
    if err:
        return err
    if not rows:
        return {"error": f"No online order data for {month} {year}"}

    hour_list = [
        {
            "hour":        to_int(row["hour"]),
            "hour_label":  f"{to_int(row['hour']):02d}:00",
            "orders":      to_int(row["orders"]),
            "revenue":     round(to_float(row["revenue"]), 2),
        }
        for row in rows
    ]

    peak   = max(hour_list, key=lambda x: x["orders"])
    quiet  = [h for h in hour_list if h["orders"] < 5]

    # Find busiest 3-hour window
    max_window = 0
    peak_window_label = ""
    for i in range(len(hour_list) - 2):
        window = sum(hour_list[j]["orders"] for j in range(i, i + 3))
        if window > max_window:
            max_window = window
            peak_window_label = (
                f"{hour_list[i]['hour_label']} – "
                f"{hour_list[i+2]['hour_label']}"
            )

    return {
        "month":        _month_label(year, month_num),
        "by_hour":      hour_list,
        "peak_hour":    peak["hour_label"],
        "peak_window":  peak_window_label,
        "quiet_hours":  [h["hour_label"] for h in quiet],
    }


def get_item_daily_sales(
    item_name: str,
    month:     str = "april",
    year:      str = "2026",
    threshold: int = 0,
) -> dict:
    """
    Returns day-by-day sales quantity for a specific menu item.
    Supports partial name matching — "Tunday Mutton" finds all variants.

    Use for: daily performance of specific item, how many days above
    a threshold, best/worst days for a dish, item-level daily trends,
    production planning for a specific item.

    Args:
        item_name: full or partial item name (case insensitive)
        month:     month name or number (default "april")
        year:      4-digit year string (default "2026")
        threshold: count days where qty exceeded this (default 0)

    Returns:
        dict with matched_items, daily list, days_above_threshold,
        peak_day, total_qty
    """
    month_num  = _norm_month(month)
    search     = item_name.strip().lower().replace("'", "''")

    rows = run_query(f"""
        SELECT
            item_name,
            CAST(date AS VARCHAR)   AS date_str,
            day_of_week,
            SUM(quantity)           AS total_qty,
            SUM(revenue)            AS total_revenue
        FROM   tunday_kababi.item_wise
        WHERE  year              = '{year}'
          AND  month             = '{month_num}'
          AND  LOWER(item_name) LIKE '%{search}%'
        GROUP BY item_name, date, day_of_week
        ORDER BY date
    """)

    err = _check_error(rows)
    if err:
        return err
    if not rows:
        return {
            "error":  f"No item found matching '{item_name}' "
                      f"in {month} {year}",
        }

    matched_names = list({to_str(r["item_name"]) for r in rows})

    # Aggregate across all matched variants by date
    from collections import defaultdict
    by_date = defaultdict(lambda: {"quantity": 0, "revenue": 0.0,
                                    "day_of_week": ""})
    for row in rows:
        date_key = to_str(row["date_str"])[:10]
        by_date[date_key]["quantity"]   += to_int(row["total_qty"])
        by_date[date_key]["revenue"]    += to_float(row["total_revenue"])
        by_date[date_key]["day_of_week"] = to_str(row["day_of_week"])

    daily_list = [
        {
            "date":        date,
            "day_of_week": vals["day_of_week"],
            "quantity":    vals["quantity"],
            "revenue":     round(vals["revenue"], 2),
        }
        for date, vals in sorted(by_date.items())
    ]

    days_above = [d for d in daily_list if d["quantity"] > threshold]
    peak       = max(daily_list, key=lambda x: x["quantity"])

    return {
        "search_term":          item_name,
        "matched_items":        matched_names,
        "month":                _month_label(year, month_num),
        "threshold":            threshold,
        "daily":                daily_list,
        "days_above_threshold": len(days_above),
        "days_above_details":   days_above,
        "peak_day":             peak,
        "total_qty":            sum(d["quantity"] for d in daily_list),
        "total_days_analysed":  len(daily_list),
    }


# ══════════════════════════════════════════════════════════════════════════
# CATEGORY 4 — CUSTOMER ANALYSIS
# ══════════════════════════════════════════════════════════════════════════

def get_repeat_customers(
    month:      str = "april",
    year:       str = "2026",
    min_orders: int = 2,
) -> dict:
    """
    Identifies customers who ordered more than once in a given month.
    Use for customer loyalty analysis, repeat rate, most valuable customers.

    Args:
        month:      month name or number (default "april")
        year:       4-digit year string (default "2026")
        min_orders: minimum orders to qualify as repeat (default 2)

    Returns:
        dict with repeat_customers list, repeat_rate_pct, top_customer
    """
    month_num = _norm_month(month)

    rows = run_query(f"""
        SELECT
            customer_name,
            COUNT(DISTINCT order_key)   AS order_count,
            SUM(net_amount)             AS total_spent
        FROM   tunday_kababi.online_orders
        WHERE  year  = '{year}'
          AND  month = '{month_num}'
        GROUP BY customer_name
        HAVING COUNT(DISTINCT order_key) >= {min_orders}
        ORDER BY order_count DESC, total_spent DESC
    """)

    total_rows = run_query(f"""
        SELECT COUNT(DISTINCT customer_name) AS total_customers
        FROM   tunday_kababi.online_orders
        WHERE  year  = '{year}'
          AND  month = '{month_num}'
    """)

    if _check_error(rows):
        return rows

    repeat_list = [
        {
            "customer_name": to_str(r["customer_name"]),
            "order_count":   to_int(r["order_count"]),
            "total_spent":   round(to_float(r["total_spent"]), 2),
        }
        for r in (rows or [])
    ]

    total_customers = (
        to_int(total_rows[0]["total_customers"])
        if not _check_error(total_rows) and total_rows
        else 0
    )
    repeat_rate = round(
        len(repeat_list) / total_customers * 100, 2
    ) if total_customers > 0 else 0

    return {
        "month":                   _month_label(year, month_num),
        "repeat_customers":        repeat_list,
        "total_repeat_customers":  len(repeat_list),
        "total_unique_customers":  total_customers,
        "repeat_rate_pct":         repeat_rate,
        "top_customer":            repeat_list[0] if repeat_list else None,
    }


# ══════════════════════════════════════════════════════════════════════════
# CATEGORY 5 — OPERATIONS
# ══════════════════════════════════════════════════════════════════════════

def get_material_requirements(
    month: str = "april",
    year:  str = "2026",
) -> dict:
    """
    Returns prepared dish quantities (KG) needed based on monthly sales.
    Use for kitchen planning, prep scheduling, production targets.

    Args:
        month: month name or number (default "april")
        year:  4-digit year string (default "2026")

    Returns:
        dict with materials list (material, piece_qty, kgs),
        highest_demand material
    """
    _load_business_logic()
    month_num = _norm_month(month)

    # Get item-level quantities from Athena
    rows = run_query(f"""
        SELECT
            LOWER(item_name)    AS item_name_lower,
            SUM(qty)            AS total_qty
        FROM   tunday_kababi.menu_mix
        WHERE  year  = '{year}'
          AND  month = '{month_num}'
        GROUP BY LOWER(item_name)
    """)

    err = _check_error(rows)
    if err:
        return err
    if not rows:
        return {"error": f"No menu data for {month} {year}"}

    sales_dict = {
        to_str(r["item_name_lower"]): to_float(r["total_qty"])
        for r in rows
    }

    # Apply MATERIAL_LOGIC business rules
    output = {}
    for material, logic in _MATERIAL_LOGIC.items():
        total_pieces = 0
        for item, multiplier in logic["items"].items():
            total_pieces += sales_dict.get(item.strip().lower(), 0) * multiplier
        kgs = round(total_pieces / logic["conversion"], 2)
        if kgs > 0:
            output[material] = {
                "piece_quantity": round(total_pieces, 2),
                "kgs":           kgs
            }

    material_list = sorted(
        [
            {
                "material":      mat,
                "piece_quantity": vals["piece_quantity"],
                "kgs":           vals["kgs"],
            }
            for mat, vals in output.items()
        ],
        key=lambda x: x["kgs"],
        reverse=True
    )

    return {
        "month":           _month_label(year, month_num),
        "materials":       material_list,
        "total_materials": len(material_list),
        "highest_demand":  material_list[0]["material"] if material_list else None,
    }


def get_raw_ingredients(
    month: str = "april",
    year:  str = "2026",
) -> dict:
    """
    Returns raw ingredient quantities (KG) needed for procurement.
    Derived from material requirements using recipe ratios.
    Use for purchasing decisions, stock planning, supplier orders.

    Args:
        month: month name or number (default "april")
        year:  4-digit year string (default "2026")

    Returns:
        dict with ingredients list (ingredient, qty_kg),
        highest_demand ingredient
    """
    _load_business_logic()

    # Get material requirements first
    materials_result = get_material_requirements(month, year)
    if "error" in materials_result:
        return materials_result

    prepared_kgs = {
        m["material"]: m["kgs"]
        for m in materials_result["materials"]
    }

    # Apply RAW_INGREDIENTS recipes
    from collections import defaultdict
    raw_totals = defaultdict(float)

    for item, amount in prepared_kgs.items():
        recipe = _RAW_INGREDIENTS.get(item.lower())
        if not recipe:
            continue
        yield_kg   = recipe["yield"]
        multiplier = amount / yield_kg if yield_kg > 0 else 0
        for ingredient, qty in recipe.items():
            if ingredient == "yield":
                continue
            raw_totals[ingredient] += qty * multiplier

    ingredient_list = sorted(
        [
            {"ingredient": ing, "qty_kg": round(qty, 3)}
            for ing, qty in raw_totals.items()
            if qty > 0
        ],
        key=lambda x: x["qty_kg"],
        reverse=True
    )

    return {
        "month":              materials_result["month"],
        "ingredients":        ingredient_list,
        "total_ingredients":  len(ingredient_list),
        "highest_demand":     ingredient_list[0]["ingredient"]
                              if ingredient_list else None,
    }


# ══════════════════════════════════════════════════════════════════════════
# CATEGORY 6 — ITEM KNOWLEDGE
# ══════════════════════════════════════════════════════════════════════════

def get_item_components(item_name: str) -> dict:
    """
    Returns the base components of a menu item — useful for combo
    and bundle items that are made up of multiple base dishes.

    Also shows which other menu items share the same base component
    (e.g. all items that use Tunday Mutton Galawati Kabab).

    Use for: understanding combo contents, production planning,
    calculating total pieces of a base item across all SKUs,
    answering "what goes into X" questions.

    Args:
        item_name: full or partial item name (case insensitive)

    Returns:
        dict with matched_item, components list,
        also_used_in (other items sharing same base components),
        material_logic (piece count per SKU for production calculation)
    """
    _load_business_logic()

    search = item_name.strip().lower()

    # ── Search item_master for item components ─────────────────────────
    item_components = {}
    if _ITEM_MASTER_DF is not None and not _ITEM_MASTER_DF.empty:
        df = _ITEM_MASTER_DF
        mask = df["item_name"].str.lower().str.contains(search, regex=False)
        matched = df[mask]

        if not matched.empty:
            for _, row in matched.iterrows():
                name = row["item_name"]
                breakdown = row.get("breakdown", None)
                item_components[name] = {
                    "item_name":      name,
                    "shelf_life_days": row.get("shelf_life_days", None),
                    "is_combo":       row.get("is_combo", False),
                    "base_item":      row.get("base_item_name", None),
                    "breakdown":      breakdown,
                }

    # ── Search MATERIAL_LOGIC for production piece counts ──────────────
    material_usage = {}
    for material, logic in _MATERIAL_LOGIC.items():
        for sku, pieces in logic["items"].items():
            if search in sku.lower():
                material_usage[material] = material_usage.get(
                    material, []
                )
                material_usage[material].append({
                    "sku":            sku,
                    "pieces_per_sku": pieces,
                    "conversion_per_kg": logic["conversion"],
                })

    # ── Also find which materials use this item as a component ────────
    also_used_in = []
    for material, logic in _MATERIAL_LOGIC.items():
        if search in material.lower():
            skus = [
                {"sku": sku, "pieces": pieces}
                for sku, pieces in logic["items"].items()
            ]
            also_used_in.append({
                "base_material":     material,
                "conversion_per_kg": logic["conversion"],
                "used_in_skus":      skus,
            })

    if not item_components and not material_usage and not also_used_in:
        return {
            "error": f"No item found matching '{item_name}'. "
                     f"Try a partial name like 'Galawati' or 'Biryani'."
        }

    return {
        "search_term":    item_name,
        "item_master":    list(item_components.values()),
        "material_logic": material_usage,
        "also_used_in":   also_used_in,
        "note": (
            "material_logic shows piece counts per SKU for production "
            "planning. also_used_in shows all SKUs that contain this "
            "item as a base component."
        )
    }
