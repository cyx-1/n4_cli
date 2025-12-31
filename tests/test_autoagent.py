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
    run_step_execution,
)


@pytest.fixture
def sample_yaml_config():
    """Sample YAML configuration for testing."""
    return """
version: "1.0"

defaults:
  model: sonnet
  agent: claude
  branch_strategy: separate
  auto_push: false
  abort_on_failure: true

tasks:
  - name: Task 1
    prompt: "Do task 1"
    model: opus
    execution_step: 1

  - name: Task 2
    prompt: "Do task 2"
    execution_step: 2

  - name: Task 3
    prompt: "Do task 3"
    branch: feature/task-3
    auto_push: true
    execution_step: 3
"""


@pytest.fixture
def sample_step_yaml_config():
    """Sample YAML configuration for step-based execution."""
    return """
version: "1.0"

defaults:
  model: sonnet
  abort_on_failure: true

tasks:
  - name: Task A
    prompt: "Step 1 task A"
    execution_step: 1

  - name: Task B
    prompt: "Step 1 task B"
    execution_step: 1

  - name: Task C
    prompt: "Step 2 task"
    execution_step: 2

  - name: Task D
    prompt: "Step 3 task"
    execution_step: 3
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
  abort_on_failure: true

tasks:
  - name: Run tests
    type: command
    command: pytest tests/ -v
    timeout: 60
    execution_step: 1

  - name: Build project
    type: command
    command: python -m build
    working_directory: /tmp
    execution_step: 2

  - name: Analyze results
    type: prompt
    prompt: "Analyze the build output"
    execution_step: 3
"""


@pytest.fixture
def sample_mixed_tasks_config():
    """Sample YAML with both prompt and command tasks."""
    return """
version: "1.0"

defaults:
  model: sonnet
  abort_on_failure: true

tasks:
  - name: Lint code
    type: command
    command: echo "Linting..."
    execution_step: 1

  - name: Format code
    type: command
    command: echo "Formatting..."
    execution_step: 1

  - name: Review changes
    type: prompt
    prompt: "Review the code changes"
    execution_step: 2
"""


@pytest.fixture
def sample_goto_task_config():
    """Sample YAML with goto tasks."""
    return """
version: "1.0"

defaults:
  abort_on_failure: true

tasks:
  - name: Initial task
    type: command
    command: echo "Step 1"
    execution_step: 1

  - name: Process data
    type: command
    command: echo "Step 2"
    execution_step: 2

  - name: Jump to step 1
    type: goto
    goto_step: 1
    execution_step: 3
"""


@pytest.fixture
def sample_goto_forward_config():
    """Sample YAML with goto task that jumps forward."""
    return """
version: "1.0"

defaults:
  abort_on_failure: true

tasks:
  - name: Task A
    type: command
    command: echo "A"
    execution_step: 1

  - name: Skip to end
    type: goto
    goto_step: 4
    execution_step: 2

  - name: Task B (skipped)
    type: command
    command: echo "B"
    execution_step: 3

  - name: Final task
    type: command
    command: echo "Final"
    execution_step: 4
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
        assert config.tasks[0].execution_step == 1
        assert config.tasks[1].execution_step == 2
        assert config.tasks[2].branch == "feature/task-3"
        assert config.tasks[2].auto_push is True
        assert config.tasks[2].execution_step == 3

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

    def test_parse_goto_task(self, tmp_path):
        """Test parsing a goto task."""
        config_file = tmp_path / "goto.yaml"
        config_file.write_text("""
version: "1.0"
tasks:
  - name: "Jump to step 5"
    type: goto
    goto_step: 5
    execution_step: 2
""")

        config = parse_yaml_config(config_file)

        assert len(config.tasks) == 1
        assert config.tasks[0].name == "Jump to step 5"
        assert config.tasks[0].task_type == "goto"
        assert config.tasks[0].goto_step == 5
        assert config.tasks[0].execution_step == 2

    def test_parse_goto_missing_goto_step(self, tmp_path):
        """Test parsing goto task without goto_step field."""
        config_file = tmp_path / "missing_goto_step.yaml"
        config_file.write_text("""
version: "1.0"
tasks:
  - name: "Invalid goto"
    type: goto
""")

        with pytest.raises(ValueError, match="missing required 'goto_step' field"):
            parse_yaml_config(config_file)

    def test_parse_goto_invalid_goto_step_type(self, tmp_path):
        """Test parsing goto task with non-integer goto_step."""
        config_file = tmp_path / "invalid_goto_step.yaml"
        config_file.write_text("""
