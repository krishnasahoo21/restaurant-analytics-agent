
"""
process_all.py
--------------
Triggers Lambda for all raw files by adding metadata tag on re-upload.
Uses boto3 directly — avoids Mac shell date format issues.
"""

import boto3
import io
import time

BUCKET  = "restaurant-agent-data-prod"
CLIENT  = "clients/tunday-kababi"
PROFILE = "tunday"

# Skip these — Lambda already handles them but let's not waste invocations
SKIP_EXTENSIONS = {".keep", ".DS_Store"}

session   = boto3.Session(profile_name=PROFILE)
s3        = session.client("s3", region_name="us-west-2")

# List all files in raw/
paginator = s3.get_paginator("list_objects_v2")
pages     = paginator.paginate(
    Bucket = BUCKET,
    Prefix = f"{CLIENT}/raw/"
)

keys = []
for page in pages:
    for obj in page.get("Contents", []):
        key      = obj["Key"]
        filename = key.split("/")[-1]

        # Skip placeholders and Mac hidden files
        if any(filename.endswith(ext) for ext in SKIP_EXTENSIONS):
            print(f"  SKIP: {filename}")
            continue
        if filename.startswith("."):
            continue

        keys.append(key)

print(f"\nFound {len(keys)} files to process\n")
print("="*60)

success = 0
failed  = 0

for key in keys:
    filename = key.split("/")[-1]
    print(f"Triggering: {filename[:60]}")

    try:
        # Download file content into memory
        response = s3.get_object(Bucket=BUCKET, Key=key)
        content  = response["Body"].read()

        # Re-upload with a reprocessed metadata tag
        # This changes the object metadata → valid PUT → triggers Lambda
        s3.put_object(
            Bucket   = BUCKET,
            Key      = key,
            Body     = content,
            Metadata = {"reprocessed": "true"}
        )
        print(f"  ✅ Triggered ({len(content)//1024}KB)")
        success += 1

    except Exception as e:
        print(f"  ❌ Failed: {e}")
        failed += 1

    # 2 second gap between files — Lambda can handle concurrent invocations
    # but this gives CloudWatch logs a clean separation for debugging
    time.sleep(2)

print(f"\n{'='*60}")
print(f"Done: {success} triggered, {failed} failed")
print(f"Wait 5 minutes then check processed/ for Parquet files")
