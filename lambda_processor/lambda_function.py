"""
lambda_function.py
-------------------
AWS Lambda entry point for the restaurant data processing pipeline.

Triggered by: S3 PutObject events on the raw/ prefix
Does:
    1. Parses the S3 event to get bucket + key
    2. Extracts filename metadata (report_type, year, month)
    3. Downloads the file from S3 to /tmp/
    4. Routes to the correct parser
    5. Writes clean Parquet to processed/ with Hive partitioning
    6. Returns structured success/failure response

CloudWatch logging:
    Every print() statement here appears automatically in CloudWatch
    Logs under /aws/lambda/restaurant-data-processor
    This is how you monitor what's happening in production

S3 path conventions:
    Input:  clients/{client}/raw/{report_type}/{original_filename}
    Output: clients/{client}/processed/{report_type}/year={year}/month={month}/{report_type}.parquet

Example:
    Input:  clients/tunday-kababi/raw/menu-mix/Menu_Mix(2025.07.01...).xlsx
    Output: clients/tunday-kababi/processed/menu-mix/year=2025/month=07/menu-mix.parquet
"""

import json
import os
import traceback
from pathlib import Path
import boto3
import pandas as pd

# Import our parsers
# These live in the same Lambda deployment package as this file
from filename_parser import parse_filename
from parsers.menu_mix import parse_menu_mix
from parsers.daily_sales import parse_daily_sales
from parsers.item_wise import parse_item_wise
from parsers.online_orders import parse_online_orders


# ── Constants ──────────────────────────────────────────────────────────────
# /tmp is the only writable directory in a Lambda execution environment
# Max 512MB by default, expandable to 10GB if needed
TMP_DIR = Path("/tmp")

# Valid report types — anything else gets rejected immediately
VALID_REPORT_TYPES = {"menu-mix", "daily-sales", "item-wise", "online-orders"}

# File types we handle — anything else (e.g. .keep placeholder files) is
# silently skipped rather than causing an error
VALID_EXTENSIONS = {".xlsx", ".csv"}


def lambda_handler(event, context):
    """
    Main Lambda entry point. AWS calls this function on every S3 upload.

    Args:
        event:   S3 event dict from AWS (see module docstring for shape)
        context: Lambda runtime context (used for request_id in logs)

    Returns:
        dict with statusCode and body — standard Lambda response format
    """
    request_id = context.aws_request_id if context else "local-test"
    print(f"[{request_id}] Lambda invoked — processing S3 event")

    # ── Extract S3 details from event ─────────────────────────────────
    try:
        record    = event["Records"][0]
        bucket    = record["s3"]["bucket"]["name"]
        # S3 keys with spaces come URL-encoded — decode them
        s3_key    = record["s3"]["object"]["key"].replace("+", " ")
        from urllib.parse import unquote_plus
        s3_key    = unquote_plus(s3_key)
    except (KeyError, IndexError) as e:
        print(f"[{request_id}] ERROR: Malformed S3 event — {e}")
        print(f"[{request_id}] Event received: {json.dumps(event)}")
        return _response(400, "Malformed S3 event", s3_key=None)

    print(f"[{request_id}] Bucket: {bucket}")
    print(f"[{request_id}] Key: {s3_key}")

    # ── Skip non-data files ────────────────────────────────────────────
    # .keep placeholder files trigger this Lambda too — skip them cleanly
    filename  = s3_key.split("/")[-1]
    extension = Path(filename).suffix.lower()

    if extension not in VALID_EXTENSIONS:
        print(f"[{request_id}] Skipping non-data file: {filename}")
        return _response(200, f"Skipped non-data file: {filename}", s3_key)

    # ── Skip reference/ and other non-raw/ paths ───────────────────────
    # Only process files under raw/ — reference/ files (item_master etc.)
    # are not passed through the monthly processing pipeline
    if "/raw/" not in s3_key:
        print(f"[{request_id}] Skipping non-raw path: {s3_key}")
        return _response(200, f"Skipped non-raw path", s3_key)

    # ── Parse filename to get metadata ─────────────────────────────────
    try:
        metadata     = parse_filename(filename)
        report_type  = metadata["report_type"]
        year         = metadata["year"]
        month        = metadata["month"]
    except ValueError as e:
        print(f"[{request_id}] ERROR: Cannot parse filename '{filename}' — {e}")
        return _response(400, f"Filename parse failed: {e}", s3_key)

    print(f"[{request_id}] Parsed metadata: type={report_type} year={year} month={month}")

    if report_type not in VALID_REPORT_TYPES:
        print(f"[{request_id}] ERROR: Unknown report type '{report_type}'")
        return _response(400, f"Unknown report type: {report_type}", s3_key)

    # ── Extract client identifier from S3 key path ─────────────────────
    # Key structure: clients/{client}/raw/{report_type}/{filename}
    # We need {client} for the output path
    try:
        parts  = s3_key.split("/")
        client = parts[1]   # e.g. "tunday-kababi"
    except IndexError:
        print(f"[{request_id}] ERROR: Cannot extract client from key: {s3_key}")
        return _response(400, f"Cannot extract client from S3 key", s3_key)

    # ── Download file from S3 to /tmp/ ─────────────────────────────────
    local_path = TMP_DIR / filename
    try:
        s3_client = boto3.client("s3")
        print(f"[{request_id}] Downloading s3://{bucket}/{s3_key} → {local_path}")
        s3_client.download_file(bucket, s3_key, str(local_path))
        file_size_kb = local_path.stat().st_size // 1024
        print(f"[{request_id}] Downloaded: {file_size_kb}KB")
    except Exception as e:
        print(f"[{request_id}] ERROR: S3 download failed — {e}")
        return _response(500, f"S3 download failed: {e}", s3_key)

    # ── Route to correct parser ────────────────────────────────────────
    try:
        print(f"[{request_id}] Parsing with {report_type} parser...")
        df = _route_to_parser(
            report_type = report_type,
            local_path  = str(local_path),
            extension   = extension,
            year        = year,
            month       = month,
            request_id  = request_id
        )
        print(f"[{request_id}] Parsed: {len(df)} rows, {len(df.columns)} columns")
    except Exception as e:
        print(f"[{request_id}] ERROR: Parsing failed — {e}")
        print(traceback.format_exc())
        _cleanup(local_path)
        return _response(500, f"Parsing failed: {e}", s3_key)

    # ── Write Parquet to processed/ ────────────────────────────────────
    try:
        output_key = (
            f"clients/{client}/processed/{report_type}/"
            f"year={year}/month={month}/{report_type}.parquet"
        )
        output_local = TMP_DIR / f"{report_type}_{year}_{month}.parquet"

        df.to_parquet(str(output_local), index=False, engine="pyarrow")

        parquet_size_kb = output_local.stat().st_size // 1024
        print(f"[{request_id}] Parquet written locally: {parquet_size_kb}KB")

        print(f"[{request_id}] Uploading to s3://{bucket}/{output_key}")
        s3_client.upload_file(str(output_local), bucket, output_key)
        print(f"[{request_id}] ✅ Upload complete")

    except Exception as e:
        print(f"[{request_id}] ERROR: Parquet write/upload failed — {e}")
        print(traceback.format_exc())
        _cleanup(local_path, output_local)
        return _response(500, f"Parquet write failed: {e}", s3_key)

    finally:
        # Always clean up /tmp — Lambda reuses execution environments
        # between invocations and /tmp persists. Without cleanup, repeated
        # uploads of the same report type would accumulate stale files.
        _cleanup(local_path, output_local if 'output_local' in dir() else None)

    return _response(200, "Success", s3_key, output_key=output_key, rows=len(df))