version: "1.0"
tasks:
  - name: "Invalid goto"
    type: goto
    goto_step: "not_a_number"
""")

        with pytest.raises(ValueError, match="invalid 'goto_step' value"):
            parse_yaml_config(config_file)

    def test_parse_mixed_with_goto(self, tmp_path):
        """Test parsing config with prompt, command, and goto tasks."""
        config_file = tmp_path / "mixed_with_goto.yaml"
        config_file.write_text("""
version: "1.0"
tasks:
  - name: "Prompt task"
    type: prompt
    prompt: "Do something"
    execution_step: 1
  - name: "Command task"
    type: command
    command: "echo hello"
    execution_step: 2
  - name: "Goto task"
    type: goto
    goto_step: 1
    execution_step: 3
""")

        config = parse_yaml_config(config_file)

        assert len(config.tasks) == 3
        assert config.tasks[0].task_type == "prompt"
        assert config.tasks[1].task_type == "command"
        assert config.tasks[2].task_type == "goto"
        assert config.tasks[2].goto_step == 1


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

    @pytest.mark.asyncio
    async def test_execute_goto_task(self):
        """Test goto task execution."""
        task = TaskConfig(
            name="Jump to step 3",
            task_type="goto",
            goto_step=3,
            execution_step=1
        )

        success, output, error_type = await execute_task(task, 1, 1, verbose=False)

        assert success is True
        assert output == "3"  # The goto_step as string
        assert error_type == "goto"  # Special error_type indicating a goto

    @pytest.mark.asyncio
    async def test_execute_goto_task_verbose(self):
        """Test goto task execution with verbose output."""
        task = TaskConfig(
            name="Jump to step 5",
            task_type="goto",
            goto_step=5,
            execution_step=2
        )

        success, output, error_type = await execute_task(task, 1, 1, verbose=True)

        assert success is True
        assert output == "5"
        assert error_type == "goto"


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

    def test_simple_step_order(self):
        """Test simple step-based execution order."""
        tasks = [
            TaskConfig(name="Task 1", prompt="Do 1", execution_step=1),
            TaskConfig(name="Task 2", prompt="Do 2", execution_step=2),
            TaskConfig(name="Task 3", prompt="Do 3", execution_step=3),
        ]
        graph = build_dependency_graph(tasks)

        batches = get_execution_order(tasks, graph)

        assert len(batches) == 3
        assert batches[0][0].name == "Task 1"
        assert batches[1][0].name == "Task 2"
        assert batches[2][0].name == "Task 3"

    def test_parallel_step_execution(self):
        """Test tasks with same step run in parallel."""
        tasks = [
            TaskConfig(name="A", prompt="Do A", execution_step=1),
            TaskConfig(name="B", prompt="Do B", execution_step=1),
            TaskConfig(name="C", prompt="Do C", execution_step=2),
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

    def test_complex_step_order(self):
        """Test complex execution order with multiple steps."""
        tasks = [
            TaskConfig(name="A", prompt="Do A", execution_step=1),
            TaskConfig(name="B", prompt="Do B", execution_step=1),
            TaskConfig(name="C", prompt="Do C", execution_step=2),
            TaskConfig(name="D", prompt="Do D", execution_step=2),
            TaskConfig(name="E", prompt="Do E", execution_step=3),
        ]
        graph = build_dependency_graph(tasks)

        batches = get_execution_order(tasks, graph)

        # Step 1: A, B
        # Step 2: C, D
        # Step 3: E
        assert len(batches) == 3
        assert {t.name for t in batches[0]} == {"A", "B"}
        assert {t.name for t in batches[1]} == {"C", "D"}
        assert {t.name for t in batches[2]} == {"E"}

    def test_non_sequential_step_numbers(self):
        """Test that steps with gaps are handled correctly."""
        tasks = [
            TaskConfig(name="A", prompt="Do A", execution_step=1),
            TaskConfig(name="B", prompt="Do B", execution_step=5),
            TaskConfig(name="C", prompt="Do C", execution_step=10),
        ]
        graph = build_dependency_graph(tasks)

        batches = get_execution_order(tasks, graph)

        # Should still produce 3 batches in order
        assert len(batches) == 3
        assert batches[0][0].name == "A"
        assert batches[1][0].name == "B"
        assert batches[2][0].name == "C"

    def test_default_step_is_1(self):
        """Test that tasks without execution_step default to step 1."""
        tasks = [
            TaskConfig(name="A", prompt="Do A"),  # defaults to step 1
            TaskConfig(name="B", prompt="Do B"),  # defaults to step 1
        ]
        graph = build_dependency_graph(tasks)

        batches = get_execution_order(tasks, graph)

        # Both tasks should be in the same batch (step 1)
        assert len(batches) == 1
        assert len(batches[0]) == 2
        assert {t.name for t in batches[0]} == {"A", "B"}


class TestRunStepExecution:
    """Tests for run_step_execution function."""

    @pytest.mark.asyncio
    async def test_step_execution_success(self):
        """Test successful step-based execution."""
        tasks_step1 = [
            TaskConfig(name="Task A", prompt="Do A", execution_step=1),
            TaskConfig(name="Task B", prompt="Do B", execution_step=1),
        ]
        tasks_step2 = [
            TaskConfig(name="Task C", prompt="Do C", execution_step=2),
        ]
        batches = [tasks_step1, tasks_step2]

        with patch('n4_cli.commands.autoagent.execute_task',
                   return_value=(True, "Success", None)) as mock_execute:
            await run_step_execution(batches, verbose=False, abort_on_failure=True)

            assert mock_execute.call_count == 3

    @pytest.mark.asyncio
    async def test_step_execution_failure_abort(self):
        """Test step execution with failure and abort."""
        tasks_step1 = [
            TaskConfig(name="Task A", prompt="Do A", execution_step=1),
            TaskConfig(name="Task B", prompt="Do B", execution_step=1),
        ]
        batches = [tasks_step1]

        with patch('n4_cli.commands.autoagent.execute_task',
                   return_value=(False, "Error", "generic")):
            with pytest.raises(TaskAbortException, match="failed"):
                await run_step_execution(batches, verbose=False, abort_on_failure=True)

    @pytest.mark.asyncio
    async def test_step_execution_rate_limit_abort(self):
        """Test step execution aborting on rate limit."""
        tasks_step1 = [
            TaskConfig(name="Task A", prompt="Do A", execution_step=1),
        ]
        batches = [tasks_step1]

        with patch('n4_cli.commands.autoagent.execute_task',
                   return_value=(False, "Rate limit", "rate_limit")):
            with pytest.raises(TaskAbortException, match="Rate limit exceeded"):
                await run_step_execution(batches, verbose=False, abort_on_failure=True)

    @pytest.mark.asyncio
    async def test_step_execution_exception_abort(self):
        """Test step execution with exception."""
        tasks_step1 = [
            TaskConfig(name="Task A", prompt="Do A", execution_step=1),
        ]
        batches = [tasks_step1]

        with patch('n4_cli.commands.autoagent.execute_task',
                   side_effect=Exception("Test exception")):
            with pytest.raises(TaskAbortException):
                await run_step_execution(batches, verbose=False, abort_on_failure=True)

    @pytest.mark.asyncio
    async def test_single_task_per_step(self):
        """Test execution with single task per step."""
        tasks_step1 = [
            TaskConfig(name="Task A", prompt="Do A", execution_step=1),
        ]
        tasks_step2 = [
            TaskConfig(name="Task B", prompt="Do B", execution_step=2),
        ]
        batches = [tasks_step1, tasks_step2]

        with patch('n4_cli.commands.autoagent.execute_task',
                   return_value=(True, "Success", None)) as mock_execute:
            await run_step_execution(batches, verbose=False, abort_on_failure=True)

            assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    async def test_step_execution_with_goto_forward(self):
        """Test step execution with goto that jumps forward (skipping steps)."""
        tasks_step1 = [
            TaskConfig(name="Task A", task_type="command", command="echo A", execution_step=1),
        ]
        tasks_step2 = [
            TaskConfig(name="Goto step 4", task_type="goto", goto_step=4, execution_step=2),
        ]
        tasks_step3 = [
            TaskConfig(name="Task B (skipped)", task_type="command", command="echo B", execution_step=3),
        ]
        tasks_step4 = [
            TaskConfig(name="Task C", task_type="command", command="echo C", execution_step=4),
        ]
        batches = [tasks_step1, tasks_step2, tasks_step3, tasks_step4]

        call_count = 0
        executed_tasks = []

        async def mock_execute(task, task_num, total, verbose):
            nonlocal call_count
            call_count += 1
            executed_tasks.append(task.name)
            if task.task_type == "goto":
                return True, str(task.goto_step), "goto"
            return True, "Success", None

        with patch('n4_cli.commands.autoagent.execute_task', side_effect=mock_execute):
            await run_step_execution(batches, verbose=False, abort_on_failure=True)

        # Should execute: Task A, Goto step 4, Task C (skipping Task B)
        assert "Task A" in executed_tasks
        assert "Goto step 4" in executed_tasks
        assert "Task C" in executed_tasks
        assert "Task B (skipped)" not in executed_tasks

    @pytest.mark.asyncio
    async def test_step_execution_with_goto_nonexistent_step(self):
        """Test step execution with goto to a non-existent step."""
        tasks_step1 = [
            TaskConfig(name="Task A", task_type="command", command="echo A", execution_step=1),
        ]
        tasks_step2 = [
            TaskConfig(name="Goto step 99", task_type="goto", goto_step=99, execution_step=2),
        ]
        tasks_step3 = [
            TaskConfig(name="Task B", task_type="command", command="echo B", execution_step=3),
        ]
        batches = [tasks_step1, tasks_step2, tasks_step3]

        executed_tasks = []

        async def mock_execute(task, task_num, total, verbose):
            executed_tasks.append(task.name)
            if task.task_type == "goto":
                return True, str(task.goto_step), "goto"
            return True, "Success", None

        with patch('n4_cli.commands.autoagent.execute_task', side_effect=mock_execute):
            await run_step_execution(batches, verbose=False, abort_on_failure=True)

        # Since step 99 doesn't exist, should continue to next step
        assert "Task A" in executed_tasks
        assert "Goto step 99" in executed_tasks
        assert "Task B" in executed_tasks


class TestIntegration:
    """Integration tests for the full autoagent flow."""

    @pytest.mark.asyncio
    async def test_full_step_flow(self, tmp_path, sample_yaml_config):
        """Test complete step-based execution flow."""
        config_file = tmp_path / "autoagent.yaml"
        config_file.write_text(sample_yaml_config)

        with patch('n4_cli.commands.autoagent.execute_claude_prompt',
                   return_value=(True, "Success", None)):
            from n4_cli.commands.autoagent import run_autoagent

            # Should complete without error
            await run_autoagent(config_file, verbose=False)

    @pytest.mark.asyncio
    async def test_full_parallel_step_flow(self, tmp_path, sample_step_yaml_config):
        """Test complete parallel step execution flow."""
        config_file = tmp_path / "autoagent.yaml"
        config_file.write_text(sample_step_yaml_config)

        with patch('n4_cli.commands.autoagent.execute_claude_prompt',
                   return_value=(True, "Success", None)):
            from n4_cli.commands.autoagent import run_autoagent

            # Should complete without error
            await run_autoagent(config_file, verbose=False)

    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self, tmp_path, sample_circular_dependency_config):
        """Test that circular dependencies are detected."""
        config_file = tmp_path / "autoagent.yaml"
        config_file.write_text(sample_circular_dependency_config)

        from n4_cli.commands.autoagent import run_autoagent

        # Should detect circular dependency
        # The function handles this internally and displays error, doesn't raise
        await run_autoagent(config_file, verbose=False)

    @pytest.mark.asyncio
    async def test_goto_task_integration(self, tmp_path, sample_goto_forward_config):
        """Test complete flow with goto task that skips steps."""
        config_file = tmp_path / "autoagent.yaml"
        config_file.write_text(sample_goto_forward_config)

        executed_commands = []

        async def mock_shell_command(command, working_directory=None, timeout=300):
            executed_commands.append(command)
            return True, f"Executed: {command}", None

        with patch('n4_cli.commands.autoagent.execute_shell_command', side_effect=mock_shell_command):
            from n4_cli.commands.autoagent import run_autoagent

            await run_autoagent(config_file, verbose=False)

        # Task A and Final task should be executed
        # Task B should be skipped due to goto
        assert 'echo "A"' in executed_commands
        assert 'echo "Final"' in executed_commands
        assert 'echo "B"' not in executed_commands


class TestGotoTaskType:
    """Tests specifically for goto task type functionality."""

    def test_goto_task_config_creation(self):
        """Test creating a goto TaskConfig."""
        task = TaskConfig(
            name="Jump task",
            task_type="goto",
            goto_step=5,
            execution_step=2
        )

        assert task.name == "Jump task"
        assert task.task_type == "goto"
        assert task.goto_step == 5
        assert task.execution_step == 2
        assert task.prompt is None
        assert task.command is None

    def test_goto_task_default_values(self):
        """Test default values for goto task."""
        task = TaskConfig(
            name="Goto",
            task_type="goto",
            goto_step=1
        )

        assert task.execution_step == 1  # Default
        assert task.model == "sonnet"  # Default
        assert task.timeout == 300  # Default

    @pytest.mark.asyncio
    async def test_execute_goto_returns_correct_format(self):
        """Test that execute_task returns correct format for goto."""
        task = TaskConfig(
            name="Jump to 10",
            task_type="goto",
            goto_step=10,
            execution_step=1
        )

        success, output, error_type = await execute_task(task, 1, 1, verbose=False)

        # Goto should return success=True, output=step_number, error_type='goto'
        assert success is True
        assert output == "10"
        assert error_type == "goto"


class TestPromptFlags:
    """Tests for prompt_flags functionality."""

    def test_parse_prompt_flags(self, tmp_path):
        """Test parsing a task with prompt_flags."""
        config_file = tmp_path / "prompt_flags.yaml"
        config_file.write_text("""
