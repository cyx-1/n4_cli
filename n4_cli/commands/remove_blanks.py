"""Remove blanks command - removes blank/empty lines from text."""

import sys

import click
import pyperclip


@click.command(name="remove-blanks")
@click.argument("file_path", required=False, type=click.Path(exists=True))
@click.option("--in-place", "-i", is_flag=True, help="Modify file in place (default when file is provided)")
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: stdout)")
@click.option("--clipboard", "-c", is_flag=True, help="Read from and write to clipboard")
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
    # Determine mode: file, stdin, or clipboard
    if file_path:
        # File mode
        try:
            with open(file_path, 'r') as f:
                content = f.readlines()

            # Remove blank lines
            non_blank_lines = [line for line in content if line.strip() != '']

            # Determine output destination
            if output:
                # Write to specified output file
                with open(output, 'w') as f:
                    for line_number, line in enumerate(non_blank_lines):
                        if line_number < len(non_blank_lines) - 1:
                            f.write(line)
                        else:
                            # Last line: remove trailing whitespace
                            f.write(line.rstrip())
                original_count = len(content)
                removed_count = original_count - len(non_blank_lines)
                click.echo(click.style(f"[OK] Removed {removed_count} blank lines from {original_count} total lines", fg="green"))
                click.echo(click.style(f"  Saved to: {output}", fg="green"))
            elif in_place or (not output and not in_place):
                # Default: in-place editing when file is provided
                with open(file_path, 'w') as f:
                    for line_number, line in enumerate(non_blank_lines):
                        if line_number < len(non_blank_lines) - 1:
                            f.write(line)
                        else:
                            # Last line: remove trailing whitespace
                            f.write(line.rstrip())
                original_count = len(content)
                removed_count = original_count - len(non_blank_lines)
                click.echo(click.style(f"[OK] Removed {removed_count} blank lines from {original_count} total lines", fg="green"))
                click.echo(click.style(f"  File: {file_path}", fg="green"))
            else:
                # Output to stdout
                for line_number, line in enumerate(non_blank_lines):
                    if line_number < len(non_blank_lines) - 1:
                        click.echo(line.rstrip('\n'))
                    else:
                        # Last line: remove trailing whitespace
                        click.echo(line.rstrip(), nl=False)

        except Exception as e:
            click.echo(click.style(f"Error processing file: {e}", fg="red"), err=True)
            raise click.Abort()

    elif not sys.stdin.isatty():
        # Pipe mode - read from stdin
        try:
            # Read from stdin
            content = sys.stdin.readlines()

            # Remove blank lines
            non_blank_lines = [line for line in content if line.strip() != '']

            # Output destination
            if output:
                with open(output, 'w') as f:
                    for line_number, line in enumerate(non_blank_lines):
                        if line_number < len(non_blank_lines) - 1:
                            f.write(line)
                        else:
                            # Last line: remove trailing whitespace
                            f.write(line.rstrip())
                original_count = len(content)
                removed_count = original_count - len(non_blank_lines)
                click.echo(click.style(f"[OK] Removed {removed_count} blank lines from {original_count} total lines", fg="green"), err=True)
                click.echo(click.style(f"  Saved to: {output}", fg="green"), err=True)
            else:
                # Write to stdout (for piping)
                for line_number, line in enumerate(non_blank_lines):
                    if line_number < len(non_blank_lines) - 1:
                        click.echo(line.rstrip('\n'))
                    else:
                        # Last line: remove trailing whitespace
                        click.echo(line.rstrip(), nl=False)

        except Exception as e:
            click.echo(click.style(f"Error processing stdin: {e}", fg="red"), err=True)
            raise click.Abort()

    else:
        # Clipboard mode
        try:
            clipboard_content = pyperclip.paste()

            if not clipboard_content:
                click.echo(click.style("Clipboard is empty", fg="yellow"))
                return

            lines = clipboard_content.split('\n')

            # Remove blank lines
            non_blank_lines = [line for line in lines if line.strip() != '']

            result = '\n'.join(non_blank_lines)

            if output:
                with open(output, 'w') as f:
                    f.write(result)
                original_count = len(lines)
                removed_count = original_count - len(non_blank_lines)
                click.echo(click.style(f"[OK] Removed {removed_count} blank lines from {original_count} total lines", fg="green"))
                click.echo(click.style(f"  Saved to: {output}", fg="green"))
            else:
                # Write back to clipboard and print to stdout
                pyperclip.copy(result)
                original_count = len(lines)
                removed_count = original_count - len(non_blank_lines)
                click.echo(click.style(f"[OK] Removed {removed_count} blank lines from {original_count} total lines", fg="green"), err=True)
                click.echo(click.style("Result copied to clipboard", fg="cyan"), err=True)
                click.echo(result)

        except Exception as e:
            click.echo(click.style(f"Error processing clipboard: {e}", fg="red"), err=True)
            raise click.Abort()
