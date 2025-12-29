"""Tests for git_service module."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from n4_cli.git_service import GitService


@pytest.fixture
def git_service():
    """Create a GitService instance for testing."""
    return GitService()


@pytest.fixture
def mock_repo_path(tmp_path):
    """Create a temporary repository path."""
    return tmp_path / "test_repo"


class TestGitService:
    """Test GitService methods."""

    async def test_run_command_success(self, git_service, mock_repo_path):
        """Test successful command execution."""
        with patch("asyncio.create_subprocess_shell") as mock_subprocess:
            # Mock process
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"output", b""))
            mock_proc.returncode = 0
            mock_subprocess.return_value = mock_proc

            returncode, stdout, stderr = await git_service.run_command(
                "git status", mock_repo_path
            )

            assert returncode == 0
            assert stdout == "output"
            assert stderr == ""

    async def test_run_command_error(self, git_service, mock_repo_path):
        """Test command execution with error."""
        with patch("asyncio.create_subprocess_shell") as mock_subprocess:
            # Mock process with error
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b"error message"))
            mock_proc.returncode = 1
            mock_subprocess.return_value = mock_proc

            returncode, stdout, stderr = await git_service.run_command(
                "git status", mock_repo_path
            )

            assert returncode == 1
            assert stdout == ""
            assert stderr == "error message"

    async def test_is_git_repo_true(self, git_service, mock_repo_path):
        """Test checking if path is a git repository (true case)."""
        with patch.object(git_service, "run_command", return_value=(0, "", "")):
            result = await git_service.is_git_repo(mock_repo_path)
            assert result is True

    async def test_is_git_repo_false(self, git_service, mock_repo_path):
        """Test checking if path is a git repository (false case)."""
        with patch.object(git_service, "run_command", return_value=(1, "", "error")):
            result = await git_service.is_git_repo(mock_repo_path)
            assert result is False

    async def test_fetch_all_success(self, git_service, mock_repo_path):
        """Test successful fetch."""
        with patch.object(git_service, "run_command", return_value=(0, "", "")):
            success, error = await git_service.fetch_all(mock_repo_path, max_retries=1)
            assert success is True
            assert error == ""

    async def test_fetch_all_with_retry(self, git_service, mock_repo_path):
        """Test fetch with retry logic."""
        # First call fails, second succeeds
        call_count = 0

        async def mock_run_command(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (1, "", "network error")
            return (0, "", "")

        with patch.object(git_service, "run_command", side_effect=mock_run_command):
            success, error = await git_service.fetch_all(mock_repo_path, max_retries=2)
            assert success is True
            assert call_count == 2

    async def test_get_current_branch(self, git_service, mock_repo_path):
        """Test getting current branch name."""
        with patch.object(git_service, "run_command", return_value=(0, "main", "")):
            branch = await git_service.get_current_branch(mock_repo_path)
            assert branch == "main"

    async def test_get_remote_url(self, git_service, mock_repo_path):
        """Test getting remote URL."""
        url = "https://github.com/user/repo.git"
        with patch.object(git_service, "run_command", return_value=(0, url, "")):
            remote_url = await git_service.get_remote_url(mock_repo_path)
            assert remote_url == url

    async def test_get_upstream_branch(self, git_service, mock_repo_path):
        """Test getting upstream branch."""
        with patch.object(
            git_service, "run_command", return_value=(0, "origin/main", "")
        ):
            upstream = await git_service.get_upstream_branch(mock_repo_path, "main")
            assert upstream == "origin/main"

    async def test_commits_ahead_of_remote(self, git_service, mock_repo_path):
        """Test getting number of commits ahead of remote."""
        with patch.object(git_service, "run_command", return_value=(0, "5", "")):
            count = await git_service.commits_ahead_of_remote(
                mock_repo_path, "origin/main"
            )
            assert count == 5

    async def test_get_unpulled_commits(self, git_service, mock_repo_path):
        """Test getting unpulled commits."""
        commit_output = "abc12345|John Doe|john@example.com|2024-01-01 12:00:00|Fix bug"
        with patch.object(git_service, "run_command", return_value=(0, commit_output, "")):
            commits = await git_service.get_unpulled_commits(
                mock_repo_path, "origin/main"
            )
            assert len(commits) == 1
            assert commits[0]["hash"] == "abc12345"
            assert commits[0]["author"] == "John Doe"
            assert commits[0]["message"] == "Fix bug"

    async def test_has_uncommitted_changes_true(self, git_service, mock_repo_path):
        """Test checking for uncommitted changes (true case)."""
        with patch.object(
            git_service, "get_status_porcelain", return_value=["file.txt"]
        ):
            result = await git_service.has_uncommitted_changes(mock_repo_path)
            assert result is True

    async def test_has_uncommitted_changes_false(self, git_service, mock_repo_path):
        """Test checking for uncommitted changes (false case)."""
        with patch.object(git_service, "get_status_porcelain", return_value=[]):
            result = await git_service.has_uncommitted_changes(mock_repo_path)
            assert result is False

    async def test_add_all(self, git_service, mock_repo_path):
        """Test adding all changes."""
        with patch.object(git_service, "run_command", return_value=(0, "", "")):
            success, error = await git_service.add_all(mock_repo_path)
            assert success is True
            assert error == ""

    async def test_commit(self, git_service, mock_repo_path):
        """Test committing changes."""
        with patch.object(git_service, "run_command", return_value=(0, "", "")):
            success, error = await git_service.commit(mock_repo_path, "Test commit")
            assert success is True
            assert error == ""

    async def test_push_success(self, git_service, mock_repo_path):
        """Test successful push."""
        with patch.object(git_service, "run_command", return_value=(0, "", "")):
            success, error = await git_service.push(
                mock_repo_path, "main", max_retries=1
            )
            assert success is True
            assert error == ""

    async def test_pull_success(self, git_service, mock_repo_path):
        """Test successful pull."""
        with patch.object(git_service, "run_command", return_value=(0, "", "")):
            success, error, has_conflict = await git_service.pull(
                mock_repo_path, "main", max_retries=1
            )
            assert success is True
            assert error == ""
            assert has_conflict is False

    async def test_pull_with_conflict(self, git_service, mock_repo_path):
        """Test pull with merge conflict."""
        with patch.object(
            git_service, "run_command", return_value=(1, "CONFLICT (content)", "")
        ):
            success, error, has_conflict = await git_service.pull(
                mock_repo_path, "main", max_retries=1
            )
            assert success is False
            assert has_conflict is True

    async def test_checkout(self, git_service, mock_repo_path):
        """Test checkout branch."""
        with patch.object(git_service, "run_command", return_value=(0, "", "")):
            success, error = await git_service.checkout(mock_repo_path, "main")
            assert success is True
            assert error == ""

    async def test_delete_local_branch(self, git_service, mock_repo_path):
        """Test deleting local branch."""
        with patch.object(git_service, "run_command", return_value=(0, "", "")):
            success, error = await git_service.delete_local_branch(
                mock_repo_path, "feature-branch"
            )
            assert success is True
            assert error == ""

    async def test_delete_remote_branch(self, git_service, mock_repo_path):
        """Test deleting remote branch."""
        with patch.object(git_service, "run_command", return_value=(0, "", "")):
            success, error = await git_service.delete_remote_branch(
                mock_repo_path, "feature-branch"
            )
            assert success is True
            assert error == ""

    async def test_get_main_branch_main_exists(self, git_service, mock_repo_path):
        """Test getting main branch when 'main' exists."""
        with patch.object(git_service, "run_command") as mock_run:
            # First call returns empty (symbolic-ref fails), second call succeeds (main exists)
            mock_run.side_effect = [(1, "", ""), (0, "", "")]
            branch = await git_service.get_main_branch(mock_repo_path)
            assert branch == "main"

    async def test_get_local_branches(self, git_service, mock_repo_path):
        """Test getting local branches."""
        branches = "main\nfeature-1\nfeature-2"
        with patch.object(git_service, "run_command", return_value=(0, branches, "")):
            result = await git_service.get_local_branches(mock_repo_path)
            assert result == ["main", "feature-1", "feature-2"]

    async def test_commits_behind_remote(self, git_service, mock_repo_path):
        """Test getting number of commits behind remote."""
        with patch.object(git_service, "run_command") as mock_run:
            # First call checks if remote exists (success), second returns count
            mock_run.side_effect = [(0, "", ""), (0, "3", "")]
            count = await git_service.commits_behind_remote(mock_repo_path, "main")
            assert count == 3

    async def test_get_merged_branches(self, git_service, mock_repo_path):
        """Test getting merged branches."""
        local_merged = "  feature-1\n* main\n  feature-2"
        remote_merged = "  origin/feature-3\n  origin/main\n  origin/feature-4"

        with patch.object(git_service, "run_command") as mock_run:
            mock_run.side_effect = [(0, local_merged, ""), (0, remote_merged, "")]
            branches = await git_service.get_merged_branches(
                mock_repo_path, "origin/main", include_remote=True
            )

            # Should exclude 'main' and 'origin/main'
            assert "main" not in branches
            assert "feature-1" in branches
            assert "feature-2" in branches
            assert "origin/feature-3" in branches
            assert "origin/feature-4" in branches
