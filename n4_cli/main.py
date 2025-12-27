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
from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.styles import Style


def load_commands():
    """Dynamically load all commands from the commands package with descriptions."""
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
                # Extract short description from docstring
                description = ""
                if attr.help:
                    # Use the first line of the help text
                    description = attr.help.split('\n')[0].strip()

                commands[command_name] = {
                    'command': attr,
                    'description': description
                }
                break

    return commands


def fuzzy_match(query, text, description=""):
    """Fuzzy matching - searches both command name and description."""
    if not query:
        return True, 0

    query = query.lower()
    text_lower = text.lower()
    description_lower = description.lower() if description else ""

    # Combine text for searching
    combined_text = f"{text_lower} {description_lower}"

    # Exact match on name gets highest score
    if query == text_lower:
        return True, 1000

    # Starts with query on name gets high score
    if text_lower.startswith(query):
        return True, 500

    # Contains query in name gets medium-high score
    if query in text_lower:
        return True, 400

    # Contains query in description gets medium score
    if description_lower and query in description_lower:
        return True, 200

    # Fuzzy match - all characters appear in order in combined text
    query_idx = 0
    score = 0
    for i, char in enumerate(combined_text):
        if query_idx < len(query) and char == query[query_idx]:
            score += (10 - min(i, 10))  # Earlier matches get higher scores
            query_idx += 1

    if query_idx == len(query):
        return True, score

    return False, 0


def get_matching_commands(commands, query):
    """Get all matching commands based on fuzzy search."""
    matches = []

    for cmd_name, cmd_info in commands.items():
        is_match, score = fuzzy_match(query, cmd_name, cmd_info['description'])
        if is_match:
            matches.append((cmd_name, cmd_info, score))

    # Sort by score (descending) and then alphabetically
    matches.sort(key=lambda x: (-x[2], x[0]))

    return [(name, info) for name, info, _ in matches]


@click.group(invoke_without_command=True, context_settings={'max_content_width': 120})
@click.pass_context
def cli(ctx):
    """n4_cli - A modular command-line tool with interactive command selection.

    Run without arguments to enter interactive mode with typeahead completion.
    """
    if ctx.invoked_subcommand is None:
        # Enter interactive mode
        interactive_mode(ctx)


