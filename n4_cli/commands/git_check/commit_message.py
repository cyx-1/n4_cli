"""AI-powered commit message generation using Claude CLI."""

import asyncio
import shutil
from pathlib import Path

import click
import yaml


def is_claude_available() -> bool:
    """Check if claude CLI is available."""
    return shutil.which("claude") is not None


async def generate_commit_message(repo_path: Path) -> str:
    """Generate a commit message using Claude CLI.

    Returns a suggested commit message or a default message if Claude is not available.
    """
    if not is_claude_available():
        return "Update changes"

    try:
        # Use the exact prompt that works well
        prompt = "suggest a commit msg no longer than 50 words in a single sentence based on the unpushed / unstaged changes in the current branch in yaml format having the key of commit_msg"

        # Debug: Print the command
        click.echo(click.style(f"\n[DEBUG] Repo: {repo_path.name}", fg="blue"))
        click.echo(click.style(f"[DEBUG] Command: claude --model haiku -p \"{prompt}\"", fg="blue"))

        proc = await asyncio.create_subprocess_shell(
            f'claude --model haiku -p "{prompt}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(repo_path)
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0 and stdout:
            output = stdout.decode().strip()

            # Debug: Print raw output
            click.echo(click.style("[DEBUG] Raw Claude output:", fg="blue"))
            click.echo(click.style("=" * 80, fg="blue"))
            click.echo(output)
            click.echo(click.style("=" * 80, fg="blue"))

            # Strip markdown code blocks FIRST (before parsing)
            if '```' in output:
                # Remove code block markers
                lines = output.split('\n')
                # Find start and end of code block
                yaml_content = []
                in_block = False
                for line in lines:
                    if line.strip().startswith('```'):
                        in_block = not in_block
                        continue
                    if in_block:
                        yaml_content.append(line)

                # If we found content in code blocks, use it
                if yaml_content:
                    output = '\n'.join(yaml_content).strip()
                    # Debug: Print cleaned output
                    click.echo(click.style("[DEBUG] After stripping code blocks:", fg="blue"))
                    click.echo(output)
                    click.echo(click.style("-" * 80, fg="blue"))

            # Try to parse YAML
            try:
                data = yaml.safe_load(output)

                # Debug: Print parsed data
                click.echo(click.style(f"[DEBUG] Parsed YAML data: {data}", fg="blue"))

                # Check for both 'commit_msg' and 'commit_message' keys
                if isinstance(data, dict):
                    msg = data.get('commit_msg') or data.get('commit_message')
                    if msg:
                        msg = str(msg).strip()
                        click.echo(click.style(f"[DEBUG] Extracted message: {msg}", fg="green"))
                        # Limit to 100 chars for table display
                        if len(msg) > 100:
                            msg = msg[:97] + "..."
                        return msg
                    else:
                        click.echo(click.style(f"[DEBUG] No commit_msg or commit_message key found in: {data}", fg="red"))
            except yaml.YAMLError as e:
                click.echo(click.style(f"[DEBUG] YAML parsing failed: {e}", fg="red"))
                # If YAML parsing fails, try to extract message from raw output
                # Look for lines that look like commit messages (not meta-text)
                lines = output.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith(('Based on', 'Here', 'commit_msg:', 'commit_message:', '**', '-', '#', '```')):
                        # Check if it's a YAML key-value pair
                        if ':' in line:
                            key = line.split(':')[0].strip()
                            if key in ['commit_msg', 'commit_message']:
                                # Extract value after colon
                                msg = ':'.join(line.split(':')[1:]).strip().strip('"').strip("'").strip()
                                click.echo(click.style(f"[DEBUG] Extracted from fallback (key-value): {msg}", fg="yellow"))
                                if len(msg) > 100:
                                    msg = msg[:97] + "..."
                                return msg
                        # Otherwise try direct extraction
                        msg = line.strip('"').strip("'").strip()
                        if len(msg) > 20:  # Only accept if it's substantial
                            click.echo(click.style(f"[DEBUG] Extracted from fallback (direct): {msg}", fg="yellow"))
                            if len(msg) > 100:
                                msg = msg[:97] + "..."
                            return msg

            click.echo(click.style("[DEBUG] No valid message found, returning default", fg="red"))
            return "Update changes"
        else:
            click.echo(click.style(f"[DEBUG] Claude CLI failed. Return code: {proc.returncode}", fg="red"))
            if stderr:
                click.echo(click.style(f"[DEBUG] Stderr: {stderr.decode()}", fg="red"))
            return "Update changes"
    except Exception as e:
        click.echo(click.style(f"[DEBUG] Exception: {e}", fg="red"))
        import traceback
        click.echo(click.style(f"[DEBUG] Traceback: {traceback.format_exc()}", fg="red"))
        return "Update changes"
