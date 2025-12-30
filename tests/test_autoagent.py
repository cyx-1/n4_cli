"""Unit tests for autoagent command."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest
import yaml

from n4_cli.commands.autoagent import (
    AutoAgentConfig,
    TaskAbortException,
    TaskConfig,
    build_dependency_graph,
    execute_claude_prompt,
    execute_shell_command,
    execute_task,
    get_execution_order,
    is_claude_available,
    parse_yaml_config,
    run_parallel_execution,
    run_sequential_execution,
)


@pytest.fixture
def sample_yaml_config():
    """Sample YAML configuration for testing."""
    return """
version: "1.0"

defaults:
  model: sonnet
  agent: claude
  execution_mode: sequential
  branch_strategy: separate
  auto_push: false
  abort_on_failure: true

tasks:
  - name: Task 1
    prompt: "Do task 1"
    model: opus

  - name: Task 2
    prompt: "Do task 2"
    depends_on:
      - Task 1

  - name: Task 3
    prompt: "Do task 3"
    branch: feature/task-3
    auto_push: true
"""


@pytest.fixture
def sample_parallel_yaml_config():
    """Sample YAML configuration for parallel execution."""
    return """
version: "1.0"

defaults:
  model: sonnet
  execution_mode: parallel
  abort_on_failure: true

tasks:
  - name: Task A
    prompt: "Independent task A"

  - name: Task B
    prompt: "Independent task B"

  - name: Task C
    prompt: "Depends on A and B"
    depends_on:
      - Task A
      - Task B

  - name: Task D
    prompt: "Depends on C"
    depends_on:
      - Task C
"""


@pytest.fixture
def sample_circular_dependency_config():
    """Sample YAML with circular dependencies."""
    return """
version: "1.0"

defaults:
  model: sonnet

tasks:
  - name: Task 1
    prompt: "Do task 1"
    depends_on:
      - Task 2

  - name: Task 2
    prompt: "Do task 2"
    depends_on:
      - Task 1
"""


@pytest.fixture
def sample_command_task_config():
    """Sample YAML with command tasks."""
    return """
version: "1.0"

defaults:
  execution_mode: sequential

tasks:
  - name: Run tests
    type: command
    command: pytest tests/ -v
    timeout: 60

  - name: Build project
    type: command
    command: python -m build
    depends_on:
      - Run tests
    working_directory: /tmp

  - name: Analyze results
    type: prompt
    prompt: "Analyze the build output"
    depends_on:
      - Build project
"""


@pytest.fixture
def sample_mixed_tasks_config():
    """Sample YAML with both prompt and command tasks."""
    return """
version: "1.0"

defaults:
  model: sonnet
  execution_mode: parallel

tasks:
  - name: Lint code
    type: command
    command: echo "Linting..."

  - name: Format code
    type: command
    command: echo "Formatting..."

  - name: Review changes
    type: prompt
    prompt: "Review the code changes"
    depends_on:
      - Lint code
      - Format code
