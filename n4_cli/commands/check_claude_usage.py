"""Check Claude usage command - checks usage against a threshold."""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import click
import yaml


def _check_usage_once(usage_file, threshold):
    """Attempt to check usage once. Returns True if check succeeded and usage is OK, False otherwise.

    Raises an exception with a descriptive message if the check cannot be performed.
    """
    # Check if the file exists
    if not usage_file.exists():
        raise FileNotFoundError(f"Usage file not found at: {usage_file}")

    print(f"[INFO] Found usage file: {usage_file}", flush=True)

    # Read and parse the YAML file
    try:
        with open(usage_file, "r") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML file: {e}")
    except Exception as e:
        raise IOError(f"Failed to read file: {e}")

    print(f"[INFO] Successfully parsed YAML file", flush=True)

    # Check for error indicators in the data
    if isinstance(data, dict):
        if data.get("error"):
            error_msg = data.get("error")
            raise RuntimeError(f"Error in usage data: {error_msg}")

        # Check if there's an indicator that we're out of tokens
        if data.get("insufficient_tokens") or data.get("rate_limited"):
            raise RuntimeError("Insufficient tokens available to check usage - API rate limited")

    # Extract the usage percentage
    if "plan_usage_limit_session_pct" not in data:
        raise KeyError("Missing 'plan_usage_limit_session_pct' key in YAML file")

    usage_pct = data["plan_usage_limit_session_pct"]
    reset_time = data.get("plan_usage_limit_reset_time", "N/A")

    print(f"[INFO] Current usage: {usage_pct}%", flush=True)
    print(f"[INFO] Reset time: {reset_time}", flush=True)
    print(f"[INFO] Threshold: {threshold}%", flush=True)

    # Compare usage against threshold
    if usage_pct > threshold:
        print(f"[WARNING] Usage ({usage_pct}%) exceeds threshold ({threshold}%)", flush=True)

        # Check if we have a valid reset time
        if reset_time == "N/A" or not reset_time:
            raise ValueError("No reset time available - cannot calculate wait time")

        try:
            # Parse the reset time (expecting ISO format)
            reset_datetime = datetime.fromisoformat(reset_time.replace('Z', '+00:00'))

            # Calculate target time: 5 minutes after reset
            target_datetime = reset_datetime + timedelta(minutes=5)
            current_datetime = datetime.now(reset_datetime.tzinfo)

            print(f"[INFO] Usage limit reset time: {reset_datetime.isoformat()}", flush=True)
            print(f"[INFO] Target resume time (reset + 5 mins): {target_datetime.isoformat()}", flush=True)
            print(f"[INFO] Current time: {current_datetime.isoformat()}", flush=True)

            # Calculate wait duration
            wait_seconds = (target_datetime - current_datetime).total_seconds()

            if wait_seconds > 0:
                wait_minutes = wait_seconds / 60
                print(f"[ACTION] Usage limit exceeded - waiting {wait_minutes:.1f} minutes until {target_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}", flush=True)
                print(f"[ACTION] This ensures we wait 5 minutes after the usage reset at {reset_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}", flush=True)
                print(f"[WAITING] Sleeping for {wait_seconds:.0f} seconds...", flush=True)

                time.sleep(wait_seconds)

                print(f"[SUCCESS] Wait complete - current time is now 5+ minutes past the reset time", flush=True)
                print(f"[OK] Proceeding with execution", flush=True)
                return True
            else:
                print(f"[INFO] Target time has already passed (by {abs(wait_minutes):.1f} minutes)", flush=True)
                print(f"[OK] Current time is already 5+ minutes past the reset time - proceeding", flush=True)
                return True

        except (ValueError, AttributeError) as e:
            raise ValueError(f"Failed to parse reset time '{reset_time}': {e}")
    else:
        print(f"[OK] Usage ({usage_pct}%) is within threshold ({threshold}%)", flush=True)
        return True


@click.command(name="check-claude-usage")
@click.option(
    "--threshold",
    "-t",
    type=float,
    required=True,
    help="Usage percentage threshold to check against",
)
def check_claude_usage(threshold):
    """Check Claude usage percentage against a threshold.

    Reads ./tmp/claude_usage.yaml and compares plan_usage_limit_session_pct
    against the provided threshold. If usage cannot be checked (e.g., insufficient
    tokens), retries every 15 minutes. If usage exceeds threshold, waits until
    5 minutes after the reset time.
    """
    usage_file = Path("./tmp/claude_usage.yaml")
    retry_interval_minutes = 15
    retry_interval_seconds = retry_interval_minutes * 60
    attempt = 1

    print(f"[INFO] Starting Claude usage check against threshold: {threshold}%", flush=True)
    print(f"[INFO] Looking for usage file at: {usage_file.absolute()}", flush=True)
    print(f"[INFO] Will retry every {retry_interval_minutes} minutes if unable to check usage", flush=True)
    print("", flush=True)

    while True:
        print(f"[ATTEMPT #{attempt}] Checking Claude usage at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

        try:
            # Attempt to check usage
            if _check_usage_once(usage_file, threshold):
                # Success - usage is within limits
                sys.exit(0)

        except (FileNotFoundError, ValueError, KeyError, IOError, RuntimeError) as e:
            # Failed to check usage - log the error clearly
            print("", flush=True)
            print("=" * 80, flush=True)
            print("[ERROR] UNABLE TO CHECK CLAUDE USAGE", flush=True)
            print("=" * 80, flush=True)
            print(f"[ERROR] Reason: {str(e)}", flush=True)
            print(f"[ERROR] This typically means:", flush=True)
            print(f"[ERROR]   - Not enough tokens available to query usage API", flush=True)
            print(f"[ERROR]   - Usage file is corrupted or missing", flush=True)
            print(f"[ERROR]   - API rate limit has been hit", flush=True)
            print("", flush=True)
            print(f"[ACTION] Will retry checking usage in {retry_interval_minutes} minutes", flush=True)
            print(f"[ACTION] Next check at: {(datetime.now() + timedelta(minutes=retry_interval_minutes)).strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
            print("=" * 80, flush=True)
            print(f"[WAITING] Sleeping for {retry_interval_seconds} seconds ({retry_interval_minutes} minutes)...", flush=True)
            print("", flush=True)

            time.sleep(retry_interval_seconds)
            attempt += 1
            continue

        except Exception as e:
            # Unexpected error
            print("", flush=True)
            print("=" * 80, flush=True)
            print("[ERROR] UNEXPECTED ERROR WHILE CHECKING USAGE", flush=True)
            print("=" * 80, flush=True)
            print(f"[ERROR] {type(e).__name__}: {str(e)}", flush=True)
            print(f"[ACTION] Will retry in {retry_interval_minutes} minutes", flush=True)
            print("=" * 80, flush=True)
            print(f"[WAITING] Sleeping for {retry_interval_seconds} seconds...", flush=True)
            print("", flush=True)

            time.sleep(retry_interval_seconds)
            attempt += 1
            continue
