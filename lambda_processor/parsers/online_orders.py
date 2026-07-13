"""
parsers/online_orders.py
--------------------------
Parses the Online Orders report — transaction-level Swiggy and
Zomato orders, one row per item per order.

FORMAT: Consistent across all 12 months (Jul 2025 - May 2026).
No version detection needed.

One new channel variant found vs April-only code:
    "Swiggy-Bolt Urgent" — Swiggy's express delivery tier, not in April
    data but present in other months. Normalised to "Swiggy" for
    consistent aggregation across months. Preserved in raw field.

File structure (confirmed against Dec 2025 and Apr 2026):
    Row 0:  Restaurant name
    Row 1:  "NA"
    Row 2:  Report title
    Row 3:  Generated On timestamp
    Row 4:  blank
    Row 5:  Main column headers
    Row 6:  Sub-headers (only for Ordered Items columns 11-17, rest None)
    Row 7+: Data rows — one row per item per order

Merged cell handling (identical to existing data_loader.py logic):
    Excel merges order-level columns across all item rows of the same order.
    Pandas reads merged cells as NaN in continuation rows.
    Forward-fill (ffill) restores order-level data to each item row.

Column mapping (confirmed from Row 5):
    Col 00: date            Col 11: item_name
    Col 01: bill_number     Col 12: rate
    Col 02: time            Col 13: quantity
    Col 03: outlet_name     Col 14: subtotal
    Col 04: order_id        Col 15: category
    Col 05: order_status    Col 16: super_category
    Col 06: order_type      Col 17: comment
    Col 07: order_source    Col 18: total_discount
    Col 08: customer_name   Col 19: amount
    Col 09: customer_addr   Col 20: packaging_charges
    Col 10: customer_phone  Col 21: net_amount
                            Col 22: round_off
                            Col 23: grand_total
                            Col 24: payment_mode
                            Col 25: executive_name
                            Col 26: delivery_boy
                            Col 27: delivery_boy_mobile

Output DataFrame columns:
    All mapped columns above, plus:
    - order_source_raw:  original value before normalisation
    - order_key:         unique order identifier (order_id as string)
    - hour:              hour of day extracted from time column
    - day_of_week, day
"""

import pandas as pd


# ── Channel normalisation map ──────────────────────────────────────────────
# Maps raw order_source values → canonical channel names for consistent
# aggregation across all months. Add new variants here as they appear.
CHANNEL_NORMALISATION = {
    "swiggy-bolt urgent": "Swiggy",   # express tier, treat as Swiggy
    "swiggy bolt":        "Swiggy",   # alt spelling seen in some exports
    "swiggy":             "Swiggy",
    "zomato":             "Zomato",
    "magic pin":          "Magic Pin",
    "magicpin":           "Magic Pin",
}

COLUMN_NAMES = {
    0:  "date",            1:  "bill_number",
    2:  "time",            3:  "outlet_name",
    4:  "order_id",        5:  "order_status",
    6:  "order_type",      7:  "order_source",
    8:  "customer_name",   9:  "customer_address",
    10: "customer_phone",  11: "item_name",
    12: "rate",            13: "quantity",
    14: "subtotal",        15: "category",
    16: "super_category",  17: "comment",
    18: "total_discount",  19: "amount",
    20: "packaging_charges",21:"net_amount",
    22: "round_off",       23: "grand_total",
    24: "payment_mode",    25: "executive_name",
    26: "delivery_boy",    27: "delivery_boy_mobile"
}

# These columns are order-level (merged across item rows) → ffill
ORDER_LEVEL_COLS = [
    "date", "bill_number", "time", "outlet_name",
    "order_id", "order_status", "order_type", "order_source",
    "customer_name", "customer_address", "customer_phone",
    "total_discount", "amount", "packaging_charges", "net_amount",
    "round_off", "grand_total", "payment_mode",
    "executive_name", "delivery_boy", "delivery_boy_mobile"
]


