"""
check_parquet_types.py
-----------------------
Reads every Parquet file from S3 and prints the actual
column dtypes pyarrow wrote. Run this to find type
inconsistencies across partitions before fixing Glue schema.

Run from project root with venv active:
    python3 check_parquet_types.py
"""

import boto3
import pandas as pd
import io

session  = boto3.Session(profile_name="tunday")
s3       = session.client("s3", region_name="us-west-2")
BUCKET   = "restaurant-agent-data-prod"
BASE     = "clients/tunday-kababi/processed"

TABLES = {
    "menu_mix":     ["item_name", "qty", "amount", "discount", "net_amount"],
    "item_wise":    ["item_name", "quantity", "revenue", "day"],
    "online_orders":["order_source", "quantity", "net_amount", "grand_total", "hour", "day"],
    "daily_sales":  ["net_sales", "total_revenue", "total_orders", "total_items_sold"],
}

for table, check_cols in TABLES.items():
    prefix = f"{BASE}/{table.replace('_', '-')}/"
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=BUCKET, Prefix=prefix)

    keys = []
    for page in pages:
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                keys.append(obj["Key"])

    if not keys:
        print(f"\n{table}: no parquet files found")
        continue

    print(f"\n{'='*70}")
    print(f"TABLE: {table}")
    print(f"{'='*70}")
    col_header = "  ".join(f"{c:<12}" for c in check_cols)
    print(f"{'Partition':<25}  {col_header}")
    print("-" * 70)

    type_sets = {col: set() for col in check_cols}

    for key in sorted(keys):
        partition = "/".join(key.split("/")[-3:-1])
        buf = io.BytesIO(
            s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
        )
        df = pd.read_parquet(buf)
        col_types = "  ".join(
            f"{str(df[c].dtype) if c in df.columns else 'MISSING':<12}"
            for c in check_cols
        )
        print(f"{partition:<25}  {col_types}")

        for col in check_cols:
            if col in df.columns:
                type_sets[col].add(str(df[col].dtype))

    print(f"\nType consistency per column:")
    all_consistent = True
    for col, types in type_sets.items():
        status = "✅" if len(types) == 1 else "❌ INCONSISTENT"
        print(f"  {col:<20} {status}  types found: {types}")
        if len(types) > 1:
            all_consistent = False

    if all_consistent:
        print(f"  ✅ All columns consistent across partitions")
    else:
        print(f"  ❌ Fix needed — inconsistent types across months")
