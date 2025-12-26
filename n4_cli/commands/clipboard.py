"""Clipboard command - displays current clipboard content."""

import click
import pyperclip


@click.command()
def clipboard():
    """Display current clipboard content."""
    clipboard_content = pyperclip.paste()
    click.echo(clipboard_content)
