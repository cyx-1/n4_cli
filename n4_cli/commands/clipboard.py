"""Clipboard command - opens interactive web-based clipboard viewer."""

import html
import json
import tempfile
from pathlib import Path

import click
import pyperclip
import webbrowser


@click.command()
def clipboard():
    """Open interactive web-based clipboard format viewer.

    Opens a browser window showing all available clipboard formats including:
    - Text formats (plain, HTML, RTF)
    - Images and screenshots
    - Files with metadata
    - Multiple format inspection

    Based on Simon Willison's clipboard-viewer tool.
    """
    # Get the HTML file path
    assets_dir = Path(__file__).parent.parent / "assets"
    html_file = assets_dir / "clipboard-viewer.html"

    if not html_file.exists():
        click.echo(click.style("Error: clipboard-viewer.html not found in assets", fg="red"), err=True)
        raise click.Abort()

    # Read current clipboard content
    try:
        clipboard_content = pyperclip.paste()
    except Exception as e:
        click.echo(click.style(f"Warning: Could not read clipboard: {e}", fg="yellow"))
        clipboard_content = ""

    # Read the HTML template
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Inject JavaScript to auto-populate clipboard content
    # We'll add a script that simulates having clipboard content
    if clipboard_content:
        # Escape the clipboard content for JavaScript
        escaped_content = json.dumps(clipboard_content)

        injection_script = f"""
    <script>
        // Auto-populate clipboard content on page load
        window.addEventListener('DOMContentLoaded', function() {{
            const output = document.getElementById('output');
            const clipboardContent = {escaped_content};

            if (clipboardContent) {{
                // Clear the initial message
                output.innerHTML = '';

                // Create a format display
                const formatDiv = document.createElement('div');
                formatDiv.className = 'format';

                const formatTitle = document.createElement('h2');
                formatTitle.textContent = 'text/plain';
                formatDiv.appendChild(formatTitle);

                const formatContent = document.createElement('pre');
                formatContent.className = 'format-content';
                formatContent.textContent = clipboardContent;
                formatDiv.appendChild(formatContent);

                output.appendChild(formatDiv);

                // Add info section
                const eventInfo = document.createElement('div');
                eventInfo.className = 'format';
                eventInfo.innerHTML = `
                    <h2>Clipboard Information</h2>
                    <div class="format-content">
                        <pre>Content loaded automatically from system clipboard
Size: ${{clipboardContent.length}} characters
Lines: ${{clipboardContent.split('\\n').length}}
Type: text/plain

Note: To see all clipboard formats (HTML, images, etc.), paste content manually using Ctrl+V or Cmd+V</pre>
                    </div>
                `;
                output.appendChild(eventInfo);
            }}
        }});
    </script>
</body>
"""
        # Replace the closing </body> tag with our script + </body>
        html_content = html_content.replace('</body>', injection_script)

    # Create a temporary HTML file with the injected content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_file:
        temp_file.write(html_content)
        temp_html_path = temp_file.name

    # Open in default browser
    try:
        click.echo(click.style("Opening clipboard viewer in browser...", fg="cyan"))

        if clipboard_content:
            preview = clipboard_content[:100]
            if len(clipboard_content) > 100:
                preview += "..."
            click.echo(click.style(f"Clipboard content ({len(clipboard_content)} chars): {preview}", fg="green"))
        else:
            click.echo(click.style("Clipboard is empty", fg="yellow"))

        webbrowser.open(f"file://{temp_html_path}")
        click.echo(click.style(f"✓ Viewer opened in browser", fg="green"))
        click.echo(click.style("\nYou can paste (Ctrl+V / Cmd+V) to see additional clipboard formats.", fg="yellow"))
    except Exception as e:
        click.echo(click.style(f"Error opening browser: {e}", fg="red"), err=True)
        # Clean up temp file on error
        Path(temp_html_path).unlink(missing_ok=True)
        raise click.Abort()
