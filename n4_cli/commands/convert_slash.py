"""Convert slash command - converts between different path formats."""

import click


@click.command(name="convert-slash")
@click.argument("path", required=False)
@click.option("--to-windows", is_flag=True, help="Convert to Windows-style paths (backslashes)")
@click.option("--to-unix", is_flag=True, help="Convert to Unix-style paths (forward slashes)")
def convert_slash(path, to_windows, to_unix):
    """Convert between different path slash formats.

    If no path is provided, reads from clipboard.
    """
    import pyperclip

    input_path = path if path else pyperclip.paste()

    if not input_path:
        click.echo(click.style("Error: No path provided", fg="red"), err=True)
        raise click.Abort()

    if to_windows:
        converted = input_path.replace("/", "\\")
        click.echo(converted)
        pyperclip.copy(converted)
        click.echo(click.style("Copied to clipboard", fg="green"))
    elif to_unix:
        converted = input_path.replace("\\", "/")
        click.echo(converted)
        pyperclip.copy(converted)
        click.echo(click.style("Copied to clipboard", fg="green"))
    else:
        # Auto-detect and toggle
        if "\\" in input_path:
            converted = input_path.replace("\\", "/")
            click.echo(f"Converted to Unix-style: {converted}")
        else:
            converted = input_path.replace("/", "\\")
            click.echo(f"Converted to Windows-style: {converted}")
        pyperclip.copy(converted)
        click.echo(click.style("Copied to clipboard", fg="green"))
