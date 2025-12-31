"""Check Claude usage command - checks usage against a threshold."""

import sys
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
        print(f"[FAIL] Usage ({usage_pct}%) exceeds threshold ({threshold}%)")
        sys.exit(1)
    else:
        print(f"[OK] Usage ({usage_pct}%) is within threshold ({threshold}%)")
        sys.exit(0)
