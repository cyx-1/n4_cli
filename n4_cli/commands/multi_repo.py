"""Multi-repo management - parallel async operations across multiple git repositories."""

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import click
import questionary
import yaml
from rich.console import Console
from rich.table import Table


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

        proc = await asyncio.create_subprocess_shell(
            f'claude --model haiku -p "{prompt}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(repo_path)
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0 and stdout:
            output = stdout.decode().strip()

            # Strip markdown code blocks if present
            if output.startswith('```yaml') or output.startswith('```'):
                # Remove code block markers
                lines = output.split('\n')
                # Find start and end of code block
                yaml_content = []
                in_block = False
                for line in lines:
                    if line.strip().startswith('```'):
                        in_block = not in_block
                        continue
                    if in_block or (not line.strip().startswith('```')):
                        yaml_content.append(line)
                output = '\n'.join(yaml_content).strip()

            # Try to parse YAML
            try:
                data = yaml.safe_load(output)
                # Check for both 'commit_msg' and 'commit_message' keys
                if isinstance(data, dict):
                    msg = data.get('commit_msg') or data.get('commit_message')
                    if msg:
                        msg = str(msg).strip()
                        # Limit to 100 chars for table display
                        if len(msg) > 100:
                            msg = msg[:97] + "..."
                        return msg
            except yaml.YAMLError:
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
                                if len(msg) > 100:
                                    msg = msg[:97] + "..."
                                return msg
                        # Otherwise try direct extraction
                        msg = line.strip('"').strip("'").strip()
                        if len(msg) > 20:  # Only accept if it's substantial
                            if len(msg) > 100:
                                msg = msg[:97] + "..."
                            return msg

            return "Update changes"
        else:
            return "Update changes"
    except Exception:
        return "Update changes"


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


def select_repo_statuses_interactive(statuses: List["RepoStatus"], prompt: str = "Select repositories") -> List["RepoStatus"]:
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


class RepoStatus:
    """Status information for a single repository."""

    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.changed_files: List[str] = []
        self.behind_branches: Dict[str, int] = {}  # branch_name: commits_behind
        self.ahead_of_remote: int = 0  # commits ahead of upstream
        self.merged_branches: List[str] = []
        self.current_branch: Optional[str] = None
        self.remote_url: Optional[str] = None
        self.has_uncommitted: bool = False
        self.errors: List[str] = []

    def has_issues(self) -> bool:
        """Check if repo has any issues to report."""
        return bool(
            self.changed_files or
            self.behind_branches or
            self.ahead_of_remote or
            self.merged_branches or
            self.has_uncommitted or
            self.errors
        )


async def run_git_async(command: str, cwd: Path) -> Tuple[int, str, str]:
    """Run a git command asynchronously and return (returncode, stdout, stderr)."""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd)
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode().strip(), stderr.decode().strip()
    except Exception as e:
        return 1, "", str(e)


