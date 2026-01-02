"""Check Claude usage command - checks usage against a threshold."""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import click
import yaml


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
    against the provided threshold. Exits with code 1 if usage exceeds
    threshold, otherwise exits with code 0.
    """
    usage_file = Path("./tmp/claude_usage.yaml")

    print(f"[INFO] Checking Claude usage against threshold: {threshold}%")
    print(f"[INFO] Looking for usage file at: {usage_file.absolute()}")

    # Check if the file exists
    if not usage_file.exists():
        print(f"[ERROR] Usage file not found: {usage_file}")
        sys.exit(1)

    print(f"[INFO] Found usage file: {usage_file}")

    # Read and parse the YAML file
    try:
        with open(usage_file, "r") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"[ERROR] Failed to parse YAML file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed to read file: {e}")
        sys.exit(1)

    print(f"[INFO] Successfully parsed YAML file")

    # Extract the usage percentage
    if "plan_usage_limit_session_pct" not in data:
        print("[ERROR] Missing 'plan_usage_limit_session_pct' key in YAML file")
        sys.exit(1)

    usage_pct = data["plan_usage_limit_session_pct"]
    reset_time = data.get("plan_usage_limit_reset_time", "N/A")

    print(f"[INFO] Current usage: {usage_pct}%")
    print(f"[INFO] Reset time: {reset_time}")
    print(f"[INFO] Threshold: {threshold}%")

    # Compare usage against threshold
    if usage_pct > threshold:
        print(f"[WARNING] Usage ({usage_pct}%) exceeds threshold ({threshold}%)")

        # Check if we have a valid reset time
        if reset_time == "N/A" or not reset_time:
            print("[ERROR] No reset time available - cannot calculate wait time")
            sys.exit(1)

        try:
            # Parse the reset time (expecting ISO format)
            reset_datetime = datetime.fromisoformat(reset_time.replace('Z', '+00:00'))

            # Calculate target time: 5 minutes after reset
            target_datetime = reset_datetime + timedelta(minutes=5)
            current_datetime = datetime.now(reset_datetime.tzinfo)

            print(f"[INFO] Usage limit reset time: {reset_datetime.isoformat()}")
            print(f"[INFO] Target resume time (reset + 5 mins): {target_datetime.isoformat()}")
            print(f"[INFO] Current time: {current_datetime.isoformat()}")

            # Calculate wait duration
            wait_seconds = (target_datetime - current_datetime).total_seconds()

            if wait_seconds > 0:
                wait_minutes = wait_seconds / 60
                print(f"[ACTION] Usage limit exceeded - waiting {wait_minutes:.1f} minutes until {target_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                print(f"[ACTION] This ensures we wait 5 minutes after the usage reset at {reset_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                print(f"[WAITING] Sleeping for {wait_seconds:.0f} seconds...")

                time.sleep(wait_seconds)

                print(f"[SUCCESS] Wait complete - current time is now 5+ minutes past the reset time")
                print(f"[OK] Proceeding with execution")
                sys.exit(0)
            else:
                print(f"[INFO] Target time has already passed (by {abs(wait_minutes):.1f} minutes)")
                print(f"[OK] Current time is already 5+ minutes past the reset time - proceeding")
                sys.exit(0)

        except (ValueError, AttributeError) as e:
            print(f"[ERROR] Failed to parse reset time '{reset_time}': {e}")
            sys.exit(1)
    else:
        print(f"[OK] Usage ({usage_pct}%) is within threshold ({threshold}%)")
        sys.exit(0)
