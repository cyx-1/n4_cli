"""Git merge latest command - merges the latest commit across all remote branches into main."""

import subprocess

import click


def run_git_command(command, description):
    """Run a git command and display it."""
    click.echo(click.style(f"\n> {description}", fg="cyan", bold=True))
    click.echo(click.style(f"$ {command}", fg="white"))

    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )

        if result.stdout:
            click.echo(result.stdout.rstrip())

        return result.stdout.strip()

    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"Error: {e.stderr}", fg="red"), err=True)
        raise click.Abort()


@click.command(name="git-merge-latest")
@click.option("--dry-run", is_flag=True, help="Show commands without executing")
def git_merge_latest(dry_run):
    """Merge the latest commit across all remote branches into main.

    This command:
    1. Checks out the main branch
    2. Updates main to the latest commit (pull)
    3. Finds the latest commit across all remote branches
    4. Merges that commit into main
    5. Pushes main to remote

    Examples:
      n4_cli git-merge-latest           # Execute the merge
      n4_cli git-merge-latest --dry-run # Show what would be executed
    """
    if dry_run:
        click.echo(click.style("DRY RUN MODE - Commands that would be executed:", fg="yellow", bold=True))
        click.echo()

    commands = [
        ("git checkout main", "Checkout main branch"),
        ("git pull origin main", "Update main branch to latest commit"),
        ("git fetch --all", "Fetch all remote branches"),
        ("git for-each-ref --sort=-committerdate refs/remotes/origin --format='%(objectname)' | head -1", "Find latest commit across all remote branches"),
    ]

    if dry_run:
        for cmd, desc in commands:
            click.echo(click.style(f"\n> {desc}", fg="cyan", bold=True))
            click.echo(click.style(f"$ {cmd}", fg="white"))

        click.echo(click.style("\n> Merge to latest commit", fg="cyan", bold=True))
        click.echo(click.style("$ git merge <latest_commit_hash>", fg="white"))

        click.echo(click.style("\n> Push main branch to remote", fg="cyan", bold=True))
        click.echo(click.style("$ git push origin main", fg="white"))
        click.echo()
        return

    # Execute commands
    click.echo(click.style("=== Git Merge Latest ===", fg="green", bold=True))

    # Step 1: Checkout main
    run_git_command("git checkout main", "Checkout main branch")

    # Step 2: Update main branch
    run_git_command("git pull origin main", "Update main branch to latest commit")

    # Step 3: Fetch all remote branches
    run_git_command("git fetch --all", "Fetch all remote branches")

    # Step 4: Find latest commit
    latest_commit = run_git_command(
        "git for-each-ref --sort=-committerdate refs/remotes/origin --format='%(objectname)' | head -1",
        "Find latest commit across all remote branches"
    )

    if not latest_commit:
        click.echo(click.style("Error: Could not find latest commit", fg="red"), err=True)
        raise click.Abort()

    click.echo(click.style(f"\n[OK] Latest commit: {latest_commit}", fg="green"))

    # Step 5: Merge to latest commit
    run_git_command(f"git merge {latest_commit}", f"Merge to {latest_commit}")

    # Step 6: Push to remote
    run_git_command("git push origin main", "Push main branch to remote")

    click.echo()
    click.echo(click.style("[OK] Successfully merged and pushed to main", fg="green", bold=True))
