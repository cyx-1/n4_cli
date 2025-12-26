"""Codex command - integrations with OpenAI Codex."""

import click


@click.command()
@click.argument("query", required=False)
@click.option("--language", "-l", help="Programming language context")
def codex(query, language):
    """Query OpenAI Codex for code generation and assistance.

    If no query is provided, reads from clipboard.
    """
    import pyperclip

    input_query = query if query else pyperclip.paste()

    if not input_query:
        click.echo(click.style("Error: No query provided", fg="red"), err=True)
        raise click.Abort()

    click.echo(f"Query: {input_query}")
    if language:
        click.echo(f"Language context: {language}")

    # TODO: Implement actual Codex integration
    click.echo(click.style("Codex integration not yet implemented", fg="yellow"))
    click.echo("This command will integrate with OpenAI Codex API")