def parse_online_orders(filepath: str) -> pd.DataFrame:
    """
    Parses an Online Orders xlsx file into a clean DataFrame.

    Args:
        filepath: local path to the downloaded xlsx file

    Returns:
        DataFrame with one row per item per order, all order-level
        columns forward-filled. Includes normalised channel names.
    """
    df_raw = pd.read_excel(filepath, header=None)

    # ── Step 1: Get data rows from row 7 onward ────────────────────────
    df_data = df_raw.iloc[7:].copy()

    # ── Step 2: Remove day-separator header repetition rows ────────────
    # POS system inserts "Date" header rows between days — not data rows
    df_data = df_data[df_data.iloc[:, 0] != "Date"].copy()

    # ── Step 3: Rename columns ─────────────────────────────────────────
    df_data = df_data.iloc[:, :28].copy()
    df_data.columns = range(28)
    df_data = df_data.rename(columns=COLUMN_NAMES)

    # ── Step 4: Forward-fill order-level columns ───────────────────────
    for col in ORDER_LEVEL_COLS:
        if col in df_data.columns:
            df_data[col] = df_data[col].ffill()

    # ── Step 5: Drop rows where item_name is blank ─────────────────────
    df_data = df_data[df_data["item_name"].notna()].copy()
    df_data = df_data[
        df_data["item_name"].astype(str).str.strip() != ""
    ].copy()
    df_data = df_data[df_data["item_name"] != "nan"].copy()

    df = df_data.reset_index(drop=True)

    # ── Step 6: Parse and clean columns ───────────────────────────────
    # Two date formats found across 12 months of real data:
    #   "Dec 01,2025"  — format "%b %d,%Y" (most months)
    #   "01-Apr-2026"  — format "%d-%b-%Y" (some months)
    # Try both — whichever produces fewer NaT values wins.
    date_col = df["date"].astype(str)
    parsed_v1 = pd.to_datetime(date_col, format="%b %d,%Y", errors="coerce")
    parsed_v2 = pd.to_datetime(date_col, format="%d-%b-%Y", errors="coerce")

    # Use whichever format successfully parsed more rows
    if parsed_v1.notna().sum() >= parsed_v2.notna().sum():
        df["date"] = parsed_v1
    else:
        df["date"] = parsed_v2

    df["hour"] = pd.to_datetime(
        df["time"].astype(str),
        format="%I:%M:%S %p",
        errors="coerce"
    ).dt.hour

    for col in ["rate", "quantity", "subtotal", "total_discount",
                "amount", "net_amount", "grand_total",
                "packaging_charges", "round_off"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # ── Enforce float64 for all revenue/amount columns ─────────────────
    # Jul 2025 orders have whole-number net_amount values — pyarrow
    # infers int64 causing HIVE_PARTITION_SCHEMA_MISMATCH in Athena
    # when other months write float64 for the same column.
    for col in ["rate", "quantity", "subtotal", "total_discount",
                "amount", "net_amount", "grand_total",
                "packaging_charges", "round_off"]:
        if col in df.columns:
            df[col] = df[col].astype(float)

    for col in ["order_source", "customer_name", "item_name",
                "category", "super_category", "order_type",
                "payment_mode", "order_status"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # customer_phone and bill_number come from Excel as mixed int/float/string
    # depending on whether the value looks numeric. pyarrow rejects mixed-type
    # object columns — cast everything to string to make Parquet writing safe.
    for col in ["customer_phone", "bill_number", "order_id", "customer_address"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # ── Step 7: Normalise order_source across channel variants ─────────
    # Preserve raw value before normalisation for auditability
    df["order_source_raw"] = df["order_source"]
    df["order_source"] = df["order_source"].apply(
        lambda x: CHANNEL_NORMALISATION.get(x.lower(), x)
    )

    # ── Step 8: Derived columns ────────────────────────────────────────
    df["day_of_week"] = df["date"].dt.day_name()
    df["day"]         = df["date"].dt.day
    df["order_key"]   = df["order_id"].astype(str)

    # ── Step 9: Drop rows with unparseable dates ───────────────────────
    df = df.dropna(subset=["date"]).reset_index(drop=True)

    return df
