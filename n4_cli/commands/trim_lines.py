"""Trim lines command - removes leading and trailing whitespace from each line."""

import sys

import click
import pyperclip


@click.command(name="trim-lines")
@click.argument("file_path", required=False, type=click.Path(exists=True))
@click.option("--in-place", "-i", is_flag=True, help="Modify file in place (default when file is provided)")
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: stdout)")
@click.option("--clipboard", "-c", is_flag=True, help="Read from and write to clipboard")
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
    # Determine mode: file, stdin, or clipboard
    if file_path:
        # File mode
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()

            # Trim each line
            trimmed_lines = [line.strip() for line in lines]

            # Determine output destination
            if output:
                # Write to specified output file
                with open(output, 'w') as f:
                    for line in trimmed_lines:
                        f.write(f'{line}\n')
                click.echo(click.style(f"[OK] Trimmed {len(trimmed_lines)} lines to: {output}", fg="green"))
            elif in_place or (not output and not in_place):
                # Default: in-place editing when file is provided
                with open(file_path, 'w') as f:
                    for line in trimmed_lines:
                        f.write(f'{line}\n')
                click.echo(click.style(f"[OK] Trimmed {len(trimmed_lines)} lines in: {file_path}", fg="green"))
            else:
                # Output to stdout
                for line in trimmed_lines:
                    click.echo(line)

        except Exception as e:
            click.echo(click.style(f"Error processing file: {e}", fg="red"), err=True)
            raise click.Abort()

    elif not sys.stdin.isatty():
        # Pipe mode - read from stdin
        try:
            # Read from stdin
            lines = sys.stdin.readlines()

            # Trim each line
            trimmed_lines = [line.strip() for line in lines]

            # Output destination
            if output:
                with open(output, 'w') as f:
                    for line in trimmed_lines:
                        f.write(f'{line}\n')
                click.echo(click.style(f"[OK] Trimmed {len(trimmed_lines)} lines to: {output}", fg="green"), err=True)
            else:
                # Write to stdout (for piping)
                for line in trimmed_lines:
                    click.echo(line)

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

            # Trim each line
            trimmed_lines = [line.strip() for line in lines]

            result = '\n'.join(trimmed_lines)

            if output:
                with open(output, 'w') as f:
                    f.write(result)
                click.echo(click.style(f"[OK] Trimmed {len(trimmed_lines)} lines from clipboard to: {output}", fg="green"))
            else:
                # Write back to clipboard
                pyperclip.copy(result)
                click.echo(click.style(f"[OK] Trimmed {len(trimmed_lines)} lines", fg="green"))
                click.echo(click.style("Result copied to clipboard", fg="cyan"))

        except Exception as e:
            click.echo(click.style(f"Error processing clipboard: {e}", fg="red"), err=True)
            raise click.Abort()
