"""Interactive repository selection functions."""

from pathlib import Path
from typing import List

import click
import questionary

from .models import RepoStatus


def select_repos_interactive(repos: List[Path], prompt: str = "Select repositories") -> List[Path]:
    """Interactive repository selection with number-based input.

    Allows users to:
    - Press Enter for all repos (default)
    - Enter numbers: 1,3,5 or 1-3
    - Type 'all' for all repos
    """
    if len(repos) <= 1:
        return repos

    # Display numbered list
    click.echo(click.style(f"\n{prompt}:", fg="cyan", bold=True))
    for i, repo in enumerate(repos, 1):
        click.echo(f"  {i}. {repo.name} ({repo})")

    click.echo(click.style("\nEnter selection:", fg="yellow"))
    click.echo("  • Press Enter for all (default)")
    click.echo("  • Enter numbers: 1,3,5")
    click.echo("  • Enter ranges: 1-3")
    click.echo("  • Type 'all' for all repositories")

    selection = questionary.text(
        "",
        default="all"
    ).ask()

    if not selection or selection.strip().lower() == "all":
        return repos

    # Parse selection
    selected_indices = set()
    parts = selection.split(',')

    try:
        for part in parts:
            part = part.strip()
            if '-' in part:
                # Range like "1-3"
                start, end = part.split('-')
                start_idx = int(start.strip())
                end_idx = int(end.strip())
                for idx in range(start_idx, end_idx + 1):
                    if 1 <= idx <= len(repos):
                        selected_indices.add(idx - 1)
            else:
                # Single number
                idx = int(part)
                if 1 <= idx <= len(repos):
                    selected_indices.add(idx - 1)
    except ValueError:
        click.echo(click.style("Invalid input. Selecting all repositories.", fg="yellow"))
        return repos

    if not selected_indices:
        click.echo(click.style("No valid selection. Selecting all repositories.", fg="yellow"))
        return repos

    selected_repos = [repos[i] for i in sorted(selected_indices)]
    click.echo(click.style(f"\n✓ Selected {len(selected_repos)} repository/repositories\n", fg="green"))

    return selected_repos


def select_repo_statuses_interactive(statuses: List[RepoStatus], prompt: str = "Select repositories") -> List[RepoStatus]:
    """Interactive RepoStatus selection with number-based input."""
    if len(statuses) <= 1:
        return statuses

    # Display numbered list
    click.echo(click.style(f"\n{prompt}:", fg="cyan", bold=True))
    for i, status in enumerate(statuses, 1):
        click.echo(f"  {i}. {status.name}")

    click.echo(click.style("\nEnter selection:", fg="yellow"))
    click.echo("  • Press Enter for all (default)")
    click.echo("  • Enter numbers: 1,3,5")
    click.echo("  • Enter ranges: 1-3")
    click.echo("  • Type 'all' for all repositories")
    click.echo("  • Type 'none' or '0' to skip")

    selection = questionary.text(
        "",
        default="all"
    ).ask()

    if not selection or selection.strip().lower() in ["none", "0"]:
        return []

    if selection.strip().lower() == "all":
        return statuses

    # Parse selection
    selected_indices = set()
    parts = selection.split(',')

    try:
        for part in parts:
            part = part.strip()
            if '-' in part:
                # Range like "1-3"
                start, end = part.split('-')
                start_idx = int(start.strip())
                end_idx = int(end.strip())
                for idx in range(start_idx, end_idx + 1):
                    if 1 <= idx <= len(statuses):
                        selected_indices.add(idx - 1)
            else:
                # Single number
                idx = int(part)
                if 1 <= idx <= len(statuses):
                    selected_indices.add(idx - 1)
    except ValueError:
        click.echo(click.style("Invalid input. Selecting all repositories.", fg="yellow"))
        return statuses

    if not selected_indices:
        return []

    selected_statuses = [statuses[i] for i in sorted(selected_indices)]
    click.echo(click.style(f"\n✓ Selected {len(selected_statuses)} repository/repositories\n", fg="green"))

    return selected_statuses