version: "1.0"
tasks:
  - name: "Task with flags"
    type: prompt
    prompt: "Do something"
    prompt_flags: "--chrome --permission-mode acceptEdits"
""")

        config = parse_yaml_config(config_file)

        assert len(config.tasks) == 1
        assert config.tasks[0].name == "Task with flags"
        assert config.tasks[0].prompt_flags == "--chrome --permission-mode acceptEdits"

    def test_parse_prompt_flags_none(self, tmp_path):
        """Test parsing a task without prompt_flags (should be None)."""
        config_file = tmp_path / "no_flags.yaml"
        config_file.write_text("""
version: "1.0"
tasks:
  - name: "Task without flags"
    type: prompt
    prompt: "Do something"
""")

        config = parse_yaml_config(config_file)

        assert len(config.tasks) == 1
        assert config.tasks[0].prompt_flags is None

    def test_parse_prompt_flags_invalid_type(self, tmp_path):
        """Test parsing task with invalid prompt_flags type."""
        config_file = tmp_path / "invalid_flags.yaml"
        config_file.write_text("""
version: "1.0"
tasks:
  - name: "Task with invalid flags"
    type: prompt
    prompt: "Do something"
    prompt_flags: 123
""")

        with pytest.raises(ValueError, match="invalid 'prompt_flags' value"):
            parse_yaml_config(config_file)

    def test_prompt_flags_task_config(self):
        """Test creating TaskConfig with prompt_flags."""
        task = TaskConfig(
            name="Test task",
            prompt="Do something",
            prompt_flags="--chrome --permission-mode acceptEdits"
        )

        assert task.prompt_flags == "--chrome --permission-mode acceptEdits"

    def test_prompt_flags_default_none(self):
        """Test that prompt_flags defaults to None."""
        task = TaskConfig(
            name="Test task",
            prompt="Do something"
        )

        assert task.prompt_flags is None

    @pytest.mark.asyncio
    async def test_execute_claude_prompt_with_flags(self):
        """Test execute_claude_prompt with custom flags."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"Success output", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_shell', return_value=mock_process) as mock_subprocess:
            from n4_cli.commands.autoagent import execute_claude_prompt
            success, output, error_type = await execute_claude_prompt(
                "Test prompt",
                "sonnet",
                "--chrome --permission-mode acceptEdits"
            )

            assert success is True
            assert output == "Success output"
            # Verify the command included the custom flags
            call_args = mock_subprocess.call_args[0][0]
            assert "--chrome" in call_args
            assert "--permission-mode acceptEdits" in call_args

    @pytest.mark.asyncio
    async def test_execute_claude_prompt_default_flags(self):
        """Test execute_claude_prompt without custom flags uses default."""
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"Success output", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_shell', return_value=mock_process) as mock_subprocess:
            from n4_cli.commands.autoagent import execute_claude_prompt
            success, output, error_type = await execute_claude_prompt(
                "Test prompt",
                "sonnet"
            )

            assert success is True
            # Verify the command included the default permission mode
            call_args = mock_subprocess.call_args[0][0]
            assert "--permission-mode acceptEdits" in call_args

    @pytest.mark.asyncio
    async def test_execute_task_with_prompt_flags(self):
        """Test execute_task passes prompt_flags to execute_claude_prompt."""
        task = TaskConfig(
            name="Test task",
            prompt="Do something",
            prompt_flags="--chrome --dangerously-skip-permissions"
        )

        with patch('n4_cli.commands.autoagent.execute_claude_prompt',
                   return_value=(True, "Success", None)) as mock_execute:
            success, output, error_type = await execute_task(task, 1, 1, verbose=False)

            assert success is True
            # Verify execute_claude_prompt was called with the flags
            mock_execute.assert_called_once_with(
                "Do something",
                "sonnet",
                "--chrome --dangerously-skip-permissions"
            )
