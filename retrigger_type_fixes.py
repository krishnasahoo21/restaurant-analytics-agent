# retrigger_type_fixes.py
import boto3, time

session = boto3.Session(profile_name="tunday")
s3 = session.client("s3", region_name="us-west-2")
BUCKET = "restaurant-agent-data-prod"
BASE   = "clients/tunday-kababi/raw"

keys = [
    f"{BASE}/menu-mix/6a0ab18d067ed814fd1ceec0Enterprise_Menu_Mix_Report01.04.2026-30.04.20261.csv",
    f"{BASE}/online-orders/Online_Orders_Reports(2025.07.01--2025.07.31) For Tunday Kababi - HUDA Gurgaon_6a3a38b495d14162ec3b0017.xlsx",
]

for key in keys:
    print(f"Triggering: {key.split('/')[-1][:60]}")
    content = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    s3.put_object(Bucket=BUCKET, Key=key, Body=content,
                  Metadata={"reprocessed": "type-fix"})
    print(f"  ✅ Done")
    time.sleep(3)

print("\nWait 2 minutes then run check_parquet_types.py to verify")