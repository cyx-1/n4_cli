"""Autoagent command - Execute tasks from autoagent.md file sequentially."""

import asyncio
import re
import shutil
from pathlib import Path
from typing import List, Tuple

import click


def is_claude_available() -> bool:
    """Check if claude CLI is available."""
    return shutil.which("claude") is not None


def parse_autoagent_file(file_path: Path) -> List[Tuple[str, str]]:
    """Parse autoagent.md file to extract tasks.

    Expected format:
    ## Task: Description
    Prompt content here

    ## Task: Another description
    Another prompt here

    Returns:
        List of tuples (task_name, prompt)
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    content = file_path.read_text()
    tasks = []

    # Split by task headers (## Task: or # Task)
    # Match patterns like: ## Task: Name, ## Task Name, # Task: Name, # Task Name
    pattern = r'^#{1,2}\s+Task:?\s+(.+?)$'

    lines = content.split('\n')
    current_task_name = None
    current_prompt = []

    for line in lines:
        # Check if this is a task header
        match = re.match(pattern, line, re.IGNORECASE)
        if match:
            # Save previous task if exists
            if current_task_name and current_prompt:
                prompt_text = '\n'.join(current_prompt).strip()
                if prompt_text:
                    tasks.append((current_task_name, prompt_text))

            # Start new task
            current_task_name = match.group(1).strip()
            current_prompt = []
        else:
            # Add line to current prompt
            if current_task_name:
                current_prompt.append(line)

    # Add the last task
    if current_task_name and current_prompt:
        prompt_text = '\n'.join(current_prompt).strip()
        if prompt_text:
            tasks.append((current_task_name, prompt_text))

    return tasks


async def execute_claude_prompt(prompt: str, model: str = "sonnet") -> Tuple[bool, str]:
    """Execute a Claude prompt and return the result.

    Args:
        prompt: The prompt to send to Claude
        model: The model to use (sonnet, opus, haiku)

    Returns:
        Tuple of (success: bool, output: str)
    """
    try:
        # Escape double quotes in prompt
        escaped_prompt = prompt.replace('"', '\\"')

        cmd = f'claude --model {model} -p "{escaped_prompt}"'

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            output = stdout.decode().strip()
            return True, output
        else:
            error = stderr.decode().strip() if stderr else "Unknown error"
            return False, error

    except Exception as e:
        return False, str(e)


async def run_autoagent(file_path: Path, model: str, verbose: bool):
    """Run all tasks from autoagent file."""
    click.echo(click.style(f"\n🤖 AutoAgent Starting...", fg="cyan", bold=True))
    click.echo(click.style(f"📄 Reading tasks from: {file_path}", fg="blue"))

    try:
        tasks = parse_autoagent_file(file_path)
    except FileNotFoundError as e:
        click.echo(click.style(f"❌ Error: {e}", fg="red"))
        return
    except Exception as e:
        click.echo(click.style(f"❌ Error parsing file: {e}", fg="red"))
        return

    if not tasks:
        click.echo(click.style("⚠️  No tasks found in file", fg="yellow"))
        return

    click.echo(click.style(f"📋 Found {len(tasks)} task(s)\n", fg="green"))

    # Execute each task
    for i, (task_name, prompt) in enumerate(tasks, 1):
        click.echo(click.style(f"{'='*80}", fg="cyan"))
        click.echo(click.style(f"Task {i}/{len(tasks)}: {task_name}", fg="cyan", bold=True))
        click.echo(click.style(f"{'='*80}", fg="cyan"))

        if verbose:
            click.echo(click.style(f"\n📝 Prompt:", fg="blue"))
            click.echo(f"{prompt}\n")

        click.echo(click.style(f"⏳ Executing with Claude ({model})...", fg="yellow"))

        success, output = await execute_claude_prompt(prompt, model)

        if success:
            click.echo(click.style(f"\n✅ Task completed successfully!", fg="green", bold=True))
            click.echo(click.style(f"\n📤 Output:", fg="blue"))
            click.echo(output)
        else:
            click.echo(click.style(f"\n❌ Task failed!", fg="red", bold=True))
            click.echo(click.style(f"Error: {output}", fg="red"))

            # Ask user if they want to continue
            if i < len(tasks):
                if not click.confirm(click.style("\n⚠️  Continue with next task?", fg="yellow"), default=True):
                    click.echo(click.style("\n🛑 AutoAgent stopped by user", fg="red"))
                    return

        click.echo()  # Empty line for spacing

    click.echo(click.style(f"{'='*80}", fg="green"))
    click.echo(click.style(f"✨ AutoAgent completed all {len(tasks)} task(s)!", fg="green", bold=True))
    click.echo(click.style(f"{'='*80}", fg="green"))


@click.command(name="autoagent")
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=False, path_type=Path),
    default="autoagent.md",
    help="Path to autoagent markdown file (default: autoagent.md)"
)
@click.option(
    "--model",
    "-m",
    type=click.Choice(["sonnet", "opus", "haiku"], case_sensitive=False),
    default="sonnet",
    help="Claude model to use (default: sonnet)"
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show prompts before execution"
)
def autoagent(file, model, verbose):
    """Execute tasks from autoagent.md file sequentially using Claude.

    The autoagent.md file should contain tasks in the following format:

    \b
    ## Task: First task description
    Prompt content for the first task

    \b
    ## Task: Second task description
    Prompt content for the second task

    Each task will be executed one by one using Claude CLI with the -p flag.
    """
    if not is_claude_available():
        click.echo(click.style("❌ Error: Claude CLI not found in PATH", fg="red"))
        click.echo(click.style("Please install Claude CLI first", fg="yellow"))
        return

    # Run the async function
    asyncio.run(run_autoagent(file, model, verbose))
