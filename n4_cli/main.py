#!/usr/bin/env python3
# /// script
# dependencies = [
#   "click",
#   "prompt-toolkit",
#   "pyyaml",
#   "requests",
#   "pyperclip",
# ]
# ///
"""
CLI tool with modular commands and interactive command selection.
"""

import importlib
import pkgutil
from pathlib import Path

import click
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter


def load_commands():
    """Dynamically load all commands from the commands package."""
    commands = {}
    commands_package = importlib.import_module("n4_cli.commands")
    commands_path = Path(commands_package.__file__).parent

    # Iterate through all Python files in the commands directory
    for module_info in pkgutil.iter_modules([str(commands_path)]):
        if module_info.name.startswith("_"):
            continue

        # Import the module
        module = importlib.import_module(f"n4_cli.commands.{module_info.name}")

        # Find Click commands in the module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, click.Command):
                # Use the command name if set, otherwise use the function name
                command_name = getattr(attr, "name", attr_name)
                commands[command_name] = attr
                break

    return commands


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """n4_cli - A modular command-line tool with interactive command selection.

    Run without arguments to enter interactive mode with typeahead completion.
    """
    if ctx.invoked_subcommand is None:
        # Enter interactive mode
        interactive_mode(ctx)


def interactive_mode(ctx):
    """Interactive mode with typeahead command selection."""
    commands = load_commands()
    command_names = sorted(commands.keys())

    # Create completer for typeahead
    completer = WordCompleter(command_names, ignore_case=True)

    click.echo(click.style("n4_cli - Interactive Mode", fg="cyan", bold=True))
    click.echo(click.style(f"Available commands: {', '.join(command_names)}", fg="green"))
    click.echo(click.style("Type a command name (with Tab completion) or 'exit' to quit", fg="yellow"))
    click.echo()

    while True:
        try:
            # Prompt with typeahead completion
            user_input = prompt(
                "n4_cli> ",
                completer=completer,
                complete_while_typing=True,
            ).strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                click.echo(click.style("Goodbye!", fg="cyan"))
                break

            # Parse the input to get command and arguments
            parts = user_input.split()
            command_name = parts[0]
            args = parts[1:] if len(parts) > 1 else []

            if command_name in commands:
                # Execute the command
                try:
                    # Create a new context for the command
                    cmd = commands[command_name]
                    ctx.invoke(cmd, *args)
                except click.exceptions.ClickException as e:
                    e.show()
                except Exception as e:
                    click.echo(click.style(f"Error executing command: {e}", fg="red"), err=True)
            else:
                click.echo(
                    click.style(f"Unknown command: {command_name}", fg="red"),
                    err=True,
                )
                click.echo(f"Available commands: {', '.join(command_names)}")

            click.echo()  # Add blank line after command output

        except KeyboardInterrupt:
            click.echo()
            click.echo(click.style("Use 'exit' to quit", fg="yellow"))
        except EOFError:
            click.echo()
            click.echo(click.style("Goodbye!", fg="cyan"))
            break


def register_commands(cli_group):
    """Register all commands to the CLI group."""
    commands = load_commands()
    for command_name, command in commands.items():
        cli_group.add_command(command, name=command_name)


# Register all commands
register_commands(cli)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
