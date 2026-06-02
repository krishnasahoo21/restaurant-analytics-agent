"""
data_loader.py
--------------
Single source of truth for all restaurant data.
Loads, cleans and structures all data sources for the agent.

Data Sources:
    1. item_master.xlsx          - Menu catalogue
    2. Monthly summary reports   - March & April KPIs (hardcoded from formatted reports)
    3. menu_mix_report.xlsx      - Item-level sales with categories (April)
    4. item_wise_sales.xlsx      - Daily item sales matrix (April)
    5. online_orders.xlsx        - Transaction-level Swiggy/Zomato orders (April)

Business Logic (from client's existing scripts):
    6. MATERIAL_LOGIC            - Maps menu items → prepared dish KGs
    7. RAW_INGREDIENTS           - Maps prepared dishes → raw ingredient KGs
"""

import pandas as pd
from pathlib import Path


# ── Config ─────────────────────────────────────────────────────────────────
# Path to data folder — works regardless of where script is run from
DATA_DIR = Path(__file__).parent.parent / "data"


# ── Business Logic (preserved exactly from client's material_calculator.py) 
# These mappings encode how menu items translate to kitchen prep quantities.
# Conversion = pieces per KG (e.g. 28 kabab pieces = 1 KG of mixture)
# ───────────────────────────────────────────────────────────────────────────
MATERIAL_LOGIC = {
    'tunday mutton galawati kabab': {
        'items': {
            'tunday mutton galawati kabab- 2 pcs': 2,
            'tunday mutton galawati kabab- 4 pcs': 4,
            'tunday mutton kabab combo': 4,
            'happy feast- chicken korma, two parathas and two signature galawati': 2,
            'half chicken biryani + half tunday mutton gilawati kabab': 2,
            'mutton galawati roll': 2
        },
        'conversion': 28
    },
    'tunday chicken galawati kabab': {
        'items': {
            'tunday chicken galawati kabab- 2 pcs': 2,
            'tunday chicken galawati kabab- 4 pcs': 4,
            'chicken gilawati combo': 4,
            'happy feast- chicken korma, two parathas and two signature galawati': 2
        },
        'conversion': 28
    },
    'chicken korma': {
        'items': {
            'happy feast- chicken korma, two parathas and two signature galawati': 0.5,
            'half chicken korma and 2 ulte tawa ka paratha': 0.5,
            'chicken korma - full': 1,
            'chicken korma - half': 0.5,
            'mini meal 1- quarter chicken korma and 1 paratha': 0.25,
            'mini meal 3- quarter chicken biryani and quarter korma': 0.25
        },
        'conversion': 3.0
    },
    'mutton korma': {
        'items': {
            'half mutton seekh kabab + half mutton korma + 2 rumali roti': 0.5,
            'mutton korma full': 1,
            'mutton korma half': 0.5
        },
        'conversion': 3.5
    },
    'shami kabab': {
        'items': {
            'shami kabab- 2 pcs': 2,
            'shami kabab- 4 pcs': 4,
            'chicken shami roll': 2
        },
        'conversion': 24
    },
    'veg shami kabab': {
        'items': {
            'veg shami combo': 4,
            'veg shami kabab full': 4,
            'veg shami kabab half': 2,
            'veg shami roll': 2
        },
        'conversion': 24
    },
    'chicken for roasted': {
        'items': {
            'half butter chicken + 2 ulte tawe ka paratha': 0.5,
            'half chicken biryani and half chicken kali mirch': 0.5,
            'half chicken biryani and half chicken masala': 0.5,
            'chicken kali mirch- full': 1,
            'chicken kali mirch- half': 0.5,
            'chicken masala- full': 1,
            'chicken masala- half': 0.5,
            'butter chicken- full': 1,
            'butter chicken- half': 0.5,
            'roasted chicken- full': 1,
            'roasted chicken- half': 0.5
        },
        'conversion': 1.0
    },
    'mutton biryani': {
        'items': {
            'mutton biryani - full': 1,
            'mutton biryani- half': 0.5
        },
        'conversion': 3.5
    },
    'chicken biryani': {
        'items': {
            'chicken biryani - half': 0.5,
            'chicken biryani- full': 1,
            'half chicken biryani + half tunday mutton gilawati kabab': 0.5,
            'half chicken biryani and half chicken kali mirch': 0.5,
            'half chicken biryani and half chicken masala': 0.5,
            'half chicken biryani and cold drink': 0.5,
            'mini meal 3- quarter chicken biryani and quarter korma': 0.25
        },
        'conversion': 3.0
    },
    'mutton bhuna': {
        'items': {
            'half mutton bhuna + 2 ulte tawe ka paratha': 0.5,
            'mutton bhuna- full': 1,
            'mutton bhuna- half': 0.5
        },
        'conversion': 3.5
    },
    'seekh kabab mutton': {
        'items': {
            'seekh kabab mutton- full': 1,
            'seekh kabab mutton- half': 0.5,
            'half mutton seekh kabab + half mutton korma + 2 rumali roti': 0.5,
            'mutton seekh roll': 0.5
        },
        'conversion': 3.5
    },
    'seekh kabab chicken': {
        'items': {
            'seekh kabab chicken- full': 1,
            'seekh kabab chicken- half': 0.5,
            'chicken seekh roll': 0.25
        },
        'conversion': 3.5
    },
    'chicken boti kabab': {
        'items': {
            'chicken boti kabab': 1,
            'chicken boti roll': 0.5,
            'mini meal 2- half chicken boti kabab and 1 paratha': 0.5
        },
        'conversion': 5
    },
    'chicken tikka': {
        'items': {
            'half chicken tikka and 2 ulte tawe ka paratha': 0.5,
            'chicken tikka (boneless)': 1,
            'chicken tikka roll': 0.5
        },
        'conversion': 2.5
    },
    'chicken tangdi kabab': {
        'items': {
            'chicken tangdi kabab half': 0.5,
            'chicken tangdi masala full': 1
        },
        'conversion': 3
    },
    'fish tikka': {
        'items': {'fish tikka': 1},
        'conversion': 3
    },
    'paneer': {
        'items': {
            'avadhi paneer masala- full': 1,
            'avadhi paneer masala- half': 0.5,
            'mini meal 4- quarter avadhi paneer and 1 paratha': 0.25,
            'paneer tikka': 1,
            'paneer tikka roll': 0.5
        },
        'conversion': 3.5
    },
    'paratha': {
        'items': {
            'chicken boti roll': 1,
            'veg shami roll': 1,
            'paneer bhuna roll': 1,
            'chicken galawati roll': 1,
            'chicken seekh roll': 1,
            'chicken shami roll': 1,
            'chicken tikka roll': 1,
            'mutton galawati roll': 1,
            'mutton seekh roll': 1,
            'paneer tikka roll': 1,
            'tunday mutton kabab combo': 2,
            'veg shami combo': 2,
            'happy feast- chicken korma, two parathas and two signature galawati': 2,
            'half chicken korma and 2 ulte tawa ka paratha': 2,
            'half chicken tikka and 2 ulte tawe ka paratha': 2,
            'half mutton bhuna + 2 ulte tawe ka paratha': 2,
            'half butter chicken + 2 ulte tawe ka paratha': 2,
            'chicken gilawati combo': 2,
            'mini meal 1- quarter chicken korma and 1 paratha': 1,
            'mini meal 2- half chicken boti kabab and 1 paratha': 1,
            'mini meal 4- quarter avadhi paneer and 1 paratha': 1,
            'mughlai paratha': 1
        },
        'conversion': 11
    }
}