def _route_to_parser(
    report_type: str,
    local_path:  str,
    extension:   str,
    year:        str,
    month:       str,
    request_id:  str
) -> pd.DataFrame:
    """
    Routes a downloaded file to the correct parser.

    Returns a clean DataFrame regardless of report_type.
    All parsers guarantee the same contract:
        - Returns a pandas DataFrame
        - No raw Excel metadata rows
        - Numeric columns are numeric types
        - String columns are stripped
        - Never raises silently — exceptions bubble up to lambda_handler
    """
    if report_type == "menu-mix":
        file_format = "csv" if extension == ".csv" else "xlsx"
        print(f"[{request_id}]   menu-mix format: {file_format}")
        return parse_menu_mix(local_path, file_format)

    elif report_type == "daily-sales":
        # daily_sales parser returns a dict (one KPI summary per month),
        # not a DataFrame — because the source file is a monthly summary
        # report, not a row-per-transaction file. We wrap it in a
        # single-row DataFrame for Parquet storage so Athena can query
        # it the same way as all other report types.
        import json as _json
        result_dict = parse_daily_sales(local_path)
        # Flatten nested dicts (channel_split, category_split) to JSON
        # strings so they fit cleanly in a single Parquet column.
        # Athena can parse these JSON strings later if needed.
        flat = {
            "net_sales":        result_dict["net_sales"],
            "total_revenue":    result_dict["total_revenue"],
            "total_orders":     result_dict["total_orders"],
            "avg_order_value":  result_dict["avg_order_value"],
            "total_discounts":  result_dict["total_discounts"],
            "total_items_sold": result_dict["total_items_sold"],
            "channel_split":    _json.dumps(result_dict["channel_split"]),
            "category_split":   _json.dumps(result_dict["category_split"]),
            "year":             int(year),
            "month":            int(month),
        }
        return pd.DataFrame([flat])

    elif report_type == "item-wise":
        return parse_item_wise(local_path, year=year, month=month)

    elif report_type == "online-orders":
        return parse_online_orders(local_path)

    else:
        # Should never reach here — caught before this function is called
        raise ValueError(f"No parser registered for report_type: {report_type}")


def _response(
    status_code: int,
    message:     str,
    s3_key,
    output_key:  str = None,
    rows:        int = None
) -> dict:
    """
    Builds a structured Lambda response dict.
    The body is JSON — useful when Lambda is invoked via API Gateway
    or tested directly from the AWS Console.
    """
    body = {
        "message":    message,
        "input_key":  s3_key,
        "output_key": output_key,
        "rows":       rows
    }
    print(f"Response: {status_code} — {message}")
    return {
        "statusCode": status_code,
        "body": json.dumps(body)
    }


def _cleanup(*paths):
    """Remove temp files from /tmp after processing."""
    for path in paths:
        if path and Path(path).exists():
            try:
                Path(path).unlink()
            except Exception:
                pass  # Non-critical, Lambda will clean up eventually
