"""Git service layer - abstracts git operations for testability and reusability."""

import asyncio
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class GitService:
    """Service for executing git operations."""

    async def run_command(self, command: str, cwd: Path) -> Tuple[int, str, str]:
        """Run a git command asynchronously and return (returncode, stdout, stderr).

        Args:
            command: The git command to execute
            cwd: The working directory to execute the command in

        Returns:
            Tuple of (returncode, stdout, stderr)
        """
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

    async def is_git_repo(self, repo_path: Path) -> bool:
        """Check if a path is a git repository.

        Args:
            repo_path: Path to check

        Returns:
            True if the path is a git repository
        """
        returncode, _, _ = await self.run_command("git rev-parse --git-dir", repo_path)
        return returncode == 0

    async def fetch_all(self, repo_path: Path, max_retries: int = 4) -> Tuple[bool, str]:
        """Fetch all remotes with retry logic.

        Args:
            repo_path: Path to the git repository
            max_retries: Maximum number of retry attempts

        Returns:
            Tuple of (success, error_message)
        """
        for attempt in range(max_retries):
            returncode, _, stderr = await self.run_command(
                "git fetch --all --prune",
                repo_path
            )
            if returncode == 0:
                return True, ""
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
        return False, stderr

    async def get_current_branch(self, repo_path: Path) -> Optional[str]:
        """Get the current branch name.

        Args:
            repo_path: Path to the git repository

        Returns:
            Current branch name or None if failed
        """
        returncode, current_branch, _ = await self.run_command(
            "git rev-parse --abbrev-ref HEAD",
            repo_path
        )
        if returncode == 0 and current_branch:
            return current_branch
        return None

    async def get_remote_url(self, repo_path: Path) -> Optional[str]:
        """Get the remote URL for origin.

        Args:
            repo_path: Path to the git repository

        Returns:
            Remote URL or None if failed
        """
        returncode, remote_url, _ = await self.run_command(
            "git remote get-url origin",
            repo_path
        )
        if returncode == 0 and remote_url:
            return remote_url
        return None

    async def get_upstream_branch(self, repo_path: Path, branch: str) -> Optional[str]:
        """Get the upstream tracking branch for a given branch.

        Args:
            repo_path: Path to the git repository
            branch: The branch to check

        Returns:
            Upstream branch name or None if no upstream
        """
        returncode, upstream_branch, _ = await self.run_command(
            f"git rev-parse --abbrev-ref {branch}@{{upstream}}",
            repo_path
        )
        if returncode == 0 and upstream_branch:
            return upstream_branch.strip()
        return None

    async def commits_ahead_of_remote(self, repo_path: Path, remote_branch: str) -> int:
        """Get number of commits ahead of remote.

        Args:
            repo_path: Path to the git repository
            remote_branch: The remote branch to compare against

        Returns:
            Number of commits ahead
        """
        returncode, ahead_output, _ = await self.run_command(
            f"git rev-list --count {remote_branch}..HEAD",
            repo_path
        )
        if returncode == 0 and ahead_output and ahead_output.isdigit():
            return int(ahead_output)
        return 0

    async def get_unpulled_commits(self, repo_path: Path, remote_branch: str, max_count: int = 20) -> List[Dict[str, str]]:
        """Get list of unpulled commits from remote.

        Args:
            repo_path: Path to the git repository
            remote_branch: The remote branch to check
            max_count: Maximum number of commits to retrieve

        Returns:
            List of commit dictionaries with hash, author, email, date, message
        """
        returncode, unpulled_output, _ = await self.run_command(
            f"git log HEAD..{remote_branch} --pretty=format:'%H|%an|%ae|%ai|%s' --max-count={max_count}",
            repo_path
        )

        commits = []
        if returncode == 0 and unpulled_output:
            for line in unpulled_output.split('\n'):
                if line.strip():
                    parts = line.split('|')
                    if len(parts) >= 5:
                        commits.append({
                            'hash': parts[0][:8],  # Short hash
                            'author': parts[1],
                            'email': parts[2],
                            'date': parts[3],
                            'message': parts[4]
                        })
        return commits

    async def get_status_porcelain(self, repo_path: Path) -> List[str]:
        """Get changed files using git status --porcelain.

        Args:
            repo_path: Path to the git repository

        Returns:
            List of changed file paths
        """
        returncode, output, _ = await self.run_command("git status --porcelain", repo_path)
        if returncode == 0 and output:
            return [line[3:] for line in output.split('\n') if line]
        return []

    async def has_uncommitted_changes(self, repo_path: Path) -> bool:
        """Check if repository has uncommitted changes.

        Args:
            repo_path: Path to the git repository

        Returns:
            True if there are uncommitted changes
        """
        files = await self.get_status_porcelain(repo_path)
        return len(files) > 0

    async def get_main_branch(self, repo_path: Path) -> str:
        """Get the main/master branch name.

        Args:
            repo_path: Path to the git repository

        Returns:
            Main branch name (defaults to "main" or "master")
        """
        returncode, main_branch, _ = await self.run_command(
            "git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'",
            repo_path
        )
        if returncode != 0 or not main_branch:
            # Fallback: check if main or master exists
            returncode, _, _ = await self.run_command("git rev-parse --verify origin/main", repo_path)
            main_branch = "main" if returncode == 0 else "master"
        return main_branch

    async def get_local_branches(self, repo_path: Path) -> List[str]:
        """Get all local branches.

        Args:
            repo_path: Path to the git repository

        Returns:
            List of local branch names
        """
        returncode, branches_output, _ = await self.run_command(
            "git for-each-ref --format='%(refname:short)' refs/heads/",
            repo_path
        )
        if returncode == 0 and branches_output:
            return branches_output.split('\n')
        return []

    async def commits_behind_remote(self, repo_path: Path, branch: str) -> int:
        """Get number of commits a branch is behind its remote.

        Args:
            repo_path: Path to the git repository
            branch: The branch to check

        Returns:
            Number of commits behind
        """
        # Check if remote tracking branch exists
        returncode, _, _ = await self.run_command(
            f"git rev-parse --verify origin/{branch}",
            repo_path
        )
        if returncode != 0:
            return 0

        # Get commits behind
        returncode, behind_output, _ = await self.run_command(
            f"git rev-list --count {branch}..origin/{branch}",
            repo_path
        )
        if returncode == 0 and behind_output and behind_output.isdigit():
            return int(behind_output)
        return 0

    async def get_merged_branches(self, repo_path: Path, target_branch: str, include_remote: bool = True) -> List[str]:
        """Get branches that have been merged into target branch.

        Args:
            repo_path: Path to the git repository
            target_branch: The branch to check merges into (e.g., "origin/main")
            include_remote: Whether to include remote branches

        Returns:
            List of merged branch names
        """
        merged_branches = []

        # Get local branches merged into target
        returncode, merged_output, _ = await self.run_command(
            f"git branch --merged {target_branch}",
            repo_path
        )

        if returncode == 0 and merged_output:
            for line in merged_output.split('\n'):
                branch = line.strip().lstrip('* ').strip()
                if branch and branch not in ['main', 'master']:
                    merged_branches.append(branch)

        # Get remote branches merged into target
        if include_remote:
            returncode, remote_merged_output, _ = await self.run_command(
                f"git branch -r --merged {target_branch}",
                repo_path
            )

            if returncode == 0 and remote_merged_output:
                for line in remote_merged_output.split('\n'):
                    branch = line.strip().lstrip('* ').strip()
                    if not branch or '->' in branch:
                        continue
                    if branch in [f'origin/{target_branch}', 'origin/main', 'origin/master', 'origin/HEAD']:
                        continue
                    if branch.startswith('origin/'):
                        merged_branches.append(branch)

        return merged_branches

    async def add_all(self, repo_path: Path) -> Tuple[bool, str]:
        """Add all changes to staging.

        Args:
            repo_path: Path to the git repository

        Returns:
            Tuple of (success, error_message)
        """
        returncode, _, stderr = await self.run_command("git add -A", repo_path)
        return returncode == 0, stderr

    async def commit(self, repo_path: Path, message: str) -> Tuple[bool, str]:
        """Commit changes with a message.

        Args:
            repo_path: Path to the git repository
            message: Commit message

        Returns:
            Tuple of (success, error_message)
        """
        # Escape quotes in commit message
        message_escaped = message.replace('"', '\\"')
        returncode, _, stderr = await self.run_command(
            f'git commit -m "{message_escaped}"',
            repo_path
        )
        return returncode == 0, stderr

    async def push(self, repo_path: Path, branch: str, max_retries: int = 4) -> Tuple[bool, str]:
        """Push branch to remote with retry logic.

        Args:
            repo_path: Path to the git repository
            branch: Branch to push
            max_retries: Maximum number of retry attempts

        Returns:
            Tuple of (success, error_message)
        """
        for attempt in range(max_retries):
            returncode, _, stderr = await self.run_command(
                f"git push -u origin {branch}",
                repo_path
            )
            if returncode == 0:
                return True, ""
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** (attempt + 1))  # 2s, 4s, 8s
        return False, stderr

    async def pull(self, repo_path: Path, branch: str, max_retries: int = 4) -> Tuple[bool, str, bool]:
        """Pull branch from remote with retry logic.

        Args:
            repo_path: Path to the git repository
            branch: Branch to pull
            max_retries: Maximum number of retry attempts

        Returns:
            Tuple of (success, error_message, has_merge_conflict)
        """
        for attempt in range(max_retries):
            returncode, stdout, stderr = await self.run_command(
                f"git pull origin {branch}",
                repo_path
            )
            if returncode == 0:
                return True, "", False
            if "CONFLICT" in stdout or "CONFLICT" in stderr:
                return False, stderr, True
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** (attempt + 1))
        return False, stderr, False

    async def checkout(self, repo_path: Path, branch: str) -> Tuple[bool, str]:
        """Checkout a branch.

        Args:
            repo_path: Path to the git repository
            branch: Branch to checkout

        Returns:
            Tuple of (success, error_message)
        """
        returncode, _, stderr = await self.run_command(f"git checkout {branch}", repo_path)
        return returncode == 0, stderr

    async def delete_local_branch(self, repo_path: Path, branch: str) -> Tuple[bool, str]:
        """Delete a local branch.

        Args:
            repo_path: Path to the git repository
            branch: Branch to delete

        Returns:
            Tuple of (success, error_message)
        """
        returncode, _, stderr = await self.run_command(f"git branch -d {branch}", repo_path)
        return returncode == 0, stderr

    async def delete_remote_branch(self, repo_path: Path, branch: str) -> Tuple[bool, str]:
        """Delete a remote branch.

        Args:
            repo_path: Path to the git repository
            branch: Branch to delete (without 'origin/' prefix)

        Returns:
            Tuple of (success, error_message)
        """
        returncode, _, stderr = await self.run_command(
            f"git push origin --delete {branch}",
            repo_path
        )
        return returncode == 0, stderr


# Default instance
default_git_service = GitService()
