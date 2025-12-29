"""Repository status checking functions."""

import asyncio
from pathlib import Path
from typing import List

from n4_cli.git_service import GitService, default_git_service

from .models import RepoStatus


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


async def check_repo_status(repo_path: Path, git_service: GitService = None) -> RepoStatus:
    """Check status of a single repository asynchronously."""
    if git_service is None:
        git_service = default_git_service

    status = RepoStatus(repo_path)

    # Check if it's a git repo
    if not await git_service.is_git_repo(repo_path):
        status.errors.append("Not a git repository")
        return status

    # Fetch from remote (with retry logic and exponential backoff)
    fetch_success, fetch_error = await git_service.fetch_all(repo_path)
    if not fetch_success:
        status.errors.append(f"Failed to fetch from remote: {fetch_error}")
        return status

    # Get current branch
    current_branch = await git_service.get_current_branch(repo_path)
    if current_branch:
        status.current_branch = current_branch

    # Get remote URL
    remote_url = await git_service.get_remote_url(repo_path)
    if remote_url:
        status.remote_url = remote_url

    # Check for unpushed and unpulled commits
    if status.current_branch:
        # First, try to get the upstream tracking branch
        upstream_branch = await git_service.get_upstream_branch(repo_path, status.current_branch)

        # Determine remote branch to compare against
        remote_branch = None
        if upstream_branch:
            remote_branch = upstream_branch
        else:
            # Fallback: try origin/{current_branch}
            returncode, _, _ = await git_service.run_command(
                f"git rev-parse --verify origin/{status.current_branch}",
                repo_path
            )
            if returncode == 0:
                remote_branch = f"origin/{status.current_branch}"

        if remote_branch:
            # Get commits ahead of remote (unpushed)
            ahead_count = await git_service.commits_ahead_of_remote(repo_path, remote_branch)
            status.ahead_of_remote = ahead_count

            # Get unpulled commits (commits on remote but not local)
            unpulled_commits = await git_service.get_unpulled_commits(repo_path, remote_branch)
            status.unpulled_commits = unpulled_commits

    # Check for uncommitted changes
    status.has_uncommitted = await git_service.has_uncommitted_changes(repo_path)
    status.changed_files = await git_service.get_status_porcelain(repo_path)

    # Get main/master branch
    main_branch = await git_service.get_main_branch(repo_path)

    # Get all local branches
    local_branches = await git_service.get_local_branches(repo_path)

    if local_branches:
        # Check branches that are behind remote
        for branch in local_branches:
            behind_count = await git_service.commits_behind_remote(repo_path, branch)
            if behind_count > 0:
                status.behind_branches[branch] = behind_count

        # Check for merged branches (both local and remote)
        merged_branches = await git_service.get_merged_branches(
            repo_path,
            f"origin/{main_branch}",
            include_remote=True
        )

        # Filter out current branch
        status.merged_branches = [b for b in merged_branches if b != status.current_branch]

    return status


async def check_all_repos(repo_paths: List[Path], git_service: GitService = None) -> List[RepoStatus]:
    """Check status of all repositories in parallel."""
    if git_service is None:
        git_service = default_git_service
    tasks = [check_repo_status(path, git_service) for path in repo_paths]
    return await asyncio.gather(*tasks)