# ── Raw Ingredient Recipes (from client's raw_ingredient_calculator.py) ────
# Maps prepared dish KGs → raw ingredient KGs needed for procurement
# ───────────────────────────────────────────────────────────────────────────
RAW_INGREDIENTS = {
    'tunday mutton galawati kabab': {
        'mutton keema': 0.66,
        'chicken tikka': 0.37,
        'sattu': 0.25,
        'papita': 0.2,
        'kabab masala': 0.02,
        'javitri': 0.015,
        'yield': 1.485
    },
    'tunday chicken galawati kabab': {
        'chicken tikka': 1,
        'sattu': 0.25,
        'papita': 0.2,
        'kabab masala': 0.02,
        'javitri': 0.015,
        'yield': 1.485
    },
    'shami kabab': {
        'chicken tikka': 1,
        'chana dal': 0.3,
        'others': 0.25,
        'yield': 1.55
    },
    'mutton korma': {
        'onion': 0.8,
        'mutton boti': 1.5,
        'oil': 1.05,
        'red chili powder': 0.026,
        'salt': 0.05,
        'khada masala': 0.02,
        'lehsan + adrak': 0.15,
        'brown onion': 0.08,
        'yield': 1.5
    },
    'chicken korma': {'chicken boti': 1, 'yield': 1},
    'chicken biryani': {'chicken boti': 1, 'yield': 1},
    'mutton biryani': {'mutton boti': 1, 'yield': 1},
    'mutton bhuna': {
        'onion': 0.8,
        'mutton boti': 1.5,
        'oil': 1.05,
        'red chili powder': 0.026,
        'salt': 0.05,
        'khada masala': 0.02,
        'lehsan + adrak': 0.15,
        'brown onion': 0.08,
        'yield': 1.5
    },
    'seekh kabab mutton': {
        'mutton tikka seekh': 0.9,
        'others': 0.1,
        'yield': 1
    },
    'seekh kabab chicken': {
        'chicken tikka': 0.9,
        'others': 0.1,
        'yield': 1
    },
    'chicken tikka': {'chicken tikka': 1, 'yield': 1},
    'chicken for roasted': {'chicken boti': 1, 'yield': 1}
}


