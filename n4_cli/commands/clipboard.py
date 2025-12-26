"""Clipboard command - opens interactive web-based clipboard viewer."""

from pathlib import Path

import click
import webbrowser


@click.command()
def clipboard():
    """Open interactive web-based clipboard format viewer.

    Opens a browser window showing all available clipboard formats including:
    - Text formats (plain, HTML, RTF)
    - Images and screenshots
    - Files with metadata
    - Multiple format inspection

    Based on Simon Willison's clipboard-viewer tool.
    """
    # Get the HTML file path
    assets_dir = Path(__file__).parent.parent / "assets"
    html_file = assets_dir / "clipboard-viewer.html"

    if not html_file.exists():
        click.echo(click.style("Error: clipboard-viewer.html not found in assets", fg="red"), err=True)
        raise click.Abort()

    # Open in default browser
    try:
        click.echo(click.style("Opening clipboard viewer in browser...", fg="cyan"))
        webbrowser.open(f"file://{html_file.absolute()}")
        click.echo(click.style(f"✓ Opened: {html_file}", fg="green"))
        click.echo(click.style("\nThe viewer is now open in your browser.", fg="yellow"))
        click.echo(click.style("Paste (Ctrl+V / Cmd+V) to see clipboard formats.", fg="yellow"))
    except Exception as e:
        click.echo(click.style(f"Error opening browser: {e}", fg="red"), err=True)
        raise click.Abort()
