"""
tools.py
--------
All agent tool functions for the restaurant analytics agent.

These functions are called by Claude when answering user questions.
Each tool:
    - Takes simple parameters (strings, ints)
    - Queries the in-memory data loaded by data_loader.py
    - Returns a clean dictionary Claude can reason over
    - Never raises exceptions — returns error dict instead

Tool Categories:
    1. Sales Performance    — KPIs, revenue, order metrics
    2. Menu Analysis        — top items, category performance
    3. Channel Analysis     — Swiggy vs Zomato vs POS
    4. Time Analysis        — daily trends, peak hours, day of week
    5. Customer Analysis    — repeat customers, loyalty
    6. Operations           — material requirements, raw ingredients
"""

import pandas as pd
from typing import Optional


# ── Module-level data store ────────────────────────────────────────────────
# Data is loaded once and reused across all tool calls
# This avoids reloading Excel files on every question
_data: dict = {}


def initialise_tools(data: dict) -> None:
    """
    Load data into the tools module.
    Must be called once before any tool is used.

    Args:
        data: output of load_all_data() from data_loader.py
    """
    global _data
    _data = data
    print(f"✅ Tools initialised with "
          f"{data['metadata']['menu_mix_items']} menu items, "
          f"{data['metadata']['online_order_records']} order lines")


def _check_data() -> Optional[dict]:
    """
    Internal helper — checks data is loaded before tool runs.
    Returns error dict if not loaded, None if all good.
    """
    if not _data:
        return {"error": "Data not initialised. Call initialise_tools() first."}
    return None


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 1 — SALES PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════

def get_monthly_kpis(month: str) -> dict:
    """
    Returns key performance indicators for a given month.

    Args:
        month: "march" or "april" (case insensitive)

    Returns:
        dict with keys:
        - month: full month name
        - net_sales: total net sales in INR
        - total_revenue: gross revenue in INR
        - total_orders: number of orders
        - avg_order_value: average order value in INR
        - total_discounts: total discounts given in INR
        - discount_pct: discounts as % of gross revenue
        - total_items_sold: total items sold
    """
    err = _check_data()
    if err:
        return err

    month = month.strip().lower()
    summary = _data.get("monthly_summary", {})

    if month not in summary:
        return {
            "error": f"Month '{month}' not found. "
                     f"Available months: {list(summary.keys())}"
        }

    s = summary[month]
    return {
        "month":            s["month"],
        "net_sales":        s["net_sales"],
        "total_revenue":    s["total_revenue"],
        "total_orders":     s["total_orders"],
        "avg_order_value":  s["avg_order_value"],
        "total_discounts":  s["total_discounts"],
        "discount_pct":     round(
            s["total_discounts"] / s["total_revenue"] * 100, 2
        ),
        "total_items_sold": s["total_items_sold"]
    }


