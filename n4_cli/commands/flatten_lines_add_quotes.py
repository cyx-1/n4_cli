"""Flatten lines and add quotes - converts multi-line text to single line with quoted values."""

import click

from ..text_processor import text_processor_command, ProcessingResult


def _flatten_lines_processor(lines):
    """Process lines by flattening and adding quotes."""
    # Filter out empty lines and strip line endings
    non_empty_lines = [line.rstrip('\r\n') for line in lines if line.strip()]

    # Format with quotes and commas
    flattened = ''.join(f"'{line}'," for line in non_empty_lines)

    return ProcessingResult(
        result=flattened,
        original_count=len(lines),
        processed_count=len(non_empty_lines)
    )


@click.command(name="flatten-lines-add-quotes")
@click.argument("file_path", required=False, type=click.Path(exists=True))
@click.option("--in-place", "-i", is_flag=True, help="Modify file in place (default when file is provided)")
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: stdout)")
@click.option("--clipboard", "-c", is_flag=True, help="Read from and write to clipboard")
@text_processor_command(
    process_func=_flatten_lines_processor,
    success_message_template="[OK] Flattened {processed_count} lines",
    result_is_lines=False
)
def flatten_lines_add_quotes(file_path, in_place, output, clipboard):
    """Flatten multiple lines into single line with quoted, comma-separated values.

    Converts:
      line1
      line2
      line3

    To:
      'line1','line2','line3',

    Can be used in three modes:

    1. File mode (in-place editing):
       n4_cli flatten-lines-add-quotes myfile.txt

    2. Pipe mode (stdin to stdout):
       cat myfile.txt | n4_cli flatten-lines-add-quotes
       cat myfile.txt | n4_cli flatten-lines-add-quotes > output.txt

    3. Clipboard mode:
       n4_cli flatten-lines-add-quotes --clipboard
       n4_cli flatten-lines-add-quotes -c

    Examples:
      n4_cli flatten-lines-add-quotes data.txt              # Flatten file in place
      cat data.txt | n4_cli flatten-lines-add-quotes        # Flatten and print to stdout
      n4_cli flatten-lines-add-quotes -c                    # Flatten clipboard content
      n4_cli flatten-lines-add-quotes data.txt -o out.txt   # Flatten to different file
    """
    pass