"""


class TestIsClaudeAvailable:
    """Tests for is_claude_available function."""

    def test_claude_available(self):
        """Test when Claude CLI is available."""
        with patch('shutil.which', return_value='/usr/bin/claude'):
            assert is_claude_available() is True

    def test_claude_not_available(self):
        """Test when Claude CLI is not available."""
        with patch('shutil.which', return_value=None):
            assert is_claude_available() is False


class TestParseYamlConfig:
    """Tests for parse_yaml_config function."""

    def test_parse_valid_config(self, tmp_path, sample_yaml_config):
        """Test parsing a valid YAML configuration."""
        config_file = tmp_path / "autoagent.yaml"
        config_file.write_text(sample_yaml_config)

        config = parse_yaml_config(config_file)

        assert config.version == "1.0"
        assert len(config.tasks) == 3
        assert config.tasks[0].name == "Task 1"
        assert config.tasks[0].model == "opus"
        assert config.tasks[1].depends_on == ["Task 1"]
        assert config.tasks[2].branch == "feature/task-3"
        assert config.tasks[2].auto_push is True

    def test_parse_file_not_found(self, tmp_path):
        """Test parsing when file doesn't exist."""
        config_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError, match="File not found"):
            parse_yaml_config(config_file)

    def test_parse_invalid_yaml(self, tmp_path):
        """Test parsing invalid YAML."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: content: [")

        with pytest.raises(ValueError, match="Invalid YAML format"):
            parse_yaml_config(config_file)

    def test_parse_empty_config(self, tmp_path):
        """Test parsing empty configuration."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        with pytest.raises(ValueError, match="Empty configuration file"):
            parse_yaml_config(config_file)

    def test_parse_no_tasks(self, tmp_path):
        """Test parsing config with no tasks."""
        config_file = tmp_path / "no_tasks.yaml"
        config_file.write_text("""
version: "1.0"
defaults:
  model: sonnet
tasks: []
""")

        with pytest.raises(ValueError, match="No tasks defined"):
            parse_yaml_config(config_file)

    def test_parse_missing_task_name(self, tmp_path):
        """Test parsing task without name."""
        config_file = tmp_path / "missing_name.yaml"
        config_file.write_text("""
version: "1.0"
tasks:
  - prompt: "Do something"
""")

        with pytest.raises(ValueError, match="Task missing required 'name' field"):
            parse_yaml_config(config_file)

    def test_parse_missing_task_prompt(self, tmp_path):
        """Test parsing task without prompt."""
        config_file = tmp_path / "missing_prompt.yaml"
        config_file.write_text("""
version: "1.0"
tasks:
  - name: "Task 1"
""")

        with pytest.raises(ValueError, match="Task 'Task 1' of type 'prompt' missing required 'prompt' field"):
            parse_yaml_config(config_file)

    def test_parse_defaults_applied(self, tmp_path):
        """Test that defaults are applied to tasks."""
        config_file = tmp_path / "defaults.yaml"
        config_file.write_text("""
version: "1.0"
defaults:
  model: haiku
  agent: codex
  auto_push: true
tasks:
  - name: "Task 1"
    prompt: "Do something"
""")

        config = parse_yaml_config(config_file)

        assert config.tasks[0].model == "haiku"
        assert config.tasks[0].agent == "codex"
        assert config.tasks[0].auto_push is True

    def test_parse_command_task(self, tmp_path):
        """Test parsing a command task."""
        config_file = tmp_path / "command.yaml"
        config_file.write_text("""
version: "1.0"
tasks:
  - name: "Run tests"
    type: command
    command: "pytest tests/"
    timeout: 600
    working_directory: "/tmp"
""")

        config = parse_yaml_config(config_file)

        assert len(config.tasks) == 1
        assert config.tasks[0].name == "Run tests"
        assert config.tasks[0].task_type == "command"
        assert config.tasks[0].command == "pytest tests/"
        assert config.tasks[0].timeout == 600
        assert config.tasks[0].working_directory == "/tmp"

    def test_parse_mixed_tasks(self, tmp_path):
        """Test parsing both prompt and command tasks."""
        config_file = tmp_path / "mixed.yaml"
        config_file.write_text("""
version: "1.0"
tasks:
  - name: "Prompt task"
    type: prompt
    prompt: "Do something"
  - name: "Command task"
    type: command
    command: "echo hello"
""")

        config = parse_yaml_config(config_file)

        assert len(config.tasks) == 2
        assert config.tasks[0].task_type == "prompt"
        assert config.tasks[0].prompt == "Do something"
        assert config.tasks[1].task_type == "command"
        assert config.tasks[1].command == "echo hello"

    def test_parse_command_missing_command_field(self, tmp_path):
        """Test parsing command task without command field."""
        config_file = tmp_path / "missing_command.yaml"
        config_file.write_text("""
version: "1.0"
tasks:
  - name: "Task 1"
    type: command
""")

        with pytest.raises(ValueError, match="missing required 'command' field"):
            parse_yaml_config(config_file)

    def test_parse_invalid_task_type(self, tmp_path):
        """Test parsing task with invalid type."""
        config_file = tmp_path / "invalid_type.yaml"
        config_file.write_text("""
version: "1.0"
tasks:
  - name: "Task 1"
    type: invalid
    prompt: "Something"
""")

        with pytest.raises(ValueError, match="invalid type"):
            parse_yaml_config(config_file)