def interactive_mode(ctx):
    """Interactive mode with numbered dynamic choices and arrow key navigation."""
    commands = load_commands()
    all_command_names = sorted(commands.keys())

    # Configuration
    MAX_VISIBLE_CHOICES = 5

    # State management
    class AppState:
        selected_idx = 0
        scroll_offset = 0
        selected_command = None
        should_exit = False

    state = AppState()

    # Create buffer for input
    input_buffer = Buffer(
        multiline=False,
        on_text_changed=lambda _: (
            setattr(state, 'selected_idx', 0),
            setattr(state, 'scroll_offset', 0)
        ),
    )

    # Create key bindings
    kb = KeyBindings()

    def get_current_choices():
        """Get current matching commands based on input."""
        query = input_buffer.text
        choices = get_matching_commands(commands, query)
        if not choices:
            choices = [(name, commands[name]) for name in all_command_names]
        return choices

    def get_visible_choices():
        """Get the visible window of choices."""
        all_choices = get_current_choices()
        start = state.scroll_offset
        end = start + MAX_VISIBLE_CHOICES
        return all_choices[start:end], len(all_choices)

    @kb.add('up')
    def move_up(event):
        """Move selection up."""
        all_choices = get_current_choices()
        if state.selected_idx > 0:
            state.selected_idx -= 1
            # Scroll up if needed
            if state.selected_idx < state.scroll_offset:
                state.scroll_offset = state.selected_idx

    @kb.add('down')
    def move_down(event):
        """Move selection down."""
        all_choices = get_current_choices()
        if state.selected_idx < len(all_choices) - 1:
            state.selected_idx += 1
            # Scroll down if needed
            if state.selected_idx >= state.scroll_offset + MAX_VISIBLE_CHOICES:
                state.scroll_offset = state.selected_idx - MAX_VISIBLE_CHOICES + 1

    @kb.add('1')
    def select_1(event):
        """Select visible choice 1."""
        visible_choices, _ = get_visible_choices()
        if len(visible_choices) >= 1:
            state.selected_idx = state.scroll_offset + 0

    @kb.add('2')
    def select_2(event):
        """Select visible choice 2."""
        visible_choices, _ = get_visible_choices()
        if len(visible_choices) >= 2:
            state.selected_idx = state.scroll_offset + 1

    @kb.add('3')
    def select_3(event):
        """Select visible choice 3."""
        visible_choices, _ = get_visible_choices()
        if len(visible_choices) >= 3:
            state.selected_idx = state.scroll_offset + 2

    @kb.add('4')
    def select_4(event):
        """Select visible choice 4."""
        visible_choices, _ = get_visible_choices()
        if len(visible_choices) >= 4:
            state.selected_idx = state.scroll_offset + 3

    @kb.add('5')
    def select_5(event):
        """Select visible choice 5."""
        visible_choices, _ = get_visible_choices()
        if len(visible_choices) >= 5:
            state.selected_idx = state.scroll_offset + 4

    @kb.add('enter')
    def accept(event):
        """Execute selected command."""
        all_choices = get_current_choices()
        if all_choices and 0 <= state.selected_idx < len(all_choices):
            state.selected_command = all_choices[state.selected_idx][0]
            event.app.exit()

    @kb.add('c-c')
    def exit_app(event):
        """Exit on Ctrl+C."""
        state.should_exit = True
        event.app.exit()

    @kb.add('c-d')
    def exit_app_eof(event):
        """Exit on Ctrl+D."""
        state.should_exit = True
        event.app.exit()

    # Function to generate choices display
    def get_choices_text():
        """Generate formatted text for choices."""
        visible_choices, total_count = get_visible_choices()
        lines = [("class:header", f"Available commands (showing {len(visible_choices)} of {total_count}):\n")]

        # Show scroll indicator at top if there are items above
        if state.scroll_offset > 0:
            lines.append(("class:scroll", "  ▲ More above...\n"))

        for i, (choice_name, choice_info) in enumerate(visible_choices):
            absolute_idx = state.scroll_offset + i
            description = choice_info['description']

            # Format: "1. command-name - Description here"
            if description:
                display_text = f"  {i+1}. {choice_name} - {description}\n"
            else:
                display_text = f"  {i+1}. {choice_name}\n"

            if absolute_idx == state.selected_idx:
                lines.append(("class:selected", f"  {i+1}. → {choice_name}"))
                if description:
                    lines.append(("class:selected_desc", f" - {description}\n"))
                else:
                    lines.append(("class:selected", "\n"))
            else:
                lines.append(("class:unselected", f"  {i+1}.   {choice_name}"))
                if description:
                    lines.append(("class:unselected_desc", f" - {description}\n"))
                else:
                    lines.append(("class:unselected", "\n"))

        # Show scroll indicator at bottom if there are items below
        if state.scroll_offset + len(visible_choices) < total_count:
            lines.append(("class:scroll", "  ▼ More below...\n"))

        return lines

    # Create layout
    header_text = [
        ("class:title", "n4 - your trusted helper\n"),
        ("class:info", f"Total commands: {len(all_command_names)}\n"),
        ("class:help", "Type to filter • ↑↓ or 1-5 to select • Enter to run • Ctrl+C to exit\n"),
        ("class:separator", "\n"),
    ]

    layout = Layout(
        HSplit([
            Window(
                FormattedTextControl(text=header_text),
                height=4,
            ),
            Window(
                FormattedTextControl(get_choices_text),
                height=8,
            ),
            Window(height=1, char="-"),
            Window(
                BufferControl(buffer=input_buffer),
                height=1,
            ),
        ])
    )

    # Define style
    style = Style.from_dict({
        'title': 'cyan bold',
        'info': 'green',
        'help': 'yellow',
        'separator': '',
        'header': 'white bold',
        'selected': 'cyan bold',
        'selected_desc': 'cyan',
        'unselected': 'gray',
        'unselected_desc': '#666666',
        'scroll': 'magenta',
    })

    # Create application
    app = Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=False,
        mouse_support=False,
    )

    # Main loop
    while True:
        # Reset state
        state.selected_idx = 0
        state.scroll_offset = 0
        state.selected_command = None
        state.should_exit = False
        input_buffer.text = ""

        # Run the application
        app.run()

        # Check if user wants to exit
        if state.should_exit:
            click.echo(click.style("\nGoodbye!", fg="cyan"))
            break

        # Execute selected command
        if state.selected_command:
            click.echo(click.style(f"\n\nRunning: {state.selected_command}", fg="green", bold=True))
            click.echo()

            # Check for special exit commands
            if state.selected_command.lower() in ("exit", "quit"):
                click.echo(click.style("Goodbye!", fg="cyan"))
                break

            try:
                cmd = commands[state.selected_command]['command']
                ctx.invoke(cmd)
            except click.exceptions.ClickException as e:
                e.show()
            except Exception as e:
                click.echo(click.style(f"Error executing command: {e}", fg="red"), err=True)

            click.echo()
            click.echo(click.style("Press Enter to continue...", fg="yellow"))
            input()
            click.clear()


def register_commands(cli_group):
    """Register all commands to the CLI group."""
    commands = load_commands()
    for command_name, command_info in commands.items():
        cli_group.add_command(command_info['command'], name=command_name)


# Register all commands
register_commands(cli)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
