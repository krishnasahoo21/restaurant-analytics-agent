# Add this to process_all.py or run as a quick one-liner
import boto3

session = boto3.Session(profile_name="tunday")
s3 = session.client("s3", region_name="us-west-2")

BUCKET = "restaurant-agent-data-prod"
failing_keys = [
    "clients/tunday-kababi/raw/item-wise/Item_Wise_Enterprise(2025.11.01--2025.11.30) For Tunday Kababi - HUDA Gurgaon_6a3a32a997c8125d3d784604.xlsx",
    "clients/tunday-kababi/raw/item-wise/Item_Wise_Enterprise(2025.12.01--2025.12.31) For Tunday Kababi - HUDA Gurgaon_6a3a3292c393445d2b92dc9d.xlsx",
    "clients/tunday-kababi/raw/item-wise/Item_Wise_Enterprise(2026.04.01--2026.04.30) For Tunday Kababi - HUDA Gurgaon_6a0ab274f4056a70fee77962.xlsx",
]

# for key in failing_keys:
#     content = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
#     s3.put_object(Bucket=BUCKET, Key=key, Body=content, Metadata={"reprocessed": "v2"})
#     print(f"Triggered: {key.split('/')[-1][:50]}")

key = "clients/tunday-kababi/raw/online-orders/Online_Orders_Reports(2026.04.01--2026.04.30) For Tunday Kababi - HUDA Gurgaon_6a0ab3ac7547707116e278db.xlsx"
content = s3.get_object(Bucket="restaurant-agent-data-prod", Key=key)["Body"].read()
s3.put_object(Bucket="restaurant-agent-data-prod", Key=key, Body=content, Metadata={"reprocessed": "v3"})
print("Triggered Apr 2026 online orders")