# ── Data Loaders ────────────────────────────────────────────────────────────

def load_item_master() -> pd.DataFrame:
    """
    Loads the menu item master data.

    Returns:
        DataFrame with columns:  
        - item_name: name of the menu item
        - shelf_life_days: how long item stays fresh
        - base_item_name: parent item (for Half/Full variants)
        - is_combo: whether item is a combo
        - breakdown: component breakdown of item
    """
    filepath = DATA_DIR / "item_master.xlsx"
    if not filepath.exists():
        raise FileNotFoundError(f"item_master.xlsx not found in {DATA_DIR}")

    df = pd.read_excel(filepath)

    # ── Cleaning of column names, item names ─────────────────────────────────
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    df["item_name"] = df["item_name"].str.strip()

    if "is_combo" in df.columns:
        df["is_combo"] = df["is_combo"].str.strip().str.lower() == "yes"

    print(f"✅ Item master loaded: {len(df)} items")
    return df


def load_monthly_summary() -> dict:
    """
    Monthly KPI summaries for March and April 2026.
    Hardcoded from pre-formatted summary reports (not raw tabular data).

    Returns:
        dict with keys 'march' and 'april', each containing:
        - net_sales: total net sales in INR
        - total_revenue: gross revenue in INR
        - total_orders: number of orders/checks
        - avg_order_value: average order value in INR
        - total_discounts: total discounts given in INR
        - total_items_sold: total items sold
        - channel_split: dict of revenue by channel (Swiggy/Zomato/POS)
        - category_split: dict of revenue by food category
    """

    march = {
        "month": "March 2026",
        "net_sales": 260672,
        "total_revenue": 266929,
        "total_orders": 456,
        "avg_order_value": 571.65,
        "total_discounts": 26358,
        "total_items_sold": 1112,
        "channel_split": {
            "Swiggy":  {"revenue": 117221, "orders": 214, "share_pct": 44.97},
            "Zomato":  {"revenue": 95530,  "orders": 128, "share_pct": 36.65},
            "POS":     {"revenue": 47922,  "orders": 114, "share_pct": 18.38},
        },
        "category_split": {
            "Kabab & Roasted": {"items": 335, "revenue": 107895},
            "Breads":          {"items": 492, "revenue": 32917},
            "Combos":          {"items": 129, "revenue": 65159},
            "Biryani":         {"items": 87,  "revenue": 33371},
            "Rolls":           {"items": 52,  "revenue": 14016},
            "Main Course":     {"items": 17,  "revenue": 7315},
        }
    }

    april = {
        "month": "April 2026",
        "net_sales": 291829,
        "total_revenue": 299848,
        "total_orders": 489,
        "avg_order_value": 596.79,
        "total_discounts": 23526,
        "total_items_sold": 1299,
        "channel_split": {
            "Swiggy":    {"revenue": 102281, "orders": 156, "share_pct": 35.05},
            "Zomato":    {"revenue": 114600, "orders": 198, "share_pct": 39.27},
            "POS":       {"revenue": 74948,  "orders": 114, "share_pct": 25.68},
            "Magic Pin": {"revenue": 2940,   "orders": 21,  "share_pct": 1.01},
        },
        "category_split": {
            "Kabab & Roasted": {"items": 361, "revenue": 114699},
            "Breads":          {"items": 580, "revenue": 39008},
            "Combos":          {"items": 126, "revenue": 55874},
            "Biryani":         {"items": 124, "revenue": 48585},
            "Rolls":           {"items": 79,  "revenue": 21014},
            "Main Course":     {"items": 29,  "revenue": 12650},
        }
    }

    print(f"✅ Monthly summaries loaded: March & April 2026")
    return {"march": march, "april": april}


