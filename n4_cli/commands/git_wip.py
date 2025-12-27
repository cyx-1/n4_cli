"""Git WIP (Work In Progress) - Check multiple git repositories for unpushed changes."""

import os
from pathlib import Path
import subprocess

import click


@click.command(name="git-wip")
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to .n4_cli config file (default: ~/.n4_cli)")
def git_wip(config):
    """Check multiple git repositories for uncommitted or unpushed changes.

    Reads a list of git project paths from ~/.n4_cli (or specified config file)
    and reports which projects have:
    - Uncommitted changes (modified, added, deleted files)
    - Commits not yet pushed to remote

    Config file format (.n4_cli):
      One project path per line, e.g.:
        /home/user/project1
        /home/user/project2
        ~/code/myproject

      Lines starting with # are ignored as comments.

    Examples:
      n4 git-wip                    # Use default ~/.n4_cli
      n4 git-wip -c my-projects.txt # Use custom config file
    """
    # Determine config file path
    if not config:
        config = Path.home() / ".n4_cli"
    else:
        config = Path(config)

    if not config.exists():
        click.echo(click.style(f"Error: Config file not found: {config}", fg="red"), err=True)
        click.echo(click.style(f"Create a .n4_cli file with one project path per line", fg="yellow"), err=True)
        raise click.Abort()

    # Read project paths
    try:
        with open(config, 'r') as f:
            project_paths = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    except Exception as e:
        click.echo(click.style(f"Error reading config file: {e}", fg="red"), err=True)
        raise click.Abort()

    if not project_paths:
        click.echo(click.style("No project paths found in config file", fg="yellow"))
        return

    click.echo(click.style(f"Checking {len(project_paths)} projects...\n", fg="cyan", bold=True))

    projects_with_changes = []
    projects_clean = []
    projects_error = []

    for project_path in project_paths:
        # Expand ~ to home directory
        project_path = os.path.expanduser(project_path)
        project_path = Path(project_path)

        if not project_path.exists():
            projects_error.append((project_path, "Path does not exist"))
            continue

        if not (project_path / ".git").exists():
            projects_error.append((project_path, "Not a git repository"))
            continue

        # Check for uncommitted changes
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            has_uncommitted = bool(result.stdout.strip())
        except Exception as e:
            projects_error.append((project_path, f"Error checking status: {e}"))
            continue

        # Check for unpushed commits
        try:
            # Get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            current_branch = result.stdout.strip()

            # Check if branch has upstream
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", f"{current_branch}@{{upstream}}"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            has_upstream = result.returncode == 0
            has_unpushed = False
            unpushed_count = 0

            if has_upstream:
                # Check for unpushed commits
                result = subprocess.run(
                    ["git", "log", "@{upstream}..HEAD", "--oneline"],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                unpushed_lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
                has_unpushed = bool(unpushed_lines)
                unpushed_count = len(unpushed_lines) if has_unpushed else 0

        except Exception as e:
            projects_error.append((project_path, f"Error checking commits: {e}"))
            continue

        # Categorize project
        if has_uncommitted or has_unpushed:
            status_details = []
            if has_uncommitted:
                status_details.append("uncommitted changes")
            if has_unpushed:
                status_details.append(f"{unpushed_count} unpushed commit{'s' if unpushed_count != 1 else ''}")
            projects_with_changes.append((project_path, ", ".join(status_details)))
        else:
            projects_clean.append(project_path)

    # Display results
    if projects_with_changes:
        click.echo(click.style("Projects with changes:", fg="yellow", bold=True))
        for project, status in projects_with_changes:
            click.echo(click.style(f"  [!] {project}", fg="yellow"))
            click.echo(click.style(f"      {status}", fg="cyan"))
        click.echo()

    if projects_clean:
        click.echo(click.style("Clean projects:", fg="green", bold=True))
        for project in projects_clean:
            click.echo(click.style(f"  [OK] {project}", fg="green"))
        click.echo()

    if projects_error:
        click.echo(click.style("Projects with errors:", fg="red", bold=True))
        for project, error in projects_error:
            click.echo(click.style(f"  [X] {project}", fg="red"))
            click.echo(click.style(f"      {error}", fg="red"))
        click.echo()

    # Summary
    click.echo(click.style("Summary:", fg="cyan", bold=True))
    click.echo(f"  Total: {len(project_paths)}")
    click.echo(click.style(f"  With changes: {len(projects_with_changes)}", fg="yellow" if projects_with_changes else "green"))
    click.echo(click.style(f"  Clean: {len(projects_clean)}", fg="green"))
    if projects_error:
        click.echo(click.style(f"  Errors: {len(projects_error)}", fg="red"))
