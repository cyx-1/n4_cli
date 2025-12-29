"""Trim lines command - removes leading and trailing whitespace from each line."""

import click

from ..text_processor import text_processor_command, ProcessingResult


def _trim_lines_processor(lines):
    """Process lines by trimming whitespace."""
    # Strip each line and add newline back
    trimmed_lines = [line.strip() + '\n' for line in lines]

    return ProcessingResult(
        result=trimmed_lines,
        original_count=len(lines),
        processed_count=len(trimmed_lines)
    )


@click.command(name="trim-lines")
@click.argument("file_path", required=False, type=click.Path(exists=True))
@click.option("--in-place", "-i", is_flag=True, help="Modify file in place (default when file is provided)")
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: stdout)")
@click.option("--clipboard", "-c", is_flag=True, help="Read from and write to clipboard")
@text_processor_command(
    process_func=_trim_lines_processor,
    success_message_template="[OK] Trimmed {processed_count} lines"
)
def trim_lines(file_path, in_place, output, clipboard):
    """Remove leading and trailing whitespace from each line.

    Can be used in three modes:

    1. File mode (in-place editing):
       n4_cli trim-lines myfile.txt

    2. Pipe mode (stdin to stdout):
       cat myfile.txt | n4_cli trim-lines
       cat myfile.txt | n4_cli trim-lines > output.txt

    3. Clipboard mode:
       n4_cli trim-lines --clipboard
       n4_cli trim-lines -c

    Examples:
      n4_cli trim-lines data.txt              # Trim file in place
      cat data.txt | n4_cli trim-lines        # Trim and print to stdout
      n4_cli trim-lines -c                    # Trim clipboard content
      n4_cli trim-lines data.txt -o out.txt   # Trim to different file
    """
    pass
