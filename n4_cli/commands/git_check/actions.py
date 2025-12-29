"""Action execution functions for git operations."""

from typing import Dict, List

from n4_cli.git_service import GitService, default_git_service

from .models import RepoStatus


async def execute_action_push(statuses: List[RepoStatus], repo_to_message: Dict[RepoStatus, str], git_service: GitService = None) -> Dict[str, str]:
    """Push changes to main/master for repos with uncommitted changes."""
    if git_service is None:
        git_service = default_git_service

    results = {}

    for status in statuses:
        if not status.has_uncommitted or status.errors:
            continue

        repo_path = status.path

        # Get commit message for this repo
        commit_msg = repo_to_message.get(status, "Auto-commit: batch update")

        # Get main/master branch
        main_branch = await git_service.get_main_branch(repo_path)

        # Add all changes
        add_success, add_error = await git_service.add_all(repo_path)
        if not add_success:
            results[status.name] = f"Failed to add files: {add_error}"
            continue

        # Commit changes with generated message
        commit_success, commit_error = await git_service.commit(repo_path, commit_msg)
        if not commit_success:
            results[status.name] = f"Failed to commit: {commit_error}"
            continue

        # Push with retry logic
        push_success, push_error = await git_service.push(
            repo_path,
            status.current_branch or main_branch
        )

        if push_success:
            results[status.name] = "✓ Pushed successfully"
        else:
            results[status.name] = f"✗ Failed to push: {push_error}"

    return results


async def execute_action_pull(statuses: List[RepoStatus], git_service: GitService = None) -> Dict[str, str]:
    """Pull branches that are behind remote."""
    if git_service is None:
        git_service = default_git_service

    results = {}

    for status in statuses:
        if not status.behind_branches or status.errors:
            continue

        repo_path = status.path

        for branch in status.behind_branches.keys():
            # Checkout branch
            checkout_success, _ = await git_service.checkout(repo_path, branch)
            if not checkout_success:
                results[f"{status.name}/{branch}"] = "✗ Failed to checkout"
                continue

            # Pull with retry logic
            pull_success, pull_error, has_conflict = await git_service.pull(repo_path, branch)

            if has_conflict:
                results[f"{status.name}/{branch}"] = "⚠ Merge conflict - handle manually"
            elif pull_success:
                results[f"{status.name}/{branch}"] = "✓ Pulled successfully"
            else:
                results[f"{status.name}/{branch}"] = "✗ Failed to pull"

        # Return to original branch
        if status.current_branch:
            await git_service.checkout(repo_path, status.current_branch)

    return results


async def execute_action_prune(statuses: List[RepoStatus], git_service: GitService = None) -> Dict[str, str]:
    """Delete merged branches (both local and remote)."""
    if git_service is None:
        git_service = default_git_service

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
                delete_success, delete_error = await git_service.delete_remote_branch(repo_path, branch_name)
                if delete_success:
                    results[f"{status.name}/{branch}"] = "✓ Deleted from remote"

                    # Clean up the remote tracking reference
                    await git_service.run_command(f"git branch -d -r {branch}", repo_path)
                else:
                    results[f"{status.name}/{branch}"] = f"✗ Failed to delete from remote: {delete_error}"
            else:
                # Delete local branch
                delete_success, delete_error = await git_service.delete_local_branch(repo_path, branch)
                if delete_success:
                    results[f"{status.name}/{branch}"] = "✓ Deleted locally"

                    # Try to delete remote branch if it exists
                    remote_delete_success, _ = await git_service.delete_remote_branch(repo_path, branch)
                    if remote_delete_success:
                        results[f"{status.name}/{branch}"] += " and remotely"
                else:
                    results[f"{status.name}/{branch}"] = f"✗ Failed to delete: {delete_error}"

    return results