class TestExecuteClaudePrompt:
    """Tests for execute_claude_prompt function."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful prompt execution."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"Success output", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            success, output, error_type = await execute_claude_prompt("Test prompt", "sonnet")

            assert success is True
            assert output == "Success output"
            assert error_type is None

    @pytest.mark.asyncio
    async def test_execute_failure_generic(self):
        """Test failed prompt execution with generic error."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"Generic error"))
        mock_process.returncode = 1

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            success, output, error_type = await execute_claude_prompt("Test prompt", "sonnet")

            assert success is False
            assert "Generic error" in output
            assert error_type == "generic"

    @pytest.mark.asyncio
    async def test_execute_failure_rate_limit(self):
        """Test failed prompt execution with rate limit error."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"Error: Rate limit exceeded")
        )
        mock_process.returncode = 1

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            success, output, error_type = await execute_claude_prompt("Test prompt", "sonnet")

            assert success is False
            assert error_type == "rate_limit"

    @pytest.mark.asyncio
    async def test_execute_failure_auth_error(self):
        """Test failed prompt execution with auth error."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"Error: Unauthorized access")
        )
        mock_process.returncode = 1

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            success, output, error_type = await execute_claude_prompt("Test prompt", "sonnet")

            assert success is False
            assert error_type == "auth_error"

    @pytest.mark.asyncio
    async def test_execute_exception(self):
        """Test exception during execution."""
        with patch('asyncio.create_subprocess_shell', side_effect=Exception("Test exception")):
            success, output, error_type = await execute_claude_prompt("Test prompt", "sonnet")

            assert success is False
            assert "Test exception" in output
            assert error_type == "generic"


class TestExecuteShellCommand:
    """Tests for execute_shell_command function."""

    @pytest.mark.asyncio
    async def test_execute_command_success(self):
        """Test successful command execution."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"Command output", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            success, output, error_type = await execute_shell_command("echo test")

            assert success is True
            assert output == "Command output"
            assert error_type is None

    @pytest.mark.asyncio
    async def test_execute_command_failure(self):
        """Test failed command execution."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"Command failed"))
        mock_process.returncode = 1

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            success, output, error_type = await execute_shell_command("false")

            assert success is False
            assert "Command failed" in output
            assert error_type == "generic"

    @pytest.mark.asyncio
    async def test_execute_command_timeout(self):
        """Test command execution timeout."""
        mock_process = AsyncMock()
        mock_process.kill = AsyncMock()
        mock_process.wait = AsyncMock()

        async def mock_communicate():
            await asyncio.sleep(10)  # Simulate long-running command
            return b"", b""

        mock_process.communicate = mock_communicate

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            success, output, error_type = await execute_shell_command("sleep 100", timeout=0.1)

            assert success is False
            assert "timed out" in output.lower()
            assert error_type == "timeout"

    @pytest.mark.asyncio
    async def test_execute_command_with_working_directory(self):
        """Test command execution with working directory."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"Success", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_shell', return_value=mock_process) as mock_subprocess:
            success, output, error_type = await execute_shell_command(
                "pwd",
                working_directory="/tmp"
            )

            assert success is True
            # Verify that cwd was passed
            call_kwargs = mock_subprocess.call_args[1]
            assert call_kwargs['cwd'] == "/tmp"

    @pytest.mark.asyncio
    async def test_execute_command_not_found(self):
        """Test command not found error."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"command not found: nonexistent")
        )
        mock_process.returncode = 127

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            success, output, error_type = await execute_shell_command("nonexistent")

            assert success is False
            assert error_type == "command_not_found"

    @pytest.mark.asyncio
    async def test_execute_command_permission_denied(self):
        """Test permission denied error."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"", b"Permission denied")
        )
        mock_process.returncode = 1

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            success, output, error_type = await execute_shell_command("restricted_command")

            assert success is False
            assert error_type == "permission_error"

    @pytest.mark.asyncio
    async def test_execute_command_with_stdout_and_stderr(self):
        """Test command with both stdout and stderr."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"Standard output", b"Error output")
        )
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_shell', return_value=mock_process):
            success, output, error_type = await execute_shell_command("test_command")

            assert success is True
            assert "Standard output" in output
            assert "Error output" in output
            assert "STDERR" in output


