"""CLI command for git-check functionality."""

import asyncio
from pathlib import Path

import click

from n4_cli.git_service import default_git_service

from .actions import execute_action_prune, execute_action_pull, execute_action_push
from .checker import check_all_repos, find_git_repos
from .display import (
    display_push_repos_with_messages,
    display_status,
    display_unpulled_commits,
)
from .interactive import select_repo_statuses_interactive, select_repos_interactive


@click.command(name="git-check")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path.cwd(),
    help="Base path to search for repositories (default: current directory)"
)
@click.option(
    "--recursive",
    "-r",
    is_flag=True,
    default=True,
    help="Recursively search for git repositories (default: True, use --no-recursive to disable)"
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show all repositories, including clean ones"
)
@click.option(
    "--action",
    "-a",
    is_flag=True,
    help="Interactive mode to select and execute actions (push/pull/prune)"
)
def git_check(path: Path, recursive: bool, verbose: bool, action: bool):
    """Check and manage multiple git repositories in parallel.

    This command analyzes all git repositories in the specified path and reports:
    - Changed files (uncommitted/unstaged)
    - Unpushed commits (commits ahead of remote)
    - Branches behind their remote tracking branch
    - Branches that have been merged to main/master

    By default, searches recursively for all git repositories in subdirectories.
    Use --action for interactive mode to select and execute batch operations.

    Examples:
      n4_cli git-check                    # Check current directory recursively
      n4_cli git-check -p ~/projects      # Check ~/projects recursively
      n4_cli git-check --no-recursive     # Check only current directory (no subdirs)
      n4_cli git-check -v                 # Show all repos including clean ones
      n4_cli git-check --action           # Interactive mode to execute actions
    """
    # Find all git repositories
    click.echo(click.style("🔍 Scanning for git repositories...", fg="cyan"))
    repos = find_git_repos(path, recursive)

    if not repos:
        click.echo(click.style("No git repositories found.", fg="yellow"))
        return

    click.echo(click.style(f"Found {len(repos)} repository/repositories", fg="cyan"))

    # Interactive repository selection
    repos = select_repos_interactive(repos, "Select repositories to check")

    # Check status of all repos in parallel
    statuses = asyncio.run(check_all_repos(repos))

    # Display status
    display_status(statuses, verbose)

    # Display unpulled commits warning
    display_unpulled_commits(statuses)

    # Execute action if specified
    if action:
        click.echo(click.style("\n=== Interactive Action Mode ===\n", fg="yellow", bold=True))

        # Determine available actions
        push_repos = [s for s in statuses if s.has_uncommitted and not s.errors]
        pull_repos = [s for s in statuses if s.behind_branches and not s.errors]
        prune_repos = [s for s in statuses if s.merged_branches and not s.errors]

        if not any([push_repos, pull_repos, prune_repos]):
            click.echo(click.style("✓ All repositories are clean. No actions needed.", fg="green"))
            return

        # Show available actions
        click.echo("Available actions:\n")

        actions_to_execute = []

        # Option 1: Push changes
        repo_to_message = {}
        if push_repos:
            # Display repos with AI-generated commit messages
            repo_to_message = asyncio.run(display_push_repos_with_messages(push_repos))

            # Directly go to repo selection
            selected_push = select_repo_statuses_interactive(push_repos, "Select repositories for PUSH")
            if selected_push:
                # Filter repo_to_message for selected repos only
                selected_repo_to_message = {k: v for k, v in repo_to_message.items() if k in selected_push}
                actions_to_execute.append(("push", selected_push, selected_repo_to_message))
            click.echo()

        # Option 2: Pull branches
        if pull_repos:
            click.echo(click.style("2. PULL - Update branches behind remote", fg="cyan", bold=True))
            for i, status in enumerate(pull_repos, 1):
                click.echo(f"   {i}. {status.name}")
                for branch, count in status.behind_branches.items():
                    click.echo(f"      - {branch}: {count} commit(s) behind")

            if click.confirm(click.style("\n   Execute pull action?", fg="yellow")):
                selected_pull = select_repo_statuses_interactive(pull_repos, "Select repositories for PULL")
                if selected_pull:
                    actions_to_execute.append(("pull", selected_pull))
            click.echo()

        # Option 3: Prune merged branches
        if prune_repos:
            click.echo(click.style("3. PRUNE - Delete merged branches", fg="cyan", bold=True))
            for i, status in enumerate(prune_repos, 1):
                click.echo(f"   {i}. {status.name}")
                for branch in status.merged_branches:
                    click.echo(f"      - {branch}")

            if click.confirm(click.style("\n   Execute prune action?", fg="yellow")):
                selected_prune = select_repo_statuses_interactive(prune_repos, "Select repositories for PRUNE")
                if selected_prune:
                    actions_to_execute.append(("prune", selected_prune))
            click.echo()

        if not actions_to_execute:
            click.echo(click.style("No actions selected. Exiting.", fg="yellow"))
            return

        # Show summary and final confirmation
        click.echo(click.style("=== Summary of Actions ===\n", fg="magenta", bold=True))
        for action_item in actions_to_execute:
            if len(action_item) == 3:
                action_type, repos, repo_msg_map = action_item
            else:
                action_type, repos = action_item
                repo_msg_map = {}

            click.echo(click.style(f"{action_type.upper()}:", fg="cyan", bold=True))
            for repo in repos:
                if action_type == "push":
                    commit_msg = repo_msg_map.get(repo, "Auto-commit: batch update")
                    click.echo(f"  • {repo.name}: {len(repo.changed_files)} file(s) to commit and push")
                    click.echo(f"      Message: {commit_msg}")
                elif action_type == "pull":
                    click.echo(f"  • {repo.name}:")
                    for branch, count in repo.behind_branches.items():
                        click.echo(f"      - Pull {branch} ({count} commit(s) behind)")
                elif action_type == "prune":
                    click.echo(f"  • {repo.name}:")
                    for branch in repo.merged_branches:
                        click.echo(f"      - DELETE {branch}")
            click.echo()

        if not click.confirm(click.style("Proceed with these actions?", fg="yellow", bold=True)):
            click.echo(click.style("Actions cancelled.", fg="red"))
            return

        # Execute selected actions
        all_results = {}

        for action_item in actions_to_execute:
            if len(action_item) == 3:
                # Push action with commit messages
                action_type, repos, repo_msg_map = action_item
            else:
                # Other actions
                action_type, repos = action_item
                repo_msg_map = {}

            click.echo(click.style(f"\n⚙️  Executing {action_type}...\n", fg="cyan"))

            if action_type == "push":
                results = asyncio.run(execute_action_push(repos, repo_msg_map, default_git_service))
            elif action_type == "pull":
                results = asyncio.run(execute_action_pull(statuses, default_git_service))
            elif action_type == "prune":
                results = asyncio.run(execute_action_prune(statuses, default_git_service))

            all_results.update(results)

        # Display results
        click.echo(click.style("\n=== Results ===\n", fg="green", bold=True))
        for repo_or_branch, result in all_results.items():
            if "✓" in result:
                click.echo(click.style(f"{repo_or_branch}: {result}", fg="green"))
            elif "⚠" in result:
                click.echo(click.style(f"{repo_or_branch}: {result}", fg="yellow"))
            else:
                click.echo(click.style(f"{repo_or_branch}: {result}", fg="red"))

        click.echo()
