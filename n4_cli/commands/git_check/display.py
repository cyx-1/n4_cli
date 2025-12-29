"""Display functions for repository status output."""

import asyncio
from typing import Dict, List

from rich.console import Console
from rich.table import Table

from .commit_message import generate_commit_message
from .models import RepoStatus


def display_status(statuses: List[RepoStatus], verbose: bool = False):
    """Display repository statuses using a rich table."""
    console = Console()

    repos_with_issues = [s for s in statuses if s.has_issues()]

    if not repos_with_issues and not verbose:
        console.print("\n✓ All repositories are clean and up to date!", style="bold green")
        return

    # Create table
    table = Table(title="\n📦 Repository Status", show_header=True, header_style="bold cyan")

    table.add_column("Repository", style="cyan", no_wrap=True)
    table.add_column("Branch", style="blue")
    table.add_column("Status", style="white")
    table.add_column("Changed", style="yellow", justify="right")
    table.add_column("Unpushed", style="yellow", justify="right")
    table.add_column("Unpulled", style="red", justify="right")
    table.add_column("Behind", style="yellow", justify="right")
    table.add_column("Merged Branches", style="magenta")
    table.add_column("Remote", style="dim", no_wrap=False)

    # Add rows
    for status in statuses:
        if not verbose and not status.has_issues():
            continue

        # Repository name
        repo_name = f"📁 {status.name}"

        # Branch
        branch = status.current_branch or "-"

        # Status indicator
        if status.errors:
            status_icon = "[red]✗ Error[/red]"
        elif status.has_issues():
            status_icon = "[yellow]⚠ Issues[/yellow]"
        else:
            status_icon = "[green]✓ Clean[/green]"

        # Changed files count
        changed_count = str(len(status.changed_files)) if status.changed_files else "-"

        # Unpushed commits
        unpushed = str(status.ahead_of_remote) if status.ahead_of_remote > 0 else "-"

        # Unpulled commits
        unpulled = str(len(status.unpulled_commits)) if status.unpulled_commits else "-"

        # Behind branches
        behind_text = ""
        if status.behind_branches:
            behind_list = [f"{branch}: {count}" for branch, count in status.behind_branches.items()]
            behind_text = "\n".join(behind_list)
        else:
            behind_text = "-"

        # Merged branches
        merged_text = ""
        if status.merged_branches:
            merged_text = "\n".join(status.merged_branches[:5])  # Limit to 5
            if len(status.merged_branches) > 5:
                merged_text += f"\n... +{len(status.merged_branches) - 5} more"
        else:
            merged_text = "-"

        # Remote URL (truncate if too long)
        remote = status.remote_url or "-"
        if len(remote) > 50:
            remote = remote[:47] + "..."

        # Add row
        table.add_row(
            repo_name,
            branch,
            status_icon,
            changed_count,
            unpushed,
            unpulled,
            behind_text,
            merged_text,
            remote
        )

    console.print("\n")
    console.print(table)
    console.print()


def display_unpulled_commits(statuses: List[RepoStatus]):
    """Display unpulled commits in a rich table."""
    console = Console()

    # Collect all statuses with unpulled commits
    repos_with_unpulled = [s for s in statuses if s.unpulled_commits]

    if not repos_with_unpulled:
        return

    console.print("\n")
    console.print("[bold yellow]⚠️  Warning: Some repositories have unpulled commits from remote![/bold yellow]")
    console.print("[yellow]You should pull these changes before pushing to avoid conflicts.[/yellow]\n")

    for status in repos_with_unpulled:
        # Create table for each repository
        table = Table(
            title=f"📥 {status.name} - Unpulled Commits ({len(status.unpulled_commits)} commit{'s' if len(status.unpulled_commits) != 1 else ''})",
            show_header=True,
            header_style="bold cyan"
        )

        table.add_column("Hash", style="dim", width=10)
        table.add_column("Author", style="cyan", no_wrap=True)
        table.add_column("Date", style="blue", width=20)
        table.add_column("Message", style="white")

        # Add rows
        for commit in status.unpulled_commits:
            # Format date to be more readable
            date_str = commit['date'][:19]  # Remove timezone info for cleaner display

            # Truncate message if too long
            message = commit['message']
            if len(message) > 80:
                message = message[:77] + "..."

            table.add_row(
                commit['hash'],
                commit['author'],
                date_str,
                message
            )

        console.print(table)
        console.print()


async def display_push_repos_with_messages(push_repos: List[RepoStatus]) -> Dict[RepoStatus, str]:
    """Display push repos with AI-generated commit messages and return the mapping.

    Returns a dict mapping RepoStatus to commit message.
    """
    console = Console()

    # Generate commit messages in parallel
    console.print("\n[cyan]Generating commit messages...[/cyan]")
    tasks = [generate_commit_message(status.path) for status in push_repos]
    commit_messages = await asyncio.gather(*tasks)

    # Create mapping
    repo_to_message = {status: msg for status, msg in zip(push_repos, commit_messages)}

    # Create table
    table = Table(title="\n1. PUSH - Commit and push changes", show_header=True, header_style="bold cyan")

    table.add_column("#", style="cyan", justify="right", width=4)
    table.add_column("Repository", style="cyan", no_wrap=True)
    table.add_column("Changes", style="yellow", justify="right", width=8)
    table.add_column("Suggested Commit Message", style="green")

    # Add rows
    for i, status in enumerate(push_repos, 1):
        table.add_row(
            str(i),
            status.name,
            str(len(status.changed_files)),
            repo_to_message[status]
        )

    console.print("\n")
    console.print(table)
    console.print()

    return repo_to_message
