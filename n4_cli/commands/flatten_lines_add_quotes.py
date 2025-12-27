"""Flatten lines and add quotes - converts multi-line text to single line with quoted values."""

import sys

import click


@click.command(name="flatten-lines-add-quotes")
@click.argument("file_path", required=False, type=click.Path(exists=True))
@click.option("--in-place", "-i", is_flag=True, help="Modify file in place (default when file is provided)")
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: stdout)")
def flatten_lines_add_quotes(file_path, in_place, output):
    """Flatten multiple lines into single line with quoted, comma-separated values.

    Converts:
      line1
      line2
      line3

    To:
      'line1','line2','line3',

    Can be used in two modes:

    1. File mode (in-place editing):
       n4_cli flatten-lines-add-quotes myfile.txt

    2. Pipe mode (stdin to stdout):
       cat myfile.txt | n4_cli flatten-lines-add-quotes
       cat myfile.txt | n4_cli flatten-lines-add-quotes > output.txt

    Examples:
      n4_cli flatten-lines-add-quotes data.txt              # Flatten file in place
      cat data.txt | n4_cli flatten-lines-add-quotes        # Flatten and print to stdout
      n4_cli flatten-lines-add-quotes data.txt -o out.txt   # Flatten to different file
    """
    # Determine mode: file or stdin
    if file_path:
        # File mode
        try:
            with open(file_path, 'r') as f:
                content = f.readlines()

            # Process lines: remove newlines and format with quotes
            flattened = ''.join(f"'{line.rstrip()}',".replace('\n', '') for line in content)

            # Determine output destination
            if output:
                # Write to specified output file
                with open(output, 'w') as f:
                    f.write(flattened)
                click.echo(click.style(f"✓ Flattened {len(content)} lines to: {output}", fg="green"))
            elif in_place or (not output and not in_place):
                # Default: in-place editing when file is provided
                with open(file_path, 'w') as f:
                    f.write(flattened)
                click.echo(click.style(f"✓ Flattened {len(content)} lines in: {file_path}", fg="green"))
            else:
                # Output to stdout
                click.echo(flattened)

        except Exception as e:
            click.echo(click.style(f"Error processing file: {e}", fg="red"), err=True)
            raise click.Abort()

    else:
        # Pipe mode - read from stdin
        if sys.stdin.isatty():
            click.echo(click.style("Error: No input provided. Provide a file path or pipe input.", fg="red"), err=True)
            click.echo("\nUsage:")
            click.echo("  n4_cli flatten-lines-add-quotes <file>           # Flatten file in place")
            click.echo("  cat file.txt | n4_cli flatten-lines-add-quotes   # Flatten from stdin")
            raise click.Abort()

        try:
            # Read from stdin
            content = sys.stdin.readlines()

            # Process lines: remove newlines and format with quotes
            flattened = ''.join(f"'{line.rstrip()}',".replace('\n', '') for line in content)

            # Output destination
            if output:
                with open(output, 'w') as f:
                    f.write(flattened)
                click.echo(click.style(f"✓ Flattened {len(content)} lines to: {output}", fg="green"), err=True)
            else:
                # Write to stdout (for piping)
                click.echo(flattened)

        except Exception as e:
            click.echo(click.style(f"Error processing stdin: {e}", fg="red"), err=True)
            raise click.Abort()