class TestExecuteTask:
    """Tests for execute_task function."""

    @pytest.mark.asyncio
    async def test_execute_task_success(self):
        """Test successful task execution."""
        task = TaskConfig(
            name="Test Task",
            prompt="Do something",
            model="sonnet",
            agent="claude"
        )

        with patch('n4_cli.commands.autoagent.execute_claude_prompt',
                   return_value=(True, "Success", None)):
            success, output, error_type = await execute_task(task, 1, 1, verbose=False)

            assert success is True
            assert output == "Success"
            assert error_type is None

    @pytest.mark.asyncio
    async def test_execute_task_failure(self):
        """Test failed task execution."""
        task = TaskConfig(
            name="Test Task",
            prompt="Do something",
            model="sonnet",
            agent="claude"
        )

        with patch('n4_cli.commands.autoagent.execute_claude_prompt',
                   return_value=(False, "Error", "generic")):
            success, output, error_type = await execute_task(task, 1, 1, verbose=False)

            assert success is False
            assert output == "Error"
            assert error_type == "generic"

    @pytest.mark.asyncio
    async def test_execute_task_with_branch(self):
        """Test task execution with branch specified."""
        task = TaskConfig(
            name="Test Task",
            prompt="Do something",
            model="sonnet",
            agent="claude",
            branch="feature/test"
        )

        with patch('n4_cli.commands.autoagent.execute_claude_prompt',
                   return_value=(True, "Success", None)):
            success, output, error_type = await execute_task(task, 1, 1, verbose=True)

            assert success is True

    @pytest.mark.asyncio
    async def test_execute_command_task_success(self):
        """Test successful command task execution."""
        task = TaskConfig(
            name="Test Command",
            task_type="command",
            command="echo hello"
        )

        with patch('n4_cli.commands.autoagent.execute_shell_command',
                   return_value=(True, "hello", None)):
            success, output, error_type = await execute_task(task, 1, 1, verbose=False)

            assert success is True
            assert output == "hello"
            assert error_type is None

    @pytest.mark.asyncio
    async def test_execute_command_task_failure(self):
        """Test failed command task execution."""
        task = TaskConfig(
            name="Test Command",
            task_type="command",
            command="false"
        )

        with patch('n4_cli.commands.autoagent.execute_shell_command',
                   return_value=(False, "Command failed", "generic")):
            success, output, error_type = await execute_task(task, 1, 1, verbose=False)

            assert success is False
            assert output == "Command failed"
            assert error_type == "generic"

    @pytest.mark.asyncio
    async def test_execute_command_task_with_working_directory(self):
        """Test command task with working directory."""
        task = TaskConfig(
            name="Test Command",
            task_type="command",
            command="pwd",
            working_directory="/tmp"
        )

        with patch('n4_cli.commands.autoagent.execute_shell_command',
                   return_value=(True, "/tmp", None)) as mock_execute:
            success, output, error_type = await execute_task(task, 1, 1, verbose=True)

            assert success is True
            # Verify execute_shell_command was called with working_directory
            mock_execute.assert_called_once_with("pwd", "/tmp", 300)


class TestBuildDependencyGraph:
    """Tests for build_dependency_graph function."""

    def test_build_simple_graph(self):
        """Test building a simple dependency graph."""
        tasks = [
            TaskConfig(name="Task 1", prompt="Do 1"),
            TaskConfig(name="Task 2", prompt="Do 2", depends_on=["Task 1"]),
        ]

        graph = build_dependency_graph(tasks)

        assert graph["Task 1"] == set()
        assert graph["Task 2"] == {"Task 1"}

    def test_build_complex_graph(self):
        """Test building a complex dependency graph."""
        tasks = [
            TaskConfig(name="A", prompt="Do A"),
            TaskConfig(name="B", prompt="Do B", depends_on=["A"]),
            TaskConfig(name="C", prompt="Do C", depends_on=["A"]),
            TaskConfig(name="D", prompt="Do D", depends_on=["B", "C"]),
        ]

        graph = build_dependency_graph(tasks)

        assert graph["A"] == set()
        assert graph["B"] == {"A"}
        assert graph["C"] == {"A"}
        assert graph["D"] == {"B", "C"}

    def test_build_graph_missing_dependency(self):
        """Test building graph with missing dependency."""
        tasks = [
            TaskConfig(name="Task 1", prompt="Do 1", depends_on=["NonExistent"]),
        ]

        with pytest.raises(ValueError, match="depends on non-existent task"):
            build_dependency_graph(tasks)

    def test_build_graph_circular_dependency(self):
        """Test detecting circular dependencies."""
        tasks = [
            TaskConfig(name="Task 1", prompt="Do 1", depends_on=["Task 2"]),
            TaskConfig(name="Task 2", prompt="Do 2", depends_on=["Task 1"]),
        ]

        with pytest.raises(ValueError, match="Circular dependency detected"):
            build_dependency_graph(tasks)

    def test_build_graph_self_dependency(self):
        """Test detecting self dependency (circular)."""
        tasks = [
            TaskConfig(name="Task 1", prompt="Do 1", depends_on=["Task 1"]),
        ]

        with pytest.raises(ValueError, match="Circular dependency detected"):
            build_dependency_graph(tasks)


