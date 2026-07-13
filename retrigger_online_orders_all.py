# Save as retrigger_online_orders_all.py
import boto3, time

session = boto3.Session(profile_name="tunday")
s3 = session.client("s3", region_name="us-west-2")
BUCKET = "restaurant-agent-data-prod"
PREFIX = "clients/tunday-kababi/raw/online-orders/"

# List all online orders files
paginator = s3.get_paginator("list_objects_v2")
pages = paginator.paginate(Bucket=BUCKET, Prefix=PREFIX)

keys = []
for page in pages:
    for obj in page.get("Contents", []):
        key = obj["Key"]
        filename = key.split("/")[-1]
        if filename.startswith(".") or filename.endswith(".keep"):
            continue
        keys.append(key)

print(f"Found {len(keys)} online orders files to retrigger\n")

for key in keys:
    filename = key.split("/")[-1][:60]
    print(f"Triggering: {filename}")
    content = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    s3.put_object(
        Bucket=BUCKET, Key=key, Body=content,
        Metadata={"reprocessed": "grand-total-float-fix"}
    )
    print(f"  ✅ Done")
    time.sleep(2)

print(f"\nAll {len(keys)} files retriggered.")
print("Wait 5 minutes then run check_parquet_types.py again.")