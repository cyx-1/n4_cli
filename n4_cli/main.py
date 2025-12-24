#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pyyaml",
#   "requests",
#   "pyperclip",
# ]
# ///
"""
CLI tool that reads configuration from ~/.n4_cli and performs HTTP GET requests.
Also reads and prints clipboard content.
"""

import os
from pathlib import Path

import pyperclip
import requests
import yaml


def main():
    """Read n4_service URL from config and perform HTTP GET request, then print clipboard content."""
    config_path = Path.home() / ".n4_cli"
    
    if not config_path.exists():
        print(f"Error: Configuration file not found at {config_path}")
        return
    
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return
    except IOError as e:
        print(f"Error reading configuration file: {e}")
        return
    
    if not config or "n4_service" not in config:
        print("Error: 'n4_service' key not found in configuration file")
        return
    
    service_url = config["n4_service"]
    print(f"Getting information from: {service_url}") 
    try:
        response = requests.get(service_url)
        response.raise_for_status()
        print(response.text)
    except requests.exceptions.RequestException as e:
        print(f"Error making HTTP request: {e}")
    
    # Print clipboard content
    clipboard_content = pyperclip.paste()
    print(clipboard_content)


if __name__ == "__main__":
    main()
