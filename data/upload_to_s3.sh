#!/bin/bash

BUCKET="restaurant-agent-data-prod"
CLIENT="clients/tunday-kababi"
PROFILE="tunday"

echo "Uploading Daily Sales reports..."
aws s3 cp "Daily Sales report detailed/" \
  "s3://${BUCKET}/${CLIENT}/raw/daily-sales/" \
  --recursive --profile $PROFILE

echo "Uploading Menu Mix reports..."
aws s3 cp "Enterprise Menu mix/" \
  "s3://${BUCKET}/${CLIENT}/raw/menu-mix/" \
  --recursive --profile $PROFILE

echo "Uploading Item Wise reports..."
aws s3 cp "Item wise enterprise reports/" \
  "s3://${BUCKET}/${CLIENT}/raw/item-wise/" \
  --recursive --profile $PROFILE

echo "Uploading Online Order reports..."
aws s3 cp "Online order report/" \
  "s3://${BUCKET}/${CLIENT}/raw/online-orders/" \
  --recursive --profile $PROFILE

echo "Done. Verifying..."
aws s3 ls s3://${BUCKET}/${CLIENT}/raw/ --recursive \
  --profile $PROFILE | wc -l
echo "files uploaded"
