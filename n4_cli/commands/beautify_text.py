"""Beautify text command - formats and beautifies text content."""

import click


@click.command(name="beautify-text")
@click.argument("text", required=False)
@click.option("--json", "format_json", is_flag=True, help="Format as JSON")
@click.option("--xml", "format_xml", is_flag=True, help="Format as XML")
@click.option("--indent", default=2, help="Indentation spaces (default: 2)")
def beautify_text(text, format_json, format_xml, indent):
    """Beautify and format text content.

    If no text is provided, reads from clipboard.
    """
    import pyperclip

    input_text = text if text else pyperclip.paste()

    if not input_text:
        click.echo(click.style("Error: No text provided", fg="red"), err=True)
        raise click.Abort()

    try:
        if format_json:
            import json
            parsed = json.loads(input_text)
            beautified = json.dumps(parsed, indent=indent, ensure_ascii=False)
        elif format_xml:
            import xml.dom.minidom
            dom = xml.dom.minidom.parseString(input_text)
            beautified = dom.toprettyxml(indent=" " * indent)
        else:
            # Auto-detect format
            import json
            try:
                parsed = json.loads(input_text)
                beautified = json.dumps(parsed, indent=indent, ensure_ascii=False)
                click.echo(click.style("Detected format: JSON", fg="cyan"))
            except json.JSONDecodeError:
                beautified = input_text
                click.echo(click.style("Could not auto-detect format", fg="yellow"))

        click.echo(beautified)
        pyperclip.copy(beautified)
        click.echo(click.style("Copied to clipboard", fg="green"))
    except Exception as e:
        click.echo(click.style(f"Error beautifying text: {e}", fg="red"), err=True)
        raise click.Abort()