def compare_months() -> dict:
    """
    Compares March and April 2026 performance side by side.
    Calculates month-on-month growth for all key metrics.

    Returns:
        dict with keys:
        - march: March KPIs
        - april: April KPIs
        - growth: dict of metric → growth percentage
        - insights: list of key observations
    """
    err = _check_data()
    if err:
        return err

    march = _data["monthly_summary"]["march"]
    april = _data["monthly_summary"]["april"]

    def growth_pct(old, new):
        if old == 0:
            return 0
        return round((new - old) / old * 100, 2)

    growth = {
        "net_sales":       growth_pct(march["net_sales"],       april["net_sales"]),
        "total_orders":    growth_pct(march["total_orders"],    april["total_orders"]),
        "avg_order_value": growth_pct(march["avg_order_value"], april["avg_order_value"]),
        "total_discounts": growth_pct(march["total_discounts"], april["total_discounts"]),
        "items_sold":      growth_pct(march["total_items_sold"],april["total_items_sold"]),
    }

    # ── Auto-generate insights ─────────────────────────────────────────────
    insights = []

    if growth["net_sales"] > 0:
        insights.append(
            f"Revenue grew {growth['net_sales']}% MoM "
            f"(₹{march['net_sales']:,} → ₹{april['net_sales']:,})"
        )
    if growth["total_discounts"] < 0:
        insights.append(
            f"Discounting reduced by {abs(growth['total_discounts'])}% — "
            f"positive margin signal"
        )
    if growth["avg_order_value"] > 0:
        insights.append(
            f"Average order value increased by ₹"
            f"{round(april['avg_order_value'] - march['avg_order_value'], 2)} "
            f"({growth['avg_order_value']}% growth)"
        )

    return {
        "march":    march,
        "april":    april,
        "growth":   growth,
        "insights": insights
    }


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 2 — MENU ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def get_top_items(
    n:       int = 10,
    sort_by: str = "revenue"
) -> dict:
    """
    Returns top selling menu items from the April menu mix report.

    Args:
        n:       number of top items to return (default 10)
        sort_by: "revenue" or "quantity" (default "revenue")

    Returns:
        dict with keys:
        - sort_by: what metric was used for ranking
        - items: list of dicts with item_name, category,
                 qty, revenue, net_amount, pct_of_sales
    """
    err = _check_data()
    if err:
        return err

    df = _data.get("menu_mix_report", pd.DataFrame())
    if df.empty:
        return {"error": "Menu mix report not available"}

    sort_col = "net_amount" if sort_by == "revenue" else "qty"
    top = (
        df[["item_name", "category", "qty", "amount",
            "net_amount", "percentage_of_sales"]]
        .sort_values(sort_col, ascending=False)
        .head(n)
    )

    return {
        "sort_by": sort_by,
        "items": [
            {
                "rank":           i + 1,
                "item_name":      row["item_name"],
                "category":       row["category"],
                "quantity":       int(row["qty"]),
                "gross_revenue":  round(row["amount"], 2),
                "net_revenue":    round(row["net_amount"], 2),
                "pct_of_sales":   round(row["percentage_of_sales"], 2)
            }
            for i, (_, row) in enumerate(top.iterrows())
        ]
    }


def get_category_performance(month: str = "april") -> dict:
    """
    Returns revenue and quantity breakdown by food category.

    Args:
        month: "march" or "april" (default "april")

    Returns:
        dict with keys:
        - month: month name
        - categories: list of dicts sorted by revenue
        - top_category: highest revenue category
        - lowest_category: lowest revenue category
    """
    err = _check_data()
    if err:
        return err

    month = month.strip().lower()
    summary = _data.get("monthly_summary", {})

    if month not in summary:
        return {"error": f"Month '{month}' not available"}

    cat_split = summary[month]["category_split"]

    categories = sorted(
        [
            {
                "category": cat,
                "items_sold": vals["items"],
                "revenue":    vals["revenue"],
                "revenue_pct": round(
                    vals["revenue"] /
                    sum(v["revenue"] for v in cat_split.values()) * 100, 2
                )
            }
            for cat, vals in cat_split.items()
        ],
        key=lambda x: x["revenue"],
        reverse=True
    )

    return {
        "month":            summary[month]["month"],
        "categories":       categories,
        "top_category":     categories[0]["category"],
        "lowest_category":  categories[-1]["category"]
    }


