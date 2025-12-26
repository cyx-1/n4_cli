"""GitHub Copilot CLI command - integrations with GitHub Copilot CLI."""

import click


@click.command(name="github-copilot")
@click.argument("query", nargs=-1)
@click.option("--shell", "-s", is_flag=True, help="Generate shell commands")
@click.option("--git", "-g", is_flag=True, help="Generate git commands")
def github_copilot_cli(query, shell, git):
    """Query GitHub Copilot CLI for command suggestions.

    Examples:
      n4_cli github-copilot --shell "find large files"
      n4_cli github-copilot --git "undo last commit"
    """
    if not query:
        click.echo(click.style("Error: No query provided", fg="red"), err=True)
        raise click.Abort()

    query_text = " ".join(query)

    context = ""
    if shell:
        context = "shell"
    elif git:
        context = "git"
    else:
        context = "general"

    click.echo(f"Query ({context}): {query_text}")

    # TODO: Implement actual GitHub Copilot CLI integration
    click.echo(click.style("GitHub Copilot CLI integration not yet implemented", fg="yellow"))
    click.echo("This command will integrate with GitHub Copilot CLI")
