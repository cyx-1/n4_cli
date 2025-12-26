"""Clipboard command - displays and monitors clipboard content."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

import click
import pyperclip


def detect_clipboard_type(content):
    """Detect the type of clipboard content."""
    if not content:
        return "empty"

    # Check if it's JSON
    try:
        json.loads(content)
        return "json"
    except (json.JSONDecodeError, TypeError):
        pass

    # Check if it's HTML
    if content.strip().startswith(("<html", "<!DOCTYPE", "<div", "<span", "<p")):
        return "html"

    # Check if it's a file path
    if "\n" not in content and (Path(content.strip()).exists() or content.startswith(("http://", "https://", "file://"))):
        return "path/url"

    # Check if it's XML
    if content.strip().startswith("<?xml") or content.strip().startswith("<"):
        return "xml"

    # Default to text
    return "text"


def format_size(size):
    """Format byte size to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def display_clipboard_info(content, show_preview=True, max_preview=500):
    """Display detailed clipboard information."""
    if not content:
        click.echo(click.style("Clipboard is empty", fg="yellow"))
        return

    content_type = detect_clipboard_type(content)
    content_size = len(content.encode('utf-8'))
    line_count = content.count('\n') + 1

    # Header
    click.echo(click.style("━" * 60, fg="cyan"))
    click.echo(click.style("CLIPBOARD INFORMATION", fg="cyan", bold=True))
    click.echo(click.style("━" * 60, fg="cyan"))

    # Metadata
    click.echo(click.style("Type:        ", fg="white", bold=True) + click.style(content_type, fg="green"))
    click.echo(click.style("Size:        ", fg="white", bold=True) + click.style(format_size(content_size), fg="green"))
    click.echo(click.style("Lines:       ", fg="white", bold=True) + click.style(str(line_count), fg="green"))
    click.echo(click.style("Characters:  ", fg="white", bold=True) + click.style(str(len(content)), fg="green"))

    # Preview
    if show_preview:
        click.echo(click.style("\n" + "─" * 60, fg="cyan"))
        click.echo(click.style("CONTENT PREVIEW", fg="cyan", bold=True))
        click.echo(click.style("─" * 60, fg="cyan"))

        preview_content = content[:max_preview]
        if len(content) > max_preview:
            preview_content += click.style(f"\n\n... (truncated, {len(content) - max_preview} more characters)", fg="yellow")

        # Syntax highlighting for different types
        if content_type == "json":
            try:
                parsed = json.loads(content[:max_preview])
                preview_content = json.dumps(parsed, indent=2)
                click.echo(click.style(preview_content, fg="bright_blue"))
            except:
                click.echo(preview_content)
        elif content_type == "html" or content_type == "xml":
            click.echo(click.style(preview_content, fg="bright_magenta"))
        elif content_type == "path/url":
            click.echo(click.style(preview_content, fg="bright_cyan"))
        else:
            click.echo(preview_content)

    click.echo(click.style("\n" + "━" * 60, fg="cyan"))


@click.command()
@click.option("--web", "-w", is_flag=True, help="Open interactive web-based clipboard viewer")
@click.option("--monitor", "-m", is_flag=True, help="Monitor clipboard changes continuously")
@click.option("--raw", "-r", is_flag=True, help="Display raw clipboard content without formatting")
@click.option("--copy", "-c", metavar="TEXT", help="Copy text to clipboard")
@click.option("--clear", is_flag=True, help="Clear clipboard content")
@click.option("--interval", "-i", default=1.0, help="Monitoring interval in seconds (default: 1.0)")
def clipboard(web, monitor, raw, copy, clear, interval):
    """Display, monitor, and manage clipboard content.

    Examples:
      n4_cli clipboard              # Show current clipboard
      n4_cli clipboard --web        # Open web viewer
      n4_cli clipboard --monitor    # Watch for changes
      n4_cli clipboard --copy "Hi"  # Copy text
      n4_cli clipboard --clear      # Clear clipboard
    """
    # Handle copy operation
    if copy:
        pyperclip.copy(copy)
        click.echo(click.style(f"✓ Copied to clipboard: {copy[:50]}{'...' if len(copy) > 50 else ''}", fg="green"))
        return

    # Handle clear operation
    if clear:
        pyperclip.copy("")
        click.echo(click.style("✓ Clipboard cleared", fg="green"))
        return

    # Handle web viewer
    if web:
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
        return

    # Handle monitor mode
    if monitor:
        click.echo(click.style("Monitoring clipboard... (Press Ctrl+C to stop)", fg="cyan", bold=True))
        click.echo(click.style("─" * 60, fg="cyan"))
        last_content = ""

        try:
            while True:
                current_content = pyperclip.paste()

                if current_content != last_content:
                    click.echo(click.style(f"\n[{time.strftime('%H:%M:%S')}] Clipboard changed!", fg="green", bold=True))
                    display_clipboard_info(current_content, show_preview=not raw)
                    last_content = current_content

                time.sleep(interval)

        except KeyboardInterrupt:
            click.echo(click.style("\n\nMonitoring stopped.", fg="yellow"))
            return

    # Default: Display current clipboard
    else:
        content = pyperclip.paste()

        if raw:
            click.echo(content)
        else:
            display_clipboard_info(content)