def get_low_performing_items(
    revenue_threshold: float = 5000,
    qty_threshold:     int   = 10
) -> dict:
    """
    Identifies underperforming menu items — low sales candidates
    for menu optimisation or removal.

    Args:
        revenue_threshold: items below this net revenue flagged (default ₹5000)
        qty_threshold:     items below this quantity flagged (default 10)

    Returns:
        dict with keys:
        - low_revenue_items: items below revenue threshold
        - low_qty_items: items below quantity threshold
        - recommendation: summary observation
    """
    err = _check_data()
    if err:
        return err

    df = _data.get("menu_mix_report", pd.DataFrame())
    if df.empty:
        return {"error": "Menu mix report not available"}

    low_rev = df[df["net_amount"] < revenue_threshold][
        ["item_name", "category", "qty", "net_amount"]
    ].sort_values("net_amount").to_dict("records")

    low_qty = df[df["qty"] < qty_threshold][
        ["item_name", "category", "qty", "net_amount"]
    ].sort_values("qty").to_dict("records")

    return {
        "revenue_threshold": revenue_threshold,
        "qty_threshold":     qty_threshold,
        "low_revenue_items": low_rev,
        "low_qty_items":     low_qty,
        "recommendation": (
            f"{len(low_rev)} items below ₹{revenue_threshold} revenue. "
            f"{len(low_qty)} items sold fewer than {qty_threshold} units. "
            f"Consider reviewing these for menu optimisation."
        )
    }


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 3 — CHANNEL ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def get_channel_performance(month: str = "april") -> dict:
    """
    Returns performance breakdown by sales channel
    (Swiggy, Zomato, POS/TakeAway).

    Args:
        month: "march" or "april" (default "april")

    Returns:
        dict with keys:
        - month: month name
        - channels: list of channel dicts sorted by revenue
        - top_channel: highest revenue channel
        - insights: key observations about channel mix
    """
    err = _check_data()
    if err:
        return err

    month = month.strip().lower()
    summary = _data.get("monthly_summary", {})

    if month not in summary:
        return {"error": f"Month '{month}' not available"}

    s           = summary[month]
    channel_data = s["channel_split"]
    total_rev   = s["net_sales"]

    channels = sorted(
        [
            {
                "channel":    ch,
                "revenue":    vals["revenue"],
                "orders":     vals["orders"],
                "share_pct":  vals["share_pct"],
                "avg_order_value": round(
                    vals["revenue"] / vals["orders"], 2
                ) if vals["orders"] > 0 else 0
            }
            for ch, vals in channel_data.items()
        ],
        key=lambda x: x["revenue"],
        reverse=True
    )

    insights = []
    top = channels[0]
    insights.append(
        f"{top['channel']} leads with "
        f"₹{top['revenue']:,} ({top['share_pct']}% of sales)"
    )

    # Flag if online vs offline split is notable
    online_rev = sum(
        c["revenue"] for c in channels
        if c["channel"] in ["Swiggy", "Zomato"]
    )
    online_pct = round(online_rev / total_rev * 100, 2)
    insights.append(
        f"Online channels (Swiggy + Zomato) = "
        f"{online_pct}% of total revenue"
    )

    return {
        "month":       s["month"],
        "channels":    channels,
        "top_channel": top["channel"],
        "insights":    insights
    }


def compare_channels_across_months() -> dict:
    """
    Compares channel performance between March and April.
    Shows which channels grew or declined.

    Returns:
        dict with channel-by-channel MoM comparison
    """
    err = _check_data()
    if err:
        return err

    march_channels = _data["monthly_summary"]["march"]["channel_split"]
    april_channels = _data["monthly_summary"]["april"]["channel_split"]

    all_channels = set(march_channels.keys()) | set(april_channels.keys())

    comparison = []
    for ch in sorted(all_channels):
        mar = march_channels.get(ch, {"revenue": 0, "orders": 0})
        apr = april_channels.get(ch, {"revenue": 0, "orders": 0})

        rev_change = round(apr["revenue"] - mar["revenue"], 2)
        rev_growth = round(
            (apr["revenue"] - mar["revenue"]) /
            mar["revenue"] * 100, 2
        ) if mar["revenue"] > 0 else None

        comparison.append({
            "channel":        ch,
            "march_revenue":  mar["revenue"],
            "april_revenue":  apr["revenue"],
            "revenue_change": rev_change,
            "growth_pct":     rev_growth,
            "march_orders":   mar["orders"],
            "april_orders":   apr["orders"],
            "trend":          "🟢 grew" if rev_change > 0 else "🔴 declined"
        })

    return {
        "comparison": sorted(
            comparison, key=lambda x: x["april_revenue"], reverse=True
        )
    }


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 4 — TIME ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def get_daily_trends() -> dict:
    """
    Returns day-by-day revenue and quantity for April 2026.
    Useful for identifying best/worst days and weekly patterns.

    Returns:
        dict with keys:
        - daily: list of {date, day, day_of_week, quantity, revenue}
        - best_day: highest revenue day
        - worst_day: lowest revenue day
        - avg_daily_revenue: average revenue per day
    """
    err = _check_data()
    if err:
        return err

    df = _data.get("item_wise_sales", pd.DataFrame())
    if df.empty:
        return {"error": "Item wise sales data not available"}

    daily = (
        df.groupby(["date", "day", "day_of_week"])
        .agg(quantity=("quantity", "sum"), revenue=("revenue", "sum"))
        .reset_index()
        .sort_values("date")
    )

    daily_list = [
        {
            "date":        row["date"].strftime("%d-%b-%Y"),
            "day":         int(row["day"]),
            "day_of_week": row["day_of_week"],
            "quantity":    int(row["quantity"]),
            "revenue":     round(row["revenue"], 2)
        }
        for _, row in daily.iterrows()
    ]

    best  = max(daily_list, key=lambda x: x["revenue"])
    worst = min(daily_list, key=lambda x: x["revenue"])

    return {
        "daily":               daily_list,
        "best_day":            best,
        "worst_day":           worst,
        "avg_daily_revenue":   round(daily["revenue"].mean(), 2),
        "total_days_analysed": len(daily_list)
    }


