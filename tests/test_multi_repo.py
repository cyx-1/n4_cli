"""Tests for git_check command using mock git service."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from n4_cli.commands.git_check.actions import (
    execute_action_pull,
    execute_action_prune,
    execute_action_push,
)
from n4_cli.commands.git_check.checker import check_repo_status, find_git_repos
from n4_cli.commands.git_check.models import RepoStatus
from n4_cli.commands.multi_repo import git_check
from n4_cli.git_service import GitService


@pytest.fixture
def mock_git_service():
    """Create a mock GitService instance."""
    service = MagicMock(spec=GitService)

    # Set default return values for common methods
    service.is_git_repo = AsyncMock(return_value=True)
    service.fetch_all = AsyncMock(return_value=(True, ""))
    service.get_current_branch = AsyncMock(return_value="main")
    service.get_remote_url = AsyncMock(
        return_value="https://github.com/user/repo.git"
    )
    service.get_upstream_branch = AsyncMock(return_value="origin/main")
    service.commits_ahead_of_remote = AsyncMock(return_value=0)
    service.get_unpulled_commits = AsyncMock(return_value=[])
    service.has_uncommitted_changes = AsyncMock(return_value=False)
    service.get_status_porcelain = AsyncMock(return_value=[])
    service.get_main_branch = AsyncMock(return_value="main")
    service.get_local_branches = AsyncMock(return_value=["main"])
    service.commits_behind_remote = AsyncMock(return_value=0)
    service.get_merged_branches = AsyncMock(return_value=[])
    service.run_command = AsyncMock(return_value=(0, "", ""))

    return service


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary repository path."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    return repo_path


class TestRepoStatus:
    """Test RepoStatus class."""

    def test_has_issues_no_issues(self):
        """Test has_issues returns False when repo is clean."""
        status = RepoStatus(Path("/test"))
        assert status.has_issues() is False

    def test_has_issues_with_changed_files(self):
        """Test has_issues returns True when there are changed files."""
        status = RepoStatus(Path("/test"))
        status.changed_files = ["file.txt"]
        assert status.has_issues() is True

    def test_has_issues_with_unpulled_commits(self):
        """Test has_issues returns True when there are unpulled commits."""
        status = RepoStatus(Path("/test"))
        status.unpulled_commits = [{"hash": "abc123", "message": "commit"}]
        assert status.has_issues() is True

    def test_has_issues_with_errors(self):
        """Test has_issues returns True when there are errors."""
        status = RepoStatus(Path("/test"))
        status.errors = ["Not a git repository"]
        assert status.has_issues() is True


class TestCheckRepoStatus:
    """Test check_repo_status function."""

    async def test_check_repo_status_not_git_repo(self, mock_git_service, temp_repo):
        """Test checking status when path is not a git repo."""
        mock_git_service.is_git_repo.return_value = False

        status = await check_repo_status(temp_repo, mock_git_service)

        assert len(status.errors) == 1
        assert "Not a git repository" in status.errors[0]

    async def test_check_repo_status_fetch_failure(self, mock_git_service, temp_repo):
        """Test checking status when fetch fails."""
        mock_git_service.fetch_all.return_value = (False, "Network error")

        status = await check_repo_status(temp_repo, mock_git_service)

        assert len(status.errors) == 1
        assert "Failed to fetch" in status.errors[0]

    async def test_check_repo_status_clean_repo(self, mock_git_service, temp_repo):
        """Test checking status of a clean repository."""
        status = await check_repo_status(temp_repo, mock_git_service)

        assert status.current_branch == "main"
        assert status.remote_url == "https://github.com/user/repo.git"
        assert status.has_uncommitted is False
        assert len(status.changed_files) == 0
        assert status.ahead_of_remote == 0
        assert len(status.unpulled_commits) == 0
        assert len(status.errors) == 0

    async def test_check_repo_status_with_uncommitted_changes(
        self, mock_git_service, temp_repo
    ):
        """Test checking status with uncommitted changes."""
        mock_git_service.has_uncommitted_changes.return_value = True
        mock_git_service.get_status_porcelain.return_value = ["file1.txt", "file2.py"]

        status = await check_repo_status(temp_repo, mock_git_service)

        assert status.has_uncommitted is True
        assert len(status.changed_files) == 2

    async def test_check_repo_status_with_unpushed_commits(
        self, mock_git_service, temp_repo
    ):
        """Test checking status with unpushed commits."""
        mock_git_service.commits_ahead_of_remote.return_value = 3

        status = await check_repo_status(temp_repo, mock_git_service)

        assert status.ahead_of_remote == 3

    async def test_check_repo_status_with_unpulled_commits(
        self, mock_git_service, temp_repo
    ):
        """Test checking status with unpulled commits."""
        unpulled = [
            {
                "hash": "abc12345",
                "author": "John Doe",
                "email": "john@example.com",
                "date": "2024-01-01 12:00:00",
                "message": "Fix bug",
            }
        ]
        mock_git_service.get_unpulled_commits.return_value = unpulled

        status = await check_repo_status(temp_repo, mock_git_service)

        assert len(status.unpulled_commits) == 1
        assert status.unpulled_commits[0]["hash"] == "abc12345"

    async def test_check_repo_status_with_behind_branches(
        self, mock_git_service, temp_repo
    ):
        """Test checking status with branches behind remote."""
        mock_git_service.get_local_branches.return_value = ["main", "feature"]

        async def mock_commits_behind(repo_path, branch):
            if branch == "feature":
                return 5
            return 0

        mock_git_service.commits_behind_remote.side_effect = mock_commits_behind

        status = await check_repo_status(temp_repo, mock_git_service)

        assert "feature" in status.behind_branches
        assert status.behind_branches["feature"] == 5

    async def test_check_repo_status_with_merged_branches(
        self, mock_git_service, temp_repo
    ):
        """Test checking status with merged branches."""
        mock_git_service.get_merged_branches.return_value = [
            "old-feature",
            "origin/completed-task",
        ]

        status = await check_repo_status(temp_repo, mock_git_service)

        assert "old-feature" in status.merged_branches
        assert "origin/completed-task" in status.merged_branches


class TestExecuteActionPush:
    """Test execute_action_push function."""

    async def test_execute_action_push_success(self, mock_git_service, temp_repo):
        """Test successful push action."""
        status = RepoStatus(temp_repo)
        status.name = "test_repo"
        status.has_uncommitted = True
        status.current_branch = "main"
        status.changed_files = ["file.txt"]

        mock_git_service.get_main_branch.return_value = "main"
        mock_git_service.add_all.return_value = (True, "")
        mock_git_service.commit.return_value = (True, "")
        mock_git_service.push.return_value = (True, "")

        repo_to_message = {status: "Test commit message"}
        results = await execute_action_push([status], repo_to_message, mock_git_service)

        assert "test_repo" in results
        assert "✓" in results["test_repo"]
        mock_git_service.add_all.assert_called_once()
        mock_git_service.commit.assert_called_once()
        mock_git_service.push.assert_called_once()

    async def test_execute_action_push_add_failure(self, mock_git_service, temp_repo):
        """Test push action when add fails."""
        status = RepoStatus(temp_repo)
        status.name = "test_repo"
        status.has_uncommitted = True

        mock_git_service.get_main_branch.return_value = "main"
        mock_git_service.add_all.return_value = (False, "Permission denied")

        repo_to_message = {status: "Test commit"}
        results = await execute_action_push([status], repo_to_message, mock_git_service)

        assert "test_repo" in results
        assert "Failed to add files" in results["test_repo"]

    async def test_execute_action_push_commit_failure(
        self, mock_git_service, temp_repo
    ):
        """Test push action when commit fails."""
        status = RepoStatus(temp_repo)
        status.name = "test_repo"
        status.has_uncommitted = True

        mock_git_service.get_main_branch.return_value = "main"
        mock_git_service.add_all.return_value = (True, "")
        mock_git_service.commit.return_value = (False, "Nothing to commit")

        repo_to_message = {status: "Test commit"}
        results = await execute_action_push([status], repo_to_message, mock_git_service)

        assert "test_repo" in results
        assert "Failed to commit" in results["test_repo"]

    async def test_execute_action_push_failure(self, mock_git_service, temp_repo):
        """Test push action when push fails."""
        status = RepoStatus(temp_repo)
        status.name = "test_repo"
        status.has_uncommitted = True

        mock_git_service.get_main_branch.return_value = "main"
        mock_git_service.add_all.return_value = (True, "")
        mock_git_service.commit.return_value = (True, "")
        mock_git_service.push.return_value = (False, "Network error")

        repo_to_message = {status: "Test commit"}
        results = await execute_action_push([status], repo_to_message, mock_git_service)

        assert "test_repo" in results
        assert "✗ Failed to push" in results["test_repo"]


class TestExecuteActionPull:
    """Test execute_action_pull function."""

    async def test_execute_action_pull_success(self, mock_git_service, temp_repo):
        """Test successful pull action."""
        status = RepoStatus(temp_repo)
        status.name = "test_repo"
        status.behind_branches = {"feature": 3}
        status.current_branch = "main"

        mock_git_service.checkout.return_value = (True, "")
        mock_git_service.pull.return_value = (True, "", False)

        results = await execute_action_pull([status], mock_git_service)

        assert "test_repo/feature" in results
        assert "✓ Pulled successfully" in results["test_repo/feature"]

    async def test_execute_action_pull_with_conflict(self, mock_git_service, temp_repo):
        """Test pull action with merge conflict."""
        status = RepoStatus(temp_repo)
        status.name = "test_repo"
        status.behind_branches = {"feature": 3}
        status.current_branch = "main"

        mock_git_service.checkout.return_value = (True, "")
        mock_git_service.pull.return_value = (False, "CONFLICT", True)

        results = await execute_action_pull([status], mock_git_service)

        assert "test_repo/feature" in results
        assert "⚠ Merge conflict" in results["test_repo/feature"]

    async def test_execute_action_pull_checkout_failure(
        self, mock_git_service, temp_repo
    ):
        """Test pull action when checkout fails."""
        status = RepoStatus(temp_repo)
        status.name = "test_repo"
        status.behind_branches = {"feature": 3}

        mock_git_service.checkout.return_value = (False, "Branch not found")

        results = await execute_action_pull([status], mock_git_service)

        assert "test_repo/feature" in results
        assert "✗ Failed to checkout" in results["test_repo/feature"]


class TestExecuteActionPrune:
    """Test execute_action_prune function."""

    async def test_execute_action_prune_local_branch(self, mock_git_service, temp_repo):
        """Test pruning local branch."""
        status = RepoStatus(temp_repo)
        status.name = "test_repo"
        status.merged_branches = ["old-feature"]

        mock_git_service.delete_local_branch.return_value = (True, "")
        mock_git_service.delete_remote_branch.return_value = (True, "")

        results = await execute_action_prune([status], mock_git_service)

        assert "test_repo/old-feature" in results
        assert "✓ Deleted locally" in results["test_repo/old-feature"]

    async def test_execute_action_prune_remote_branch(
        self, mock_git_service, temp_repo
    ):
        """Test pruning remote branch."""
        status = RepoStatus(temp_repo)
        status.name = "test_repo"
        status.merged_branches = ["origin/old-feature"]

        mock_git_service.delete_remote_branch.return_value = (True, "")

        results = await execute_action_prune([status], mock_git_service)

        assert "test_repo/origin/old-feature" in results
        assert "✓ Deleted from remote" in results["test_repo/origin/old-feature"]

    async def test_execute_action_prune_failure(self, mock_git_service, temp_repo):
        """Test prune action when delete fails."""
        status = RepoStatus(temp_repo)
        status.name = "test_repo"
        status.merged_branches = ["protected-branch"]

        mock_git_service.delete_local_branch.return_value = (False, "Branch protected")

        results = await execute_action_prune([status], mock_git_service)

        assert "test_repo/protected-branch" in results
        assert "✗ Failed to delete" in results["test_repo/protected-branch"]


class TestFindGitRepos:
    """Test find_git_repos function."""

    def test_find_git_repos_single_repo(self, tmp_path):
        """Test finding a single git repository."""
        repo_path = tmp_path / "repo1"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        repos = find_git_repos(tmp_path, recursive=False)

        assert len(repos) == 1
        assert repos[0] == repo_path

    def test_find_git_repos_multiple_repos(self, tmp_path):
        """Test finding multiple git repositories."""
        repo1 = tmp_path / "repo1"
        repo1.mkdir()
        (repo1 / ".git").mkdir()

        repo2 = tmp_path / "repo2"
        repo2.mkdir()
        (repo2 / ".git").mkdir()

        repos = find_git_repos(tmp_path, recursive=False)

        assert len(repos) == 2
        assert repo1 in repos
        assert repo2 in repos

    def test_find_git_repos_recursive(self, tmp_path):
        """Test finding git repositories recursively."""
        # Create nested structure
        nested_repo = tmp_path / "projects" / "nested_repo"
        nested_repo.mkdir(parents=True)
        (nested_repo / ".git").mkdir()

        repos = find_git_repos(tmp_path, recursive=True)

        assert len(repos) == 1
        assert nested_repo in repos

    def test_find_git_repos_base_is_repo(self, tmp_path):
        """Test when base path itself is a git repo."""
        (tmp_path / ".git").mkdir()

        repos = find_git_repos(tmp_path, recursive=True)

        assert len(repos) == 1
        assert repos[0] == tmp_path


class TestGitCheckCommand:
    """Test git_check CLI command."""

    def test_git_check_command_no_repos(self, tmp_path):
        """Test command when no repositories are found."""
        runner = CliRunner()
        # Note: --recursive is a flag, so we pass it or omit it (default is True)
        result = runner.invoke(
            git_check,
            ["--path", str(tmp_path)],
            catch_exceptions=True
        )

        # The command should succeed even when no repos are found
        # It will exit with 0 and display a message
        assert "No git repositories found" in result.output or result.exit_code == 0
