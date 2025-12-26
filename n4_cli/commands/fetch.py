"""Fetch command - retrieves information from n4_service."""

from pathlib import Path

import click
import pyperclip
import requests
import yaml


@click.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to configuration file (defaults to ~/.n4_cli)",
)
def fetch(config):
    """Fetch information from n4_service and display clipboard content."""
    config_path = config if config else Path.home() / ".n4_cli"

    if not config_path.exists():
        click.echo(
            click.style(
                f"Error: Configuration file not found at {config_path}",
                fg="red",
            ),
            err=True,
        )
        raise click.Abort()

    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        click.echo(
            click.style(f"Error parsing YAML file: {e}", fg="red"),
            err=True,
        )
        raise click.Abort()
    except IOError as e:
        click.echo(
            click.style(f"Error reading configuration file: {e}", fg="red"),
            err=True,
        )
        raise click.Abort()

    if not config_data or "n4_service" not in config_data:
        click.echo(
            click.style(
                "Error: 'n4_service' key not found in configuration file",
                fg="red",
            ),
            err=True,
        )
        raise click.Abort()

    service_url = config_data["n4_service"]
    click.echo(f"Getting information from: {service_url}")

    try:
        response = requests.get(service_url)
        response.raise_for_status()
        click.echo(response.text)
    except requests.exceptions.RequestException as e:
        click.echo(
            click.style(f"Error making HTTP request: {e}", fg="red"),
            err=True,
        )
        raise click.Abort()

    # Print clipboard content
    clipboard_content = pyperclip.paste()
    click.echo(clipboard_content)