def get_day_of_week_analysis() -> dict:
    """
    Aggregates sales by day of week to identify
    which weekdays consistently perform best.

    Returns:
        dict with keys:
        - by_day: revenue and orders per day of week
        - best_day_of_week: consistently highest revenue day
        - worst_day_of_week: consistently lowest revenue day
    """
    err = _check_data()
    if err:
        return err

    df = _data.get("item_wise_sales", pd.DataFrame())
    if df.empty:
        return {"error": "Item wise sales data not available"}

    # Order days correctly Mon-Sun
    day_order = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday"
    ]

    by_day = (
        df.groupby("day_of_week")
        .agg(
            total_revenue  = ("revenue",  "sum"),
            total_quantity = ("quantity", "sum"),
            num_days       = ("date",     "nunique")
        )
        .reset_index()
    )

    by_day["avg_daily_revenue"] = round(
        by_day["total_revenue"] / by_day["num_days"], 2
    )
    by_day["day_order"] = by_day["day_of_week"].map(
        {d: i for i, d in enumerate(day_order)}
    )
    by_day = by_day.sort_values("day_order")

    day_list = [
        {
            "day_of_week":       row["day_of_week"],
            "total_revenue":     round(row["total_revenue"], 2),
            "avg_daily_revenue": row["avg_daily_revenue"],
            "total_quantity":    int(row["total_quantity"]),
            "occurrences":       int(row["num_days"])
        }
        for _, row in by_day.iterrows()
    ]

    best  = max(day_list, key=lambda x: x["avg_daily_revenue"])
    worst = min(day_list, key=lambda x: x["avg_daily_revenue"])

    return {
        "by_day":              day_list,
        "best_day_of_week":    best["day_of_week"],
        "worst_day_of_week":   worst["day_of_week"]
    }


