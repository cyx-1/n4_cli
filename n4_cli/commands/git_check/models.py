"""Data models for git repository status checking."""

from pathlib import Path
from typing import Dict, List, Optional


class RepoStatus:
    """Status information for a single repository."""

    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.changed_files: List[str] = []
        self.behind_branches: Dict[str, int] = {}  # branch_name: commits_behind
        self.ahead_of_remote: int = 0  # commits ahead of upstream
        self.unpulled_commits: List[Dict[str, str]] = []  # List of unpulled commit info
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
            self.unpulled_commits or
            self.merged_branches or
            self.has_uncommitted or
            self.errors
        )