def load_menu_mix_report() -> pd.DataFrame:
    """
    Loads the Enterprise Menu Mix Report — item-level sales with
    categories, rates, quantities and discounts for April 2026.

    File structure (confirmed from actual file):
        Row 0:    Headers — Deployment, Category, Super Category,
                            Item No., Item, Rate, Qty, Amount,
                            Discount, Net Amount, Percentage of Sales
        Row 1-40: Item data rows
        Row 41:   Grand Total row  ← stop here
        Row 44+:  Category summary section ← different structure, skip

    Column name mapping after normalisation:
        "Item"     → "item"      (we rename to item_name for consistency)
        "Item No." → "item_no."  (we rename to item_no)

    Returns:
        DataFrame with columns: deployment, category, super_category,
        item_no, item_name, rate, qty, amount, discount,
        net_amount, percentage_of_sales, item_name_lower
    """

    files = list(DATA_DIR.glob("Enterprise_Menu_Mix_Report*.xlsx"))
    if not files:
        raise FileNotFoundError(
            "Enterprise Menu Mix Report not found. "
            "Expected: Enterprise_Menu_Mix_Report*.xlsx in data/ folder"
        )

    # ── Read with Row 0 as header ──────────────────────────────────────────
    df = pd.read_excel(files[0], header=0)

    # ── Normalise column names ─────────────────────────────────────────────
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace(".", "", regex=False)
    )

    # ── Rename for consistency across the codebase ─────────────────────────
    # "item"     → "item_name"  (consistent with other data sources)
    # "item_no_" → "item_no"    (clean up trailing underscore)
    df = df.rename(columns={
        "item":     "item_name",
        "item_no_": "item_no"
    })

    # ── Keep only item rows — stop at Grand Total ──────────────────────────
    # Grand Total row has "Grand Total" in the deployment column
    # Category summary section starts at row 44 with different headers
    grand_total_mask = df["deployment"].astype(str).str.strip() == "Grand Total"
    if grand_total_mask.any():
        first_total_idx = grand_total_mask.idxmax()
        df = df.loc[:first_total_idx - 1].copy()

    # ── Clean numeric columns ──────────────────────────────────────────────
    for col in ["rate", "qty", "amount", "discount",
                "net_amount", "percentage_of_sales"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # ── Clean item_no ──────────────────────────────────────────────────────
    if "item_no" in df.columns:
        df["item_no"] = pd.to_numeric(
            df["item_no"], errors="coerce"
        ).dropna().astype(int)

    # ── Add item_name_lower for matching with MATERIAL_LOGIC ──────────────
    df["item_name_lower"] = df["item_name"].str.strip().str.lower()

    # ── Drop any remaining invalid rows ───────────────────────────────────
    df = df.dropna(subset=["item_name"]).copy()
    df = df[df["item_name"].astype(str).str.strip() != ""].copy()

    print(f"✅ Menu mix report loaded: {len(df)} items across "
          f"{df['category'].nunique()} categories")
    return df

   

def load_item_wise_sales() -> pd.DataFrame:
    """
    Loads daily item-wise sales for April 2026.
    Transforms wide-format Excel (items × dates) into long-format DataFrame
    (one row per item per day) for time-series analysis.

    File structure (discovered from actual file):
        Row 0-4:  Report metadata/headers — skip
        Row 5:    Date headers (S.No, Item, 01-Apr-2026, NaN, 02-Apr-2026...)
        Row 6:    Subheaders (Qty, Amt repeating per date)
        Row 7-46: Item data (col 0=S.No, col 1=Item name, col 2+=daily data)
        Row 47:   Grand Total — skip

    Returns:
        DataFrame with columns: 
        - item_name: menu item name
        - date: sale date
        - quantity: units sold
        - revenue: revenue in INR
        - day_of_week
        day
    """

    # Find the file — using glob because filename has a long ID suffix
    files = list(DATA_DIR.glob("Item_Wise_Enterprise(2026.04*.xlsx"))

    if not files:
        raise FileNotFoundError(
            "Item wise sales file not found. "
            "Expected: Item_Wise_Enterprise(2026.04*.xlsx"
        )

    df_raw = pd.read_excel(files[0], header=None)

    # ── Step 1: Extract dates from Row 5 ──────────────────────────────────
    # Row 5 structure: ['S.No', 'Item', '01-Apr-2026', NaN, '02-Apr-2026'...]
    # Dates appear every 2 columns starting from column 2
    # NaN between dates is the Amt column placeholder

    date_row = df_raw.iloc[5].tolist()

    dates = []
    date_col_indices = []  # track which column each date starts at

    for col_idx, val in enumerate(date_row[2:], start=2):
        if pd.notna(val) and str(val).strip() not in ['', 'nan']:
            parsed_date = pd.to_datetime(str(val), errors="coerce")
            if pd.notna(parsed_date):
                dates.append(parsed_date)
                date_col_indices.append(col_idx)

    print(f"   Found {len(dates)} dates: "
          f"{dates[0].strftime('%d-%b')} to {dates[-1].strftime('%d-%b')}")

    # ── Step 2: Extract item rows (Row 7 to second-to-last row) ───────────
    # Skip Row 47 (Grand Total) — last row
    item_rows = df_raw.iloc[7:-1]        


    # ── Step 3: Transform wide → long format ──────────────────────────────
    records = []

    for _, row in item_rows.iterrows():
        item_name = str(row.iloc[1]).strip()   # col 1 = Item name

        # Skip empty or invalid rows
        if not item_name or item_name.lower() in ["nan", "grand total", "total"]:
            continue

        # For each date, extract Qty and Amt from the correct columns
        for date, qty_col in zip(dates, date_col_indices):
            amt_col = qty_col + 1   # Amount is always one column after Qty

            qty = row.iloc[qty_col]
            amt = row.iloc[amt_col]

            # Only record days where something was actually sold
            if pd.notna(qty) and float(qty) > 0:
                records.append({
                    "item_name": item_name,
                    "date":      date,
                    "quantity":  int(float(qty)),
                    "revenue":   float(amt) if pd.notna(amt) else 0.0
                })

    # ── Step 4: Build DataFrame and add derived columns ───────────────────
    if not records:
        raise ValueError(
            "No sales records found after parsing. "
            "Check file structure matches expected format."
        )

    df = pd.DataFrame(records)
    df["day_of_week"] = df["date"].dt.day_name()
    df["day"]         = df["date"].dt.day

    print(f"✅ Item wise sales loaded: {len(df)} records, "
          f"{df['date'].nunique()} days, "
          f"{df['item_name'].nunique()} items")
    return df
    

def load_online_orders() -> pd.DataFrame:
    """
    Loads transaction-level online orders (Swiggy + Zomato) for April 2026.

    File structure (discovered from actual file):
        Row 0-4:  Report metadata — skip
        Row 5:    Main header row
        Row 6:    Sub-header row (only for Ordered Items cols 11-17) — skip
        Row 7+:   Data rows — one row per item per order

    Merged cell handling:
        Excel merges order-level columns across all item rows of the same order.
        Pandas reads merged cells as NaN in continuation rows.
        We use forward fill (ffill) to restore order-level data to each item row.

    Two types of columns:
        Order-level  → cols 0-10, 18-27  → ffill across item rows
        Item-level   → cols 11-17        → unique per row, never ffill

    Column mapping:
        Col 00: date                Col 11: item_name
        Col 01: bill_number         Col 12: rate
        Col 02: time                Col 13: quantity
        Col 03: outlet_name         Col 14: subtotal
        Col 04: order_id            Col 15: category
        Col 05: order_status        Col 16: super_category
        Col 06: order_type          Col 17: comment
        Col 07: order_source        Col 18: total_discount
        Col 08: customer_name       Col 19: amount
        Col 09: customer_address    Col 20: packaging_charges
        Col 10: customer_phone      Col 21: net_amount
                                    Col 22: round_off
                                    Col 23: grand_total
                                    Col 24: payment_mode
                                    Col 25: executive_name
                                    Col 26: delivery_boy
                                    Col 27: delivery_boy_mobile

    Returns:
        DataFrame with one row per item per order, all order-level
        columns forward filled across multi-item orders.
    """
    
    files = list(DATA_DIR.glob("Online_Orders_Reports*.xlsx"))
    if not files:
        raise FileNotFoundError(
            "Online orders file not found. "
            "Expected: Online_Orders_Reports*.xlsx in data/ folder"
        )

    df_raw = pd.read_excel(files[0], header=None)

    # ── Step 1: Define column mapping ─────────────────────────────────────
    # Manually mapped from Row 5 (main header) + Row 6 (sub-header)
    column_names = {
        0:  "date",
        1:  "bill_number",
        2:  "time",
        3:  "outlet_name",
        4:  "order_id",
        5:  "order_status",
        6:  "order_type",
        7:  "order_source",
        8:  "customer_name",
        9:  "customer_address",
        10: "customer_phone",
        11: "item_name",          # ── Item-level cols start ──
        12: "rate",
        13: "quantity",
        14: "subtotal",
        15: "category",
        16: "super_category",
        17: "comment",            # ── Item-level cols end ────
        18: "total_discount",
        19: "amount",
        20: "packaging_charges",
        21: "net_amount",
        22: "round_off",
        23: "grand_total",
        24: "payment_mode",
        25: "executive_name",
        26: "delivery_boy",
        27: "delivery_boy_mobile"
    }

    # ── Step 2: Get all rows from row 7 onwards ───────────────────────────
    df_data = df_raw.iloc[7:].copy()

    # ── Step 3: Remove repeating header rows ──────────────────────────────
    # Day-separator rows where col 0 == "Date" — these are NOT merged rows
    # They are actual header repetitions inserted by the POS system
    df_data = df_data[df_data.iloc[:, 0] != "Date"].copy()

    # ── Step 4: Rename columns ────────────────────────────────────────────
    df_data = df_data.iloc[:, :28].copy()
    df_data.columns = range(28)
    df_data = df_data.rename(columns=column_names)

    # ── Step 5: Forward fill ALL order-level columns ──────────────────────
    # These columns are merged in Excel across all item rows of one order.
    # ffill restores the value to each item row.
    #
    # Order-level = everything EXCEPT item-level cols (11-17):
    #   item_name, rate, quantity, subtotal, category,
    #   super_category, comment
    # These are legitimately different per item row — never ffill them.

    order_level_cols = [
        # Pre-item order info (cols 0-10)
        "date",
        "bill_number",
        "time",
        "outlet_name",
        "order_id",
        "order_status",
        "order_type",
        "order_source",
        "customer_name",
        "customer_address",
        "customer_phone",
        # Post-item order totals (cols 18-27)
        "total_discount",
        "amount",
        "packaging_charges",
        "net_amount",
        "round_off",
        "grand_total",
        "payment_mode",
        "executive_name",
        "delivery_boy",
        "delivery_boy_mobile"
    ]

    for col in order_level_cols:
        if col in df_data.columns:
            df_data[col] = df_data[col].ffill()

    # ── Step 6: Drop rows where item_name is blank ────────────────────────
    # After ffill, only truly empty rows will have no item_name
    df_data = df_data[df_data["item_name"].notna()].copy()
    df_data = df_data[
        df_data["item_name"].astype(str).str.strip() != ""
    ].copy()
    df_data = df_data[df_data["item_name"] != "nan"].copy()

    df = df_data.reset_index(drop=True)

    # ── Step 7: Parse and clean columns ───────────────────────────────────
    # Dates
    df["date"] = pd.to_datetime(
        df["date"], format="%b %d,%Y", errors="coerce"
    )

    # Extract hour from time for peak hour analysis
    df["hour"] = pd.to_datetime(
        df["time"].astype(str),
        format="%I:%M:%S %p",
        errors="coerce"
    ).dt.hour

    # Numeric columns
    for col in ["rate", "quantity", "subtotal", "total_discount",
                "amount", "net_amount", "grand_total",
                "packaging_charges", "round_off"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # String columns
    for col in ["order_source", "customer_name", "item_name",
                "category", "super_category", "delivery_boy",
                "order_type", "payment_mode", "order_status"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # ── Step 8: Add derived columns ───────────────────────────────────────
    df["day_of_week"] = df["date"].dt.day_name()
    df["day"]         = df["date"].dt.day

    # order_id is the reliable unique order identifier
    # Swiggy and Zomato both assign globally unique order IDs
    df["order_key"] = df["order_id"].astype(str)

    # ── Step 9: Final validation ──────────────────────────────────────────
    df = df.dropna(subset=["date"])

    print(f"✅ Online orders loaded: {len(df)} item lines across "
          f"{df['order_key'].nunique()} orders, "
          f"{df['order_source'].nunique()} platforms "
          f"({', '.join(sorted(df['order_source'].unique()))}), "
          f"{df['customer_name'].nunique()} unique customers")

    return df


# ── Business Logic Functions ────────────────────────────────────────────────

def calculate_material_requirements(sales_data: dict) -> dict:
    """
    Calculates prepared dish quantities (in KGs) needed based on sales.
    Adapted from client's material_calculator.py.

    Args:
        sales_data: dict of {item_name_lower: quantity_sold}

    Returns:
        dict of {material_name: {'quantity': float, 'kgs': float}}
    """
    output = {}
    for material, logic in MATERIAL_LOGIC.items():
        total_qty = 0
        for item, multiplier in logic['items'].items():
            total_qty += sales_data.get(item.strip().lower(), 0) * multiplier
        kgs = round(total_qty / logic['conversion'], 2)
        output[material] = {
            'quantity': round(total_qty, 2),
            'kgs': kgs
        }
    return output


def calculate_raw_ingredients(prepared_kgs: dict) -> dict:
    """
    Calculates raw ingredient quantities needed from prepared dish KGs.
    Adapted from client's raw_ingredient_calculator.py.

    Args:
        prepared_kgs: dict of {material_name: kgs_needed}

    Returns:
        dict of {ingredient_name: qty_in_kg}
    """
    from collections import defaultdict
    raw_totals = defaultdict(float)

    for item, amount in prepared_kgs.items():
        recipe = RAW_INGREDIENTS.get(item.lower())
        if not recipe:
            continue
        yield_kg = recipe['yield']
        multiplier = amount / yield_kg
        for ingredient, qty in recipe.items():
            if ingredient == 'yield':
                continue
            raw_totals[ingredient] += qty * multiplier

    return {k: round(v, 3) for k, v in sorted(raw_totals.items())}


# ── Master Load Function ────────────────────────────────────────────────────

def load_all_data() -> dict:
    """
    Master entry point for all agent data access — loads all data sources and 
    pre-computes material and raw ingredient requirements from April sales.

    Returns:
        dictionary with keys:
        - item_master:          DataFrame (menu items)
        - monthly_summary:      dict (march + april KPIs)
        - menu_mix_report:      DataFrame (item-level April sales)
        - item_wise_sales:      DataFrame (daily April sales)
        - online_orders:        DataFrame (transaction-level April)
        - material_requirements: dict (prepared dish KGs for April)
        - raw_ingredients:      dict (raw procurement KGs for April)
        - metadata:             dict (record counts + load errors)
    """
    print("\n📂 Loading all restaurant data...")
    print("─" * 45)

    data = {}
    errors = []

    # ── Load all data sources ──────────────────────────────────────────────
    for name, loader in [
        ("item_master",     load_item_master),
        ("monthly_summary", load_monthly_summary),
        ("menu_mix_report", load_menu_mix_report),
        ("item_wise_sales", load_item_wise_sales),
        ("online_orders",   load_online_orders),
    ]:
        try:
            data[name] = loader()
        except Exception as e:
            errors.append(f"{name}: {e}")
            data[name] = pd.DataFrame() if name != "monthly_summary" else {}
            print(f"⚠️  Failed to load {name}: {e}")

    # ── Pre-compute material requirements from April menu mix ─────────────
    # This runs the client's business logic automatically at load time
    try:
        if not data["menu_mix_report"].empty:
            sales_dict = dict(zip(
                data["menu_mix_report"]["item_name_lower"],
                data["menu_mix_report"]["qty"]
            ))
            data["material_requirements"] = calculate_material_requirements(
                sales_dict
            )
            prepared_kgs = {
                k: v["kgs"]
                for k, v in data["material_requirements"].items()
            }
            data["raw_ingredients"] = calculate_raw_ingredients(prepared_kgs)
            print(f"✅ Material requirements calculated: "
                  f"{len(data['material_requirements'])} prepared items")
            print(f"✅ Raw ingredients calculated: "
                  f"{len(data['raw_ingredients'])} ingredients")
    except Exception as e:
        errors.append(f"material_calculations: {e}")
        data["material_requirements"] = {}
        data["raw_ingredients"] = {}
        print(f"⚠️  Material calculations failed: {e}")

    # ── Build metadata ─────────────────────────────────────────────────────
    data["metadata"] = {
        "item_master_count":      len(data.get("item_master", [])),
        "menu_mix_items":         len(data.get("menu_mix_report", [])),
        "item_wise_records":      len(data.get("item_wise_sales", [])),
        "online_order_records":   len(data.get("online_orders", [])),
        "materials_tracked":      len(data.get("material_requirements", {})),
        "raw_ingredients_tracked":len(data.get("raw_ingredients", {})),
        "months_available":       list(data.get("monthly_summary", {}).keys()),
        "load_errors":            errors
    }

    # ── Final summary ──────────────────────────────────────────────────────
    print("─" * 45)
    status = "✅ All data loaded!" if not errors else f"⚠️  Loaded with {len(errors)} error(s)"
    print(status)
    print(f"\n📊 Data Summary:")
    print(f"   • Menu items:             {data['metadata']['item_master_count']}")
    print(f"   • Menu mix items:         {data['metadata']['menu_mix_items']}")
    print(f"   • Daily sales records:    {data['metadata']['item_wise_records']}")
    print(f"   • Online order records:   {data['metadata']['online_order_records']}")
    print(f"   • Materials tracked:      {data['metadata']['materials_tracked']}")
    print(f"   • Raw ingredients:        {data['metadata']['raw_ingredients_tracked']}")
    print(f"   • Months available:       {data['metadata']['months_available']}")

    return data