"""
verify_parquet.py
-----------------
Verifies that processed Parquet files in S3 contain correct data
by comparing against known ground truth values from data_loader.py.

Run from your project root with venv active:
    python3 verify_parquet.py

Requires: pip install boto3 pandas pyarrow
"""

import boto3
import pandas as pd
import io
import json

session = boto3.Session(profile_name="tunday")
s3      = session.client("s3", region_name="us-west-2")
BUCKET  = "restaurant-agent-data-prod"
CLIENT  = "clients/tunday-kababi/processed"


def read_parquet(key: str) -> pd.DataFrame:
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return pd.read_parquet(io.BytesIO(obj["Body"].read()))


def check(label, actual, expected, tolerance=0):
    if tolerance:
        ok = abs(float(actual) - float(expected)) <= tolerance
    else:
        ok = actual == expected
    status = "✅" if ok else "❌"
    print(f"   {status} {label}: {actual}  (expected: {expected})")
    return ok


passed = 0
failed = 0

print("=" * 65)
print("PARQUET VERIFICATION — comparing against original Excel values")
print("=" * 65)

# ── 1. Daily Sales April 2026 ─────────────────────────────────────
# Ground truth: hardcoded in data_loader.py, manually verified
print("\n1. Daily Sales — April 2026")
try:
    df = read_parquet(f"{CLIENT}/daily-sales/year=2026/month=04/daily-sales.parquet")
    cs = json.loads(df["channel_split"].iloc[0])
    cat = json.loads(df["category_split"].iloc[0])

    results = [
        check("net_sales",        round(df["net_sales"].iloc[0]),       291829,  tolerance=1),
        check("total_orders",     int(df["total_orders"].iloc[0]),       489),
        check("avg_order_value",  round(df["avg_order_value"].iloc[0], 2), 596.79, tolerance=0.5),
        check("total_discounts",  round(df["total_discounts"].iloc[0]), 23526,   tolerance=1),
        check("total_items_sold", int(df["total_items_sold"].iloc[0]),  1299),
        check("channel Zomato revenue", round(cs["Zomato"]["revenue"]), 114600,  tolerance=5),
        check("channel Swiggy orders",  cs["Swiggy"]["orders"],         156),
        check("category Biryani items", cat["Biryani"]["items"],        124),
    ]
    if all(results):
        print("   ✅ PASS — all April 2026 daily sales values match")
        passed += 1
    else:
        print("   ❌ FAIL — some values don't match")
        failed += 1
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    failed += 1

# ── 2. Menu Mix April 2026 ────────────────────────────────────────
print("\n2. Menu Mix — April 2026")
try:
    df = read_parquet(f"{CLIENT}/menu-mix/year=2026/month=04/menu-mix.parquet")
    top = df.loc[df["net_amount"].idxmax()]

    results = [
        check("total items",      len(df),                             40),
        check("total net_amount", round(df["net_amount"].sum()),       291829, tolerance=5),
        check("top item by rev",  top["item_name"],
              "Tunday Mutton Galawati Kabab- 4 Pcs"),
        check("top item revenue", round(top["net_amount"]),            44605,  tolerance=100),
        check("categories",       sorted(df["category"].unique()),
              ['Biryani', 'Breads', 'Combos', 'Kabab and Roasted',
               'Main Course', 'Rolls']),
    ]
    if all(results):
        print("   ✅ PASS — all April 2026 menu mix values match")
        passed += 1
    else:
        print("   ❌ FAIL — some values don't match")
        failed += 1
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    failed += 1

# ── 3. Online Orders April 2026 ───────────────────────────────────
print("\n3. Online Orders — April 2026")
try:
    df = read_parquet(f"{CLIENT}/online-orders/year=2026/month=04/online-orders.parquet")

    results = [
        check("unique orders",    df["order_key"].nunique(),           331,    tolerance=5),
        check("date min",         str(df["date"].min().date()),        "2026-04-01"),
        check("date max",         str(df["date"].max().date()),        "2026-04-30"),
        check("channels",         sorted(df["order_source"].unique()), ["Swiggy", "Zomato"]),
        check("Swiggy-Bolt raw",  "Swiggy-Bolt Urgent" not in
              df["order_source"].unique(),                             True),
    ]
    if all(results):
        print("   ✅ PASS — all April 2026 online orders values match")
        passed += 1
    else:
        print("   ❌ FAIL — some values don't match")
        failed += 1
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    failed += 1

# ── 4. Item Wise April 2026 ───────────────────────────────────────
print("\n4. Item Wise — April 2026")
try:
    df = read_parquet(f"{CLIENT}/item-wise/year=2026/month=04/item-wise.parquet")

    results = [
        check("date min",      str(df["date"].min().date()), "2026-04-01"),
        check("date max",      str(df["date"].max().date()), "2026-04-30"),
        check("unique days",   df["date"].nunique(),          30),
        check("qty > 0 only",  (df["quantity"] > 0).all(),   True),
    ]
    if all(results):
        print("   ✅ PASS — all April 2026 item wise values match")
        passed += 1
    else:
        print("   ❌ FAIL — some values don't match")
        failed += 1
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    failed += 1

# ── 5. Spot-check an older month — Jul 2025 menu mix ─────────────
print("\n5. Menu Mix — July 2025 (spot check older month)")
try:
    df = read_parquet(f"{CLIENT}/menu-mix/year=2025/month=07/menu-mix.parquet")

    results = [
        check("rows > 0",      len(df) > 0,                  True),
        check("total qty",     int(df["qty"].sum()),          1093),
        check("categories",    sorted(df["category"].unique()),
              ['Biryani', 'Breads', 'Combos', 'Kabab and Roasted',
               'Main Course', 'Rolls']),
    ]
    if all(results):
        print("   ✅ PASS — July 2025 menu mix values match")
        passed += 1
    else:
        print("   ❌ FAIL")
        failed += 1
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    failed += 1

# ── Summary ───────────────────────────────────────────────────────
print(f"\n{'='*65}")
print(f"Results: {passed}/{passed+failed} verification groups passed")
if failed == 0:
    print("✅ All Parquet files verified — data matches original Excel")
else:
    print("❌ Some checks failed — review output above")
print(f"{'='*65}")