async def check_repo_status(repo_path: Path) -> RepoStatus:
    """Check status of a single repository asynchronously."""
    status = RepoStatus(repo_path)

    # Check if it's a git repo
    returncode, _, _ = await run_git_async("git rev-parse --git-dir", repo_path)
    if returncode != 0:
        status.errors.append("Not a git repository")
        return status

    # Fetch from remote (with retry logic and exponential backoff)
    for attempt in range(4):
        returncode, _, stderr = await run_git_async(
            "git fetch --all --prune",
            repo_path
        )
        if returncode == 0:
            break
        if attempt < 3:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
    else:
        status.errors.append(f"Failed to fetch from remote: {stderr}")
        return status

    # Get current branch
    returncode, current_branch, _ = await run_git_async(
        "git rev-parse --abbrev-ref HEAD",
        repo_path
    )
    if returncode == 0 and current_branch:
        status.current_branch = current_branch

    # Get remote URL
    returncode, remote_url, _ = await run_git_async(
        "git remote get-url origin",
        repo_path
    )
    if returncode == 0 and remote_url:
        status.remote_url = remote_url

    # Check for unpushed commits (commits ahead of upstream)
    if status.current_branch:
        # Check if current branch has upstream
        returncode, _, _ = await run_git_async(
            f"git rev-parse --abbrev-ref {status.current_branch}@{{upstream}}",
            repo_path
        )
        if returncode == 0:
            # Get commits ahead of upstream
            returncode, ahead_output, _ = await run_git_async(
                f"git rev-list --count @{{upstream}}..HEAD",
                repo_path
            )
            if returncode == 0 and ahead_output and int(ahead_output) > 0:
                status.ahead_of_remote = int(ahead_output)

    # Check for uncommitted changes
    returncode, output, _ = await run_git_async("git status --porcelain", repo_path)
    if returncode == 0 and output:
        status.has_uncommitted = True
        status.changed_files = [line[3:] for line in output.split('\n') if line]

    # Get main/master branch
    returncode, main_branch, _ = await run_git_async(
        "git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'",
        repo_path
    )
    if returncode != 0 or not main_branch:
        # Fallback: check if main or master exists
        returncode, _, _ = await run_git_async("git rev-parse --verify origin/main", repo_path)
        main_branch = "main" if returncode == 0 else "master"

    # Get all local branches
    returncode, branches_output, _ = await run_git_async(
        "git for-each-ref --format='%(refname:short)' refs/heads/",
        repo_path
    )
    if returncode == 0 and branches_output:
        local_branches = branches_output.split('\n')

        # Check branches that are behind remote
        for branch in local_branches:
            # Check if remote tracking branch exists
            returncode, _, _ = await run_git_async(
                f"git rev-parse --verify origin/{branch}",
                repo_path
            )
            if returncode != 0:
                continue

            # Get commits behind
            returncode, behind_output, _ = await run_git_async(
                f"git rev-list --count {branch}..origin/{branch}",
                repo_path
            )
            if returncode == 0 and behind_output and int(behind_output) > 0:
                status.behind_branches[branch] = int(behind_output)

        # Check for merged branches (both local and remote)
        # Get local branches merged into origin/main or origin/master
        returncode, merged_output, _ = await run_git_async(
            f"git branch --merged origin/{main_branch}",
            repo_path
        )

        if returncode == 0 and merged_output:
            # Parse the output and filter branches
            for line in merged_output.split('\n'):
                branch = line.strip().lstrip('* ').strip()
                if not branch:
                    continue

                # Exclude main, master, and current branch
                if branch in ['main', 'master', status.current_branch]:
                    continue

                status.merged_branches.append(branch)

        # Get remote branches merged into origin/main or origin/master
        returncode, remote_merged_output, _ = await run_git_async(
            f"git branch -r --merged origin/{main_branch}",
            repo_path
        )

        if returncode == 0 and remote_merged_output:
            # Parse the output and filter remote branches
            for line in remote_merged_output.split('\n'):
                branch = line.strip().lstrip('* ').strip()
                if not branch:
                    continue

                # Exclude symbolic references like "origin/HEAD -> origin/main"
                if '->' in branch:
                    continue

                # Exclude origin/main, origin/master, and origin/HEAD
                if branch in [f'origin/{main_branch}', 'origin/main', 'origin/master', 'origin/HEAD']:
                    continue

                # Only include origin/ branches (not other remotes)
                if branch.startswith('origin/'):
                    status.merged_branches.append(branch)

    return status


async def check_all_repos(repo_paths: List[Path]) -> List[RepoStatus]:
    """Check status of all repositories in parallel."""
    tasks = [check_repo_status(path) for path in repo_paths]
    return await asyncio.gather(*tasks)


def find_git_repos(base_path: Path, recursive: bool = False) -> List[Path]:
    """Find all git repositories in the base path.

    When recursive=True, stops recursing once a git repo is found.
    """
    repos = []

    # Check if base_path itself is a git repo
    if (base_path / ".git").exists():
        repos.append(base_path)
        return repos

    # Search for git repos in subdirectories
    if recursive:
        # Manual recursive walk that stops at git repos
        def _recursive_search(path: Path):
            try:
                for item in path.iterdir():
                    if not item.is_dir():
                        continue

                    # Check if this directory is a git repo
                    if (item / ".git").exists():
                        repos.append(item)
                        # Don't recurse further into this git repo
                        continue

                    # Recurse into subdirectories
                    _recursive_search(item)
            except PermissionError:
                # Skip directories we can't access
                pass

        _recursive_search(base_path)
    else:
        for item in base_path.iterdir():
            if item.is_dir() and (item / ".git").exists():
                repos.append(item)

    return sorted(repos, key=lambda p: p.name)


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
            behind_text,
            merged_text,
            remote
        )

    console.print("\n")
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


async def execute_action_push(statuses: List[RepoStatus], repo_to_message: Dict[RepoStatus, str]) -> Dict[str, str]:
    """Push changes to main/master for repos with uncommitted changes."""
    results = {}

    for status in statuses:
        if not status.has_uncommitted or status.errors:
            continue

        repo_path = status.path

        # Get commit message for this repo
        commit_msg = repo_to_message.get(status, "Auto-commit: batch update")

        # Get main/master branch
        returncode, main_branch, _ = await run_git_async(
            "git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'",
            repo_path
        )
        if returncode != 0:
            returncode, _, _ = await run_git_async("git rev-parse --verify origin/main", repo_path)
            main_branch = "main" if returncode == 0 else "master"

        # Add all changes
        returncode, _, stderr = await run_git_async("git add -A", repo_path)
        if returncode != 0:
            results[status.name] = f"Failed to add files: {stderr}"
            continue

        # Commit changes with generated message
        # Escape quotes in commit message
        commit_msg_escaped = commit_msg.replace('"', '\\"')
        returncode, _, stderr = await run_git_async(
            f'git commit -m "{commit_msg_escaped}"',
            repo_path
        )
        if returncode != 0:
            results[status.name] = f"Failed to commit: {stderr}"
            continue

        # Push with retry logic
        push_success = False
        for attempt in range(4):
            returncode, _, stderr = await run_git_async(
                f"git push -u origin {status.current_branch or main_branch}",
                repo_path
            )
            if returncode == 0:
                push_success = True
                break
            if attempt < 3:
                await asyncio.sleep(2 ** (attempt + 1))  # 2s, 4s, 8s

        if push_success:
            results[status.name] = "✓ Pushed successfully"
        else:
            results[status.name] = f"✗ Failed to push: {stderr}"

    return results


