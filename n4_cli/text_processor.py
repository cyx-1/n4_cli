"""Shared text processing utilities for handling file/stdin/clipboard input and output."""

import sys
from typing import Callable, List, Union, Tuple, Optional

import click
import pyperclip


class ProcessingResult:
    """Container for processing results and metadata."""

    def __init__(
        self,
        result: Union[List[str], str],
        original_count: int = 0,
        processed_count: int = 0,
        metadata: Optional[dict] = None
    ):
        self.result = result
        self.original_count = original_count
        self.processed_count = processed_count
        self.metadata = metadata or {}


def text_processor_command(
    process_func: Callable[[List[str]], Union[ProcessingResult, List[str], str]],
    success_message_template: str = "[OK] Processed {processed_count} lines",
    result_is_lines: bool = True
):
    """
    Decorator factory to create text processing Click commands with consistent I/O handling.

    This eliminates ~400 lines of duplicated code across commands by providing
    a unified interface for handling file/stdin/clipboard input and output.

    Args:
        process_func: Function that processes lines. Should take List[str] and return:
                     - ProcessingResult (with metadata for custom messages)
                     - List[str] (processed lines)
                     - str (final output string)
        success_message_template: Template for success messages. Can use:
                                 {original_count}, {processed_count}, {destination}
        result_is_lines: If True, result is treated as lines (join with newlines).
                        If False, result is treated as a final string.

    Returns:
        A decorator that wraps the actual Click command function.

    Example:
        @text_processor_command(
            process_func=lambda lines: [line for line in lines if line.strip()],
            success_message_template="Removed {removed_count} blank lines"
        )
        def remove_blanks_impl(lines: List[str]) -> ProcessingResult:
            filtered = [line for line in lines if line.strip()]
            return ProcessingResult(
                result=filtered,
                original_count=len(lines),
                processed_count=len(filtered),
                metadata={'removed_count': len(lines) - len(filtered)}
            )
    """
    def decorator(func):
        def wrapper(file_path, in_place, output, clipboard):
            # Determine input source and read content
            try:
                if file_path:
                    # File mode
                    with open(file_path, 'r') as f:
                        lines = f.readlines()
                    source_mode = 'file'
                    source_name = file_path
                elif not sys.stdin.isatty():
                    # Pipe mode
                    lines = sys.stdin.readlines()
                    source_mode = 'stdin'
                    source_name = 'stdin'
                else:
                    # Clipboard mode
                    clipboard_content = pyperclip.paste()
                    if not clipboard_content:
                        click.echo(click.style("Clipboard is empty", fg="yellow"))
                        return
                    lines = clipboard_content.split('\n')
                    # Add newlines back for consistency with file/stdin
                    lines = [line + '\n' if i < len(lines) - 1 else line
                            for i, line in enumerate(lines)]
                    source_mode = 'clipboard'
                    source_name = 'clipboard'

                # Process the lines
                result = process_func(lines)

                # Handle different result types
                if isinstance(result, ProcessingResult):
                    processed_result = result.result
                    original_count = result.original_count
                    processed_count = result.processed_count
                    metadata = result.metadata
                elif isinstance(result, (list, str)):
                    processed_result = result
                    original_count = len(lines)
                    processed_count = len(result) if isinstance(result, list) else 1
                    metadata = {}
                else:
                    raise ValueError(f"Unexpected result type: {type(result)}")

                # Convert result to string for output
                if isinstance(processed_result, list):
                    if result_is_lines:
                        # Join lines, preserving newlines
                        output_str = ''.join(processed_result)
                        # Remove trailing newline for final output
                        if output_str.endswith('\n'):
                            output_str = output_str[:-1]
                    else:
                        # Join without newlines
                        output_str = ''.join(processed_result)
                else:
                    output_str = processed_result

                # Determine output destination and write
                if output:
                    # Write to output file
                    with open(output, 'w') as f:
                        f.write(output_str)
                    message_data = {
                        'original_count': original_count,
                        'processed_count': processed_count,
                        'destination': output,
                        **metadata
                    }
                    msg = success_message_template.format(**message_data)
                    # Use stderr for pipe mode to keep stdout clean
                    use_err = source_mode == 'stdin'
                    click.echo(click.style(msg, fg="green"), err=use_err)
                    if 'destination' not in success_message_template:
                        click.echo(click.style(f"  Saved to: {output}", fg="green"), err=use_err)

                elif in_place and source_mode == 'file':
                    # In-place editing
                    with open(file_path, 'w') as f:
                        f.write(output_str)
                    message_data = {
                        'original_count': original_count,
                        'processed_count': processed_count,
                        'destination': file_path,
                        **metadata
                    }
                    msg = success_message_template.format(**message_data)
                    click.echo(click.style(msg, fg="green"))
                    if 'destination' not in success_message_template:
                        click.echo(click.style(f"  File: {file_path}", fg="green"))

                elif source_mode == 'file' and not output and not in_place:
                    # File mode with default in-place behavior
                    with open(file_path, 'w') as f:
                        f.write(output_str)
                    message_data = {
                        'original_count': original_count,
                        'processed_count': processed_count,
                        'destination': file_path,
                        **metadata
                    }
                    msg = success_message_template.format(**message_data)
                    click.echo(click.style(msg, fg="green"))
                    if 'destination' not in success_message_template:
                        click.echo(click.style(f"  File: {file_path}", fg="green"))

                elif source_mode == 'stdin':
                    # Pipe mode - write to stdout
                    click.echo(output_str, nl=False)

                else:
                    # Clipboard mode - copy to clipboard and show result
                    pyperclip.copy(output_str)
                    message_data = {
                        'original_count': original_count,
                        'processed_count': processed_count,
                        **metadata
                    }
                    msg = success_message_template.format(**message_data)
                    click.echo(click.style(msg, fg="green"), err=True)
                    click.echo(click.style("Result copied to clipboard", fg="cyan"), err=True)
                    click.echo(output_str)

            except Exception as e:
                error_source = source_name if 'source_name' in locals() else 'input'
                click.echo(click.style(f"Error processing {error_source}: {e}", fg="red"), err=True)
                raise click.Abort()

        return wrapper

    return decorator
