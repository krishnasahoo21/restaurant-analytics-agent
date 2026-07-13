#!/bin/bash

BUCKET="restaurant-agent-data-prod"
CLIENT="clients/tunday-kababi"
PROFILE="tunday"

echo "Processing all raw files through Lambda..."
echo "This triggers Lambda for each file via S3 upload"
echo ""

SUCCESS=0
FAILED=0

# Get list of all files in raw/
FILES=$(aws s3 ls s3://${BUCKET}/${CLIENT}/raw/ \
  --recursive --profile $PROFILE \
  | awk '{print $4}')

for KEY in $FILES; do
    # Skip .keep placeholder files
    if [[ "$KEY" == *".keep" ]]; then
        continue
    fi

    FILENAME=$(basename "$KEY")
    echo "Triggering: $FILENAME"

    # Download locally then re-upload to trigger Lambda
    # (this is the correct way to re-trigger on existing files)
    TMPFILE="/tmp/reupload_$(date +%s%N)"

    aws s3 cp "s3://${BUCKET}/${KEY}" "$TMPFILE" \
      --profile $PROFILE --quiet

    aws s3 cp "$TMPFILE" "s3://${BUCKET}/${KEY}" \
      --profile $PROFILE --quiet \
      --metadata "reprocessed=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    rm -f "$TMPFILE"

    if [ $? -eq 0 ]; then
        SUCCESS=$((SUCCESS + 1))
        echo "  ✅ Triggered"
    else
        FAILED=$((FAILED + 1))
        echo "  ❌ Failed to trigger"
    fi

    # Small delay to avoid overwhelming Lambda with simultaneous invocations
    sleep 2
done

echo ""
echo "Done. Triggered: $SUCCESS files, Failed: $FAILED"
echo "Wait 3-4 minutes then check processed/ for Parquet files"