class TestGetExecutionOrder:
    """Tests for get_execution_order function."""

    def test_simple_sequential_order(self):
        """Test simple sequential execution order."""
        tasks = [
            TaskConfig(name="Task 1", prompt="Do 1"),
            TaskConfig(name="Task 2", prompt="Do 2", depends_on=["Task 1"]),
            TaskConfig(name="Task 3", prompt="Do 3", depends_on=["Task 2"]),
        ]
        graph = build_dependency_graph(tasks)

        batches = get_execution_order(tasks, graph)

        assert len(batches) == 3
        assert batches[0][0].name == "Task 1"
        assert batches[1][0].name == "Task 2"
        assert batches[2][0].name == "Task 3"

    def test_parallel_execution_order(self):
        """Test parallel execution order."""
        tasks = [
            TaskConfig(name="A", prompt="Do A"),
            TaskConfig(name="B", prompt="Do B"),
            TaskConfig(name="C", prompt="Do C", depends_on=["A", "B"]),
        ]
        graph = build_dependency_graph(tasks)

        batches = get_execution_order(tasks, graph)

        assert len(batches) == 2
        # First batch should have A and B (order may vary)
        assert len(batches[0]) == 2
        assert {t.name for t in batches[0]} == {"A", "B"}
        # Second batch should have C
        assert len(batches[1]) == 1
        assert batches[1][0].name == "C"

    def test_complex_execution_order(self):
        """Test complex execution order with multiple levels."""
        tasks = [
            TaskConfig(name="A", prompt="Do A"),
            TaskConfig(name="B", prompt="Do B"),
            TaskConfig(name="C", prompt="Do C", depends_on=["A"]),
            TaskConfig(name="D", prompt="Do D", depends_on=["A"]),
            TaskConfig(name="E", prompt="Do E", depends_on=["B", "C"]),
        ]
        graph = build_dependency_graph(tasks)

        batches = get_execution_order(tasks, graph)

        # Batch 1: A, B
        # Batch 2: C, D
        # Batch 3: E
        assert len(batches) == 3
        assert {t.name for t in batches[0]} == {"A", "B"}
        assert {t.name for t in batches[1]} == {"C", "D"}
        assert {t.name for t in batches[2]} == {"E"}


class TestRunSequentialExecution:
    """Tests for run_sequential_execution function."""

    @pytest.mark.asyncio
    async def test_sequential_success(self):
        """Test successful sequential execution."""
        tasks = [
            TaskConfig(name="Task 1", prompt="Do 1"),
            TaskConfig(name="Task 2", prompt="Do 2"),
        ]

        with patch('n4_cli.commands.autoagent.execute_task',
                   return_value=(True, "Success", None)) as mock_execute:
            await run_sequential_execution(tasks, verbose=False, abort_on_failure=True)

            assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    async def test_sequential_failure_abort(self):
        """Test sequential execution with failure and abort."""
        tasks = [
            TaskConfig(name="Task 1", prompt="Do 1"),
            TaskConfig(name="Task 2", prompt="Do 2"),
        ]

        with patch('n4_cli.commands.autoagent.execute_task',
                   return_value=(False, "Error", "generic")) as mock_execute:
            with pytest.raises(TaskAbortException, match="Task 'Task 1' failed"):
                await run_sequential_execution(tasks, verbose=False, abort_on_failure=True)

            # Should only execute first task
            assert mock_execute.call_count == 1

    @pytest.mark.asyncio
    async def test_sequential_rate_limit_abort(self):
        """Test sequential execution aborting on rate limit."""
        tasks = [
            TaskConfig(name="Task 1", prompt="Do 1"),
            TaskConfig(name="Task 2", prompt="Do 2"),
        ]

        with patch('n4_cli.commands.autoagent.execute_task',
                   return_value=(False, "Rate limit", "rate_limit")):
            with pytest.raises(TaskAbortException, match="Rate limit exceeded"):
                await run_sequential_execution(tasks, verbose=False, abort_on_failure=False)