def get_peak_hours() -> dict:
    """
    Analyses online order patterns by hour of day.
    Identifies peak ordering windows for staffing/prep planning.

    Returns:
        dict with keys:
        - by_hour: orders and revenue per hour
        - peak_hour: busiest hour
        - peak_window: busiest 3-hour window
        - quiet_hours: hours with fewer than 5 orders
    """
    err = _check_data()
    if err:
        return err

    df = _data.get("online_orders", pd.DataFrame())
    if df.empty:
        return {"error": "Online orders data not available"}

    by_hour = (
        df.groupby("hour")
        .agg(
            orders  = ("order_key", "nunique"),
            revenue = ("net_amount", "sum")
        )
        .reset_index()
        .sort_values("hour")
    )

    hour_list = [
        {
            "hour":        int(row["hour"]),
            "hour_label":  f"{int(row['hour']):02d}:00",
            "orders":      int(row["orders"]),
            "revenue":     round(row["revenue"], 2)
        }
        for _, row in by_hour.iterrows()
    ]

    peak       = max(hour_list, key=lambda x: x["orders"])
    quiet      = [h for h in hour_list if h["orders"] < 5]

    # Find peak 3-hour window
    max_window_orders = 0
    peak_window_label = ""
    for i in range(len(hour_list) - 2):
        window_orders = sum(
            hour_list[j]["orders"] for j in range(i, i + 3)
        )
        if window_orders > max_window_orders:
            max_window_orders = window_orders
            peak_window_label = (
                f"{hour_list[i]['hour_label']} – "
                f"{hour_list[i+2]['hour_label']}"
            )

    return {
        "by_hour":      hour_list,
        "peak_hour":    peak["hour_label"],
        "peak_window":  peak_window_label,
        "quiet_hours":  [h["hour_label"] for h in quiet]
    }


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 5 — CUSTOMER ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def get_repeat_customers(min_orders: int = 2) -> dict:
    """
    Identifies customers who ordered more than once in April.

    Args:
        min_orders: minimum number of orders to qualify (default 2)

    Returns:
        dict with keys:
        - repeat_customers: list of customers with order count
        - total_repeat_customers: count
        - total_unique_customers: total customer base
        - repeat_rate_pct: % of customers who reordered
        - top_customer: most frequent orderer
    """
    err = _check_data()
    if err:
        return err

    df = _data.get("online_orders", pd.DataFrame())
    if df.empty:
        return {"error": "Online orders data not available"}

    customer_orders = (
        df.groupby("customer_name")
        .agg(
            order_count   = ("order_key",   "nunique"),
            total_spent   = ("net_amount",  "sum"),
            items_ordered = ("item_name",   "count"),
            platforms     = ("order_source","nunique")
        )
        .reset_index()
    )

    # Deduplicate net_amount (it's order-level, not item-level)
    # Use order-level spend to avoid double counting multi-item orders
    order_spend = (
        df.drop_duplicates(subset=["order_key"])
        .groupby("customer_name")["net_amount"]
        .sum()
        .reset_index()
        .rename(columns={"net_amount": "total_spent_correct"})
    )

    customer_orders = customer_orders.merge(
        order_spend, on="customer_name", how="left"
    )

    repeat = (
        customer_orders[
            customer_orders["order_count"] >= min_orders
        ]
        .sort_values("order_count", ascending=False)
    )

    repeat_list = [
        {
            "customer_name": row["customer_name"],
            "order_count":   int(row["order_count"]),
            "total_spent":   round(row["total_spent_correct"], 2)
        }
        for _, row in repeat.iterrows()
    ]

    total_customers  = customer_orders["customer_name"].nunique()
    repeat_rate      = round(len(repeat_list) / total_customers * 100, 2)

    return {
        "repeat_customers":       repeat_list,
        "total_repeat_customers": len(repeat_list),
        "total_unique_customers": total_customers,
        "repeat_rate_pct":        repeat_rate,
        "top_customer": repeat_list[0] if repeat_list else None
    }


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY 6 — OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_material_requirements() -> dict:
    """
    Returns prepared dish quantities (KGs) needed based on April sales.
    Useful for kitchen planning and prep scheduling.

    Returns:
        dict with keys:
        - materials: list of {material, quantity, kgs} sorted by kgs
        - total_materials: number of materials tracked
        - highest_demand: material needing most KGs
    """
    err = _check_data()
    if err:
        return err

    materials = _data.get("material_requirements", {})
    if not materials:
        return {"error": "Material requirements not calculated"}

    material_list = sorted(
        [
            {
                "material": mat,
                "quantity": vals["quantity"],
                "kgs":      vals["kgs"]
            }
            for mat, vals in materials.items()
            if vals["kgs"] > 0
        ],
        key=lambda x: x["kgs"],
        reverse=True
    )

    return {
        "materials":       material_list,
        "total_materials": len(material_list),
        "highest_demand":  material_list[0]["material"] if material_list else None
    }


def get_raw_ingredients() -> dict:
    """
    Returns raw ingredient quantities (KGs) needed for procurement.
    Derived from material requirements using recipe ratios.

    Returns:
        dict with keys:
        - ingredients: list of {ingredient, qty_kg} sorted by quantity
        - total_ingredients: number of ingredients
        - highest_demand: ingredient needed most
    """
    err = _check_data()
    if err:
        return err

    ingredients = _data.get("raw_ingredients", {})
    if not ingredients:
        return {"error": "Raw ingredients not calculated"}

    ingredient_list = sorted(
        [
            {"ingredient": ing, "qty_kg": qty}
            for ing, qty in ingredients.items()
            if qty > 0
        ],
        key=lambda x: x["qty_kg"],
        reverse=True
    )

    return {
        "ingredients":      ingredient_list,
        "total_ingredients": len(ingredient_list),
        "highest_demand":   ingredient_list[0]["ingredient"] if ingredient_list else None
    }