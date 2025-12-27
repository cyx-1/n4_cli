"""Flatten lines and add quotes - converts multi-line text to single line with quoted values."""

import sys

import click
import pyperclip


@click.command(name="flatten-lines-add-quotes")
@click.argument("file_path", required=False, type=click.Path(exists=True))
@click.option("--in-place", "-i", is_flag=True, help="Modify file in place (default when file is provided)")
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: stdout)")
@click.option("--clipboard", "-c", is_flag=True, help="Read from and write to clipboard")
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
    # Determine mode: file, stdin, or clipboard
    if file_path:
        # File mode
        try:
            with open(file_path, 'r') as f:
                content = f.readlines()

            # Filter out empty lines and strip whitespace
            lines = [line.strip() for line in content if line.strip()]

            # Process lines: format with quotes
            flattened = ''.join(f"'{line}'," for line in lines)

            # Determine output destination
            if output:
                # Write to specified output file
                with open(output, 'w') as f:
                    f.write(flattened)
                click.echo(click.style(f"[OK] Flattened {len(lines)} lines to: {output}", fg="green"))
            elif in_place or (not output and not in_place):
                # Default: in-place editing when file is provided
                with open(file_path, 'w') as f:
                    f.write(flattened)
                click.echo(click.style(f"[OK] Flattened {len(lines)} lines in: {file_path}", fg="green"))
            else:
                # Output to stdout
                click.echo(flattened)

        except Exception as e:
            click.echo(click.style(f"Error processing file: {e}", fg="red"), err=True)
            raise click.Abort()

    elif not sys.stdin.isatty():
        # Pipe mode - read from stdin
        try:
            # Read from stdin
            content = sys.stdin.readlines()

            # Filter out empty lines and strip whitespace
            lines = [line.strip() for line in content if line.strip()]

            # Process lines: format with quotes
            flattened = ''.join(f"'{line}'," for line in lines)

            # Output destination
            if output:
                with open(output, 'w') as f:
                    f.write(flattened)
                click.echo(click.style(f"[OK] Flattened {len(lines)} lines to: {output}", fg="green"), err=True)
            else:
                # Write to stdout (for piping)
                click.echo(flattened)

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

            # Filter out empty lines and strip whitespace (including \r)
            lines = [line.strip() for line in lines if line.strip()]

            # Process lines: format with quotes
            flattened = ''.join(f"'{line}'," for line in lines)

            if output:
                with open(output, 'w') as f:
                    f.write(flattened)
                click.echo(click.style(f"[OK] Flattened {len(lines)} lines from clipboard to: {output}", fg="green"))
            else:
                # Write back to clipboard and print to stdout
                pyperclip.copy(flattened)
                click.echo(click.style(f"[OK] Flattened {len(lines)} lines", fg="green"), err=True)
                click.echo(click.style("Result copied to clipboard", fg="cyan"), err=True)
                click.echo(flattened)

        except Exception as e:
            click.echo(click.style(f"Error processing clipboard: {e}", fg="red"), err=True)
            raise click.Abort()
