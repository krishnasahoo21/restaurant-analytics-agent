"""
athena_client.py
-----------------
Athena query runner used by all athena_tools.py functions.

Handles:
  - Connection (local dev via AWS profile, Lambda via IAM role)
  - Async query polling (Athena submits then you poll for results)
  - Result parsing (Athena returns everything as strings)
  - Error handling (returns error dict, never raises)
  - Cost guardrails (timeout after 60 seconds)

Usage:
    from src.athena_client import run_query

    rows = run_query("SELECT * FROM tunday_kababi.daily_sales LIMIT 5")
    # Returns: [{"net_sales": "245771.0", "total_orders": "437", ...}]
    # All values are strings — tools handle type conversion
"""

import os
import time
import boto3


# ── Config ─────────────────────────────────────────────────────────────────
DATABASE        = "tunday_kababi"
WORKGROUP       = "primary"
REGION          = "us-west-2"
POLL_INTERVAL   = 0.5    # seconds between status checks
MAX_WAIT        = 60     # seconds before timeout
MAX_RETRIES     = 2      # retry transient failures


def _get_client():
    """
    Returns a boto3 Athena client.

    Local dev:  reads AWS_PROFILE env var (set in .env as "tunday")
                falls back to default profile if not set
    Lambda:     no profile needed — uses execution role automatically
                AWS_PROFILE will not be set in Lambda environment
    """
    profile = os.environ.get("AWS_PROFILE", None)
    if profile:
        session = boto3.Session(profile_name=profile)
    else:
        session = boto3.Session()
    return session.client("athena", region_name=REGION)


def _parse_results(response: dict) -> list[dict]:
    """
    Converts Athena's raw ResultSet into a list of dicts.

    Athena returns:
        rows[0] = column headers
        rows[1:] = data rows, all values as strings

    Returns:
        [{"col1": "val1", "col2": "val2"}, ...]
        Empty list if no data rows.
    """
    rows    = response["ResultSet"]["Rows"]
    if not rows:
        return []

    headers = [col["VarCharValue"] for col in rows[0]["Data"]]
    records = []

    for row in rows[1:]:
        values = [
            col.get("VarCharValue", None)
            for col in row["Data"]
        ]
        records.append(dict(zip(headers, values)))

    return records


def run_query(sql: str, database: str = DATABASE) -> list[dict] | dict:
    """
    Executes a SQL query on Athena and returns results.

    Args:
        sql:      SQL query string
        database: Glue database name (default: tunday_kababi)

    Returns:
        list of dicts on success — one dict per result row
        error dict on failure   — {"error": "reason"}

    All values in result dicts are strings.
    Tools are responsible for converting to int/float as needed.

    Example:
        rows = run_query(\"\"\"
            SELECT year, month, net_sales
            FROM tunday_kababi.daily_sales
            WHERE year = '2026' AND month = '04'
        \"\"\")

        if isinstance(rows, dict) and "error" in rows:
            return rows  # propagate error to agent

        net_sales = float(rows[0]["net_sales"])
    """
    client  = _get_client()
    attempt = 0

    while attempt <= MAX_RETRIES:
        attempt += 1
        try:
            # ── Submit query ───────────────────────────────────────────
            response = client.start_query_execution(
                QueryString             = sql,
                QueryExecutionContext   = {"Database": database},
                WorkGroup               = WORKGROUP
            )
            execution_id = response["QueryExecutionId"]

            # ── Poll until complete ────────────────────────────────────
            # Athena is asynchronous — submit returns immediately,
            # we poll every 500ms until the query finishes or times out
            elapsed = 0
            while elapsed < MAX_WAIT:
                status_response = client.get_query_execution(
                    QueryExecutionId=execution_id
                )
                state = (
                    status_response["QueryExecution"]
                    ["Status"]["State"]
                )

                if state == "SUCCEEDED":
                    break

                elif state in ("FAILED", "CANCELLED"):
                    reason = (
                        status_response["QueryExecution"]
                        ["Status"]
                        .get("StateChangeReason", "Unknown reason")
                    )
                    # Don't retry FAILED queries — syntax/schema errors
                    # won't be fixed by retrying
                    return {
                        "error": f"Athena query failed: {reason}",
                        "sql":   sql[:200]
                    }

                time.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL

            else:
                # Timeout — query took too long
                # Try to cancel it to avoid unnecessary cost
                try:
                    client.stop_query_execution(
                        QueryExecutionId=execution_id
                    )
                except Exception:
                    pass
                return {
                    "error": (
                        f"Athena query timed out after {MAX_WAIT}s. "
                        f"Query may be too broad — try adding "
                        f"year/month filters."
                    )
                }

            # ── Fetch results ──────────────────────────────────────────
            results_response = client.get_query_results(
                QueryExecutionId=execution_id
            )
            return _parse_results(results_response)

        except client.exceptions.InvalidRequestException as e:
            # Bad SQL or missing table — don't retry
            return {"error": f"Invalid Athena request: {str(e)}"}

        except Exception as e:
            # Transient error (network, throttling) — retry
            if attempt <= MAX_RETRIES:
                time.sleep(2 ** attempt)   # exponential backoff
                continue
            return {
                "error": (
                    f"Athena query failed after {MAX_RETRIES} retries: "
                    f"{str(e)}"
                )
            }

    return {"error": "Max retries exceeded"}


# ── Type conversion helpers ────────────────────────────────────────────────
# Athena returns all values as strings.
# These helpers let tools convert cleanly without repetitive try/except.

def to_float(value: str | None, default: float = 0.0) -> float:
    """Convert Athena string result to float."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def to_int(value: str | None, default: int = 0) -> int:
    """Convert Athena string result to int."""
    try:
        return int(float(value)) if value is not None else default
    except (ValueError, TypeError):
        return default


def to_str(value: str | None, default: str = "") -> str:
    """Safely return string value from Athena result."""
    return value if value is not None else default