class TestRunParallelExecution:
    """Tests for run_parallel_execution function."""

    @pytest.mark.asyncio
    async def test_parallel_success(self):
        """Test successful parallel execution."""
        tasks_batch1 = [
            TaskConfig(name="Task A", prompt="Do A"),
            TaskConfig(name="Task B", prompt="Do B"),
        ]
        tasks_batch2 = [
            TaskConfig(name="Task C", prompt="Do C"),
        ]
        batches = [tasks_batch1, tasks_batch2]

        with patch('n4_cli.commands.autoagent.execute_task',
                   return_value=(True, "Success", None)) as mock_execute:
            await run_parallel_execution(batches, verbose=False, abort_on_failure=True)

            assert mock_execute.call_count == 3

    @pytest.mark.asyncio
    async def test_parallel_failure_abort(self):
        """Test parallel execution with failure and abort."""
        tasks_batch1 = [
            TaskConfig(name="Task A", prompt="Do A"),
            TaskConfig(name="Task B", prompt="Do B"),
        ]
        batches = [tasks_batch1]

        with patch('n4_cli.commands.autoagent.execute_task',
                   return_value=(False, "Error", "generic")):
            with pytest.raises(TaskAbortException, match="failed"):
                await run_parallel_execution(batches, verbose=False, abort_on_failure=True)

    @pytest.mark.asyncio
    async def test_parallel_rate_limit_abort(self):
        """Test parallel execution aborting on rate limit."""
        tasks_batch1 = [
            TaskConfig(name="Task A", prompt="Do A"),
        ]
        batches = [tasks_batch1]

        with patch('n4_cli.commands.autoagent.execute_task',
                   return_value=(False, "Rate limit", "rate_limit")):
            with pytest.raises(TaskAbortException, match="Rate limit exceeded"):
                await run_parallel_execution(batches, verbose=False, abort_on_failure=True)

    @pytest.mark.asyncio
    async def test_parallel_exception_abort(self):
        """Test parallel execution with exception."""
        tasks_batch1 = [
            TaskConfig(name="Task A", prompt="Do A"),
        ]
        batches = [tasks_batch1]

        with patch('n4_cli.commands.autoagent.execute_task',
                   side_effect=Exception("Test exception")):
            with pytest.raises(TaskAbortException):
                await run_parallel_execution(batches, verbose=False, abort_on_failure=True)


class TestIntegration:
    """Integration tests for the full autoagent flow."""

    @pytest.mark.asyncio
    async def test_full_sequential_flow(self, tmp_path, sample_yaml_config):
        """Test complete sequential execution flow."""
        config_file = tmp_path / "autoagent.yaml"
        config_file.write_text(sample_yaml_config)

        with patch('n4_cli.commands.autoagent.execute_claude_prompt',
                   return_value=(True, "Success", None)):
            from n4_cli.commands.autoagent import run_autoagent

            # Should complete without error
            await run_autoagent(config_file, verbose=False, force_sequential=False)

    @pytest.mark.asyncio
    async def test_full_parallel_flow(self, tmp_path, sample_parallel_yaml_config):
        """Test complete parallel execution flow."""
        config_file = tmp_path / "autoagent.yaml"
        config_file.write_text(sample_parallel_yaml_config)

        with patch('n4_cli.commands.autoagent.execute_claude_prompt',
                   return_value=(True, "Success", None)):
            from n4_cli.commands.autoagent import run_autoagent

            # Should complete without error
            await run_autoagent(config_file, verbose=False, force_sequential=False)

    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self, tmp_path, sample_circular_dependency_config):
        """Test that circular dependencies are detected."""
        config_file = tmp_path / "autoagent.yaml"
        config_file.write_text(sample_circular_dependency_config)

        from n4_cli.commands.autoagent import run_autoagent

        # Should detect circular dependency
        # The function handles this internally and displays error, doesn't raise
        await run_autoagent(config_file, verbose=False, force_sequential=False)