async def execute_action_pull(statuses: List[RepoStatus]) -> Dict[str, str]:
    """Pull branches that are behind remote."""
    results = {}

    for status in statuses:
        if not status.behind_branches or status.errors:
            continue

        repo_path = status.path

        for branch in status.behind_branches.keys():
            # Checkout branch
            returncode, _, _ = await run_git_async(f"git checkout {branch}", repo_path)
            if returncode != 0:
                results[f"{status.name}/{branch}"] = "✗ Failed to checkout"
                continue

            # Pull with retry logic
            pull_success = False
            merge_conflict = False
            for attempt in range(4):
                returncode, stdout, stderr = await run_git_async(
                    f"git pull origin {branch}",
                    repo_path
                )
                if returncode == 0:
                    pull_success = True
                    break
                if "CONFLICT" in stdout or "CONFLICT" in stderr:
                    merge_conflict = True
                    break
                if attempt < 3:
                    await asyncio.sleep(2 ** (attempt + 1))

            if merge_conflict:
                results[f"{status.name}/{branch}"] = "⚠ Merge conflict - handle manually"
            elif pull_success:
                results[f"{status.name}/{branch}"] = "✓ Pulled successfully"
            else:
                results[f"{status.name}/{branch}"] = "✗ Failed to pull"

        # Return to original branch
        if status.current_branch:
            await run_git_async(f"git checkout {status.current_branch}", repo_path)

    return results


async def execute_action_prune(statuses: List[RepoStatus]) -> Dict[str, str]:
    """Delete merged branches (both local and remote)."""
    results = {}

    for status in statuses:
        if not status.merged_branches or status.errors:
            continue

        repo_path = status.path

        for branch in status.merged_branches:
            # Check if this is a remote branch
            if branch.startswith('origin/'):
                # Extract branch name without origin/ prefix
                branch_name = branch.replace('origin/', '', 1)

                # Delete from remote
                returncode, _, stderr = await run_git_async(
                    f"git push origin --delete {branch_name}",
                    repo_path
                )
                if returncode == 0:
                    results[f"{status.name}/{branch}"] = "✓ Deleted from remote"

                    # Clean up the remote tracking reference
                    await run_git_async(f"git branch -d -r {branch}", repo_path)
                else:
                    results[f"{status.name}/{branch}"] = f"✗ Failed to delete from remote: {stderr}"
            else:
                # Delete local branch
                returncode, _, stderr = await run_git_async(f"git branch -d {branch}", repo_path)
                if returncode == 0:
                    results[f"{status.name}/{branch}"] = "✓ Deleted locally"

                    # Try to delete remote branch if it exists
                    returncode, _, _ = await run_git_async(
                        f"git push origin --delete {branch}",
                        repo_path
                    )
                    if returncode == 0:
                        results[f"{status.name}/{branch}"] += " and remotely"
                else:
                    results[f"{status.name}/{branch}"] = f"✗ Failed to delete: {stderr}"

    return results


@click.command(name="git")
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
def multi_repo(path: Path, recursive: bool, verbose: bool, action: bool):
    """Manage multiple git repositories in parallel.

    This command analyzes all git repositories in the specified path and reports:
    - Changed files (uncommitted/unstaged)
    - Unpushed commits (commits ahead of remote)
    - Branches behind their remote tracking branch
    - Branches that have been merged to main/master

    By default, searches recursively for all git repositories in subdirectories.
    Use --action for interactive mode to select and execute batch operations.

    Examples:
      n4 git                       # Check current directory recursively
      n4 git -p ~/projects         # Check ~/projects recursively
      n4 git --no-recursive        # Check only current directory (no subdirs)
      n4 git -v                    # Show all repos including clean ones
      n4 git --action              # Interactive mode to execute actions
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
                results = asyncio.run(execute_action_push(repos, repo_msg_map))
            elif action_type == "pull":
                results = asyncio.run(execute_action_pull(statuses))
            elif action_type == "prune":
                results = asyncio.run(execute_action_prune(statuses))

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
