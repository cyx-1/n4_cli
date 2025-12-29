"""Remove blanks command - removes blank/empty lines from text."""

import click

from ..text_processor import text_processor_command, ProcessingResult


def _remove_blanks_processor(lines):
    """Process lines by removing blanks."""
    # Remove blank lines (preserving newlines in non-blank lines)
    non_blank_lines = [line for line in lines if line.strip() != '']

    return ProcessingResult(
        result=non_blank_lines,
        original_count=len(lines),
        processed_count=len(non_blank_lines),
        metadata={'removed_count': len(lines) - len(non_blank_lines)}
    )


@click.command(name="remove-blanks")
@click.argument("file_path", required=False, type=click.Path(exists=True))
@click.option("--in-place", "-i", is_flag=True, help="Modify file in place (default when file is provided)")
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: stdout)")
@click.option("--clipboard", "-c", is_flag=True, help="Read from and write to clipboard")
@text_processor_command(
    process_func=_remove_blanks_processor,
    success_message_template="[OK] Removed {removed_count} blank lines from {original_count} total lines"
)
def remove_blanks(file_path, in_place, output, clipboard):
    """Remove blank/empty lines from text.

    Removes lines that are empty or contain only whitespace.

    Can be used in three modes:

    1. File mode (in-place editing):
       n4_cli remove-blanks myfile.txt

    2. Pipe mode (stdin to stdout):
       cat myfile.txt | n4_cli remove-blanks
       cat myfile.txt | n4_cli remove-blanks > output.txt

    3. Clipboard mode:
       n4_cli remove-blanks --clipboard
       n4_cli remove-blanks -c

    Examples:
      n4_cli remove-blanks data.txt              # Remove blanks in place
      cat data.txt | n4_cli remove-blanks        # Remove blanks to stdout
      n4_cli remove-blanks -c                    # Remove blanks from clipboard
      n4_cli remove-blanks data.txt -o out.txt   # Remove blanks to different file
    """
    pass
