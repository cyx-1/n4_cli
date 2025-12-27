"""Clipboard command - opens interactive web-based clipboard viewer."""

import json
import re
import tempfile
from pathlib import Path

import click
import pyperclip
import webbrowser


def detect_content_formats(content):
    """Detect what formats the clipboard content might be in."""
    formats = {}

    if not content:
        return formats

    # Always include text/plain
    formats['text/plain'] = content

    # Detect HTML
    html_patterns = [
        r'^\s*<!DOCTYPE\s+html',
        r'^\s*<html',
        r'<\/html>\s*$',
        r'<(div|span|p|table|body|head)\s',
    ]

    is_html = any(re.search(pattern, content, re.IGNORECASE | re.MULTILINE) for pattern in html_patterns)

    if is_html:
        formats['text/html'] = content

    # Detect JSON
    try:
        json.loads(content.strip())
        formats['application/json'] = content
    except (json.JSONDecodeError, ValueError):
        pass

    # Detect XML
    if content.strip().startswith('<?xml') or (content.strip().startswith('<') and not is_html):
        formats['application/xml'] = content

    # Detect URLs
    url_pattern = r'^https?://[^\s]+$'
    if re.match(url_pattern, content.strip()):
        formats['text/uri-list'] = content

    # Detect Markdown (simple heuristic)
    markdown_patterns = [
        r'^#+\s',  # Headers
        r'\[.*?\]\(.*?\)',  # Links
        r'^\*\*.*?\*\*',  # Bold
        r'^```',  # Code blocks
    ]
    if any(re.search(pattern, content, re.MULTILINE) for pattern in markdown_patterns):
        formats['text/markdown'] = content

    return formats


@click.command()
def clipboard():
    """Open interactive web-based clipboard format viewer.

    Opens a browser window showing all available clipboard formats including:
    - Text formats (plain, HTML, RTF)
    - Images and screenshots
    - Files with metadata
    - Multiple format inspection

    Automatically detects and displays rich formats like HTML, JSON, XML, and Markdown.
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

    # Detect all formats
    detected_formats = detect_content_formats(clipboard_content)

    # Inject JavaScript to auto-populate clipboard content
    if detected_formats:
        # Escape the formats data for JavaScript
        formats_json = json.dumps(detected_formats)

        injection_script = f"""
    <script>
        // Auto-populate clipboard content on page load
        window.addEventListener('DOMContentLoaded', function() {{
            const output = document.getElementById('output');
            const detectedFormats = {formats_json};

            if (Object.keys(detectedFormats).length > 0) {{
                // Clear the initial message
                output.innerHTML = '';

                // Display each detected format
                for (const [formatType, formatContent] of Object.entries(detectedFormats)) {{
                    const formatDiv = document.createElement('div');
                    formatDiv.className = 'format';

                    const formatTitle = document.createElement('h2');
                    formatTitle.textContent = formatType;
                    formatDiv.appendChild(formatTitle);

                    const formatContentWrapper = document.createElement('div');
                    formatContentWrapper.className = 'format-content';

                    // Special handling for HTML
                    if (formatType === 'text/html') {{
                        const htmlPreview = document.createElement('div');
                        htmlPreview.innerHTML = '<strong>HTML Source:</strong>';
                        formatContentWrapper.appendChild(htmlPreview);

                        const htmlPre = document.createElement('pre');
                        htmlPre.textContent = formatContent;
                        formatContentWrapper.appendChild(htmlPre);

                        // Add rendered preview
                        const renderedTitle = document.createElement('div');
                        renderedTitle.innerHTML = '<strong style="margin-top: 15px; display: block;">Rendered Preview:</strong>';
                        formatContentWrapper.appendChild(renderedTitle);

                        const renderedDiv = document.createElement('div');
                        renderedDiv.style.border = '1px solid #ccc';
                        renderedDiv.style.padding = '10px';
                        renderedDiv.style.marginTop = '5px';
                        renderedDiv.style.backgroundColor = '#fff';
                        renderedDiv.innerHTML = formatContent;
                        formatContentWrapper.appendChild(renderedDiv);
                    }} else {{
                        const formatPre = document.createElement('pre');
                        formatPre.textContent = formatContent;
                        formatContentWrapper.appendChild(formatPre);
                    }}

                    formatDiv.appendChild(formatContentWrapper);
                    output.appendChild(formatDiv);
                }}

                // Add info section
                const eventInfo = document.createElement('div');
                eventInfo.className = 'format';

                const formatsList = Object.keys(detectedFormats).join(', ');
                const contentLength = detectedFormats['text/plain'] ? detectedFormats['text/plain'].length : 0;
                const lineCount = detectedFormats['text/plain'] ? detectedFormats['text/plain'].split('\\n').length : 0;

                eventInfo.innerHTML = `
                    <h2>Clipboard Information</h2>
                    <div class="format-content">
                        <pre>Content loaded automatically from system clipboard
Size: ${{contentLength}} characters
Lines: ${{lineCount}}
Detected formats: ${{formatsList}}

Note: Paste manually (Ctrl+V / Cmd+V) to see additional system-level formats like images and files.</pre>
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
            preview = clipboard_content[:100].replace('\n', ' ')
            if len(clipboard_content) > 100:
                preview += "..."

            format_types = list(detected_formats.keys())
            click.echo(click.style(f"Detected formats: {', '.join(format_types)}", fg="green"))
            click.echo(click.style(f"Content preview: {preview}", fg="green"))
        else:
            click.echo(click.style("Clipboard is empty", fg="yellow"))

        webbrowser.open(f"file://{temp_html_path}")
        click.echo(click.style(f"✓ Viewer opened in browser", fg="green"))
        click.echo(click.style("\nYou can paste (Ctrl+V / Cmd+V) to see system-level formats like images.", fg="yellow"))
    except Exception as e:
        click.echo(click.style(f"Error opening browser: {e}", fg="red"), err=True)
        # Clean up temp file on error
        Path(temp_html_path).unlink(missing_ok=True)
        raise click.Abort()
