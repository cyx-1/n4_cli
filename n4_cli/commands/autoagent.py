"""Autoagent command - Execute tasks from autoagent.yaml file."""

import asyncio
import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import click
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)


class TaskAbortException(Exception):
    """Exception raised when a task needs to abort the entire operation."""

    pass


@dataclass
class TaskConfig:
    """Configuration for a single task."""

    name: str
    task_type: str = "prompt"  # "prompt", "command", "goto", or "prepare_next_prompt"
    prompt: Optional[str] = None
    prompt_file: Optional[str] = None  # For prompt tasks: path to file containing prompt
    command: Optional[str] = None
    model: str = "sonnet"
    agent: str = "claude"
    branch: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    share_branch_with: Optional[str] = None
    auto_push: bool = False
    working_directory: Optional[str] = None  # For command tasks
    timeout: int = 300  # Timeout in seconds for command tasks
    execution_step: int = 1  # Tasks with same step run in parallel, lower steps run first
    goto_step: Optional[int] = None  # For goto tasks: step number to jump to
    prompt_flags: Optional[str] = None  # For prompt tasks: additional CLI flags for claude command
    plan_file: Optional[str] = None  # For prepare_next_prompt tasks: path to YAML file with prompts


@dataclass
class AutoAgentConfig:
    """Complete autoagent configuration."""

    version: str
    defaults: Dict
    tasks: List[TaskConfig]


def is_claude_available() -> bool:
    """Check if claude CLI is available."""
    return shutil.which("claude") is not None


def get_claude_history_folder() -> Optional[Path]:
    """Get the Claude history folder for the current project.

    Claude stores conversation history in ~/.claude/projects/{folder_name}/
    where folder_name is the current working directory path with special chars replaced by dashes.

    Returns:
        Path to the history folder if it exists, None otherwise
    """
    # Get home directory (works on both Linux and Windows)
    home = Path.home()
    claude_projects = home / ".claude" / "projects"

    if not claude_projects.exists():
        return None

    # Get current working directory and convert to folder name format
    cwd = Path.cwd().absolute()
    # Claude replaces slashes, backslashes, and underscores with dashes, prefixed with a dash
    folder_name = str(cwd).replace("/", "-").replace("\\", "-").replace("_", "-")
    if not folder_name.startswith("-"):
        folder_name = "-" + folder_name

    history_folder = claude_projects / folder_name
    if history_folder.exists():
        return history_folder

    return None


def get_latest_history_file(history_folder: Path) -> Optional[Path]:
    """Get the most recently modified JSONL file in the history folder.

    Args:
        history_folder: Path to the Claude history folder

    Returns:
        Path to the most recent JSONL file, or None if no files found
    """
    jsonl_files = list(history_folder.glob("*.jsonl"))
    if not jsonl_files:
        return None

    # Sort by modification time, most recent first
    jsonl_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return jsonl_files[0]


def parse_history_message(line: str) -> Optional[Dict]:
    """Parse a single line from the JSONL history file.

    Args:
        line: A single line from the JSONL file

    Returns:
        Parsed message dict with extracted info, or None if not relevant
    """
    try:
        data = json.loads(line.strip())
    except json.JSONDecodeError:
        return None

    msg_type = data.get("type")

    # Skip non-message types
    if msg_type not in ("user", "assistant"):
        return None

    result = {
        "type": msg_type,
        "timestamp": data.get("timestamp", ""),
        "content": [],
    }

    message = data.get("message", {})
    content = message.get("content")

    if msg_type == "user":
        # User messages have content as a string
        if isinstance(content, str):
            result["content"].append({"type": "text", "text": content})
    elif msg_type == "assistant":
        # Assistant messages have content as an array
        if isinstance(content, list):
            for item in content:
                item_type = item.get("type")
                if item_type == "text":
                    result["content"].append({"type": "text", "text": item.get("text", "")})
                elif item_type == "tool_use":
                    tool_name = item.get("name", "unknown")
                    result["content"].append({"type": "tool_use", "name": tool_name})

    # Only return if we have content
    if result["content"]:
        return result
    return None


def format_history_message(msg: Dict, max_text_length: int = 200) -> str:
    """Format a parsed history message for console display.

    Args:
        msg: Parsed message dict from parse_history_message
        max_text_length: Maximum length for text content before truncation

    Returns:
        Formatted string for display
    """
    msg_type = msg["type"]
    prefix = "👤 User" if msg_type == "user" else "🤖 Claude"

    parts = []
    for item in msg["content"]:
        if item["type"] == "text":
            text = item["text"]
            if len(text) > max_text_length:
                text = text[:max_text_length] + "..."
            # Replace newlines with spaces for compact display
            text = text.replace("\n", " ").strip()
            parts.append(text)
        elif item["type"] == "tool_use":
            parts.append(f"[Tool: {item['name']}]")

    content = " | ".join(parts) if parts else "(no content)"
    return f"{prefix}: {content}"


class ClaudeHistoryMonitor:
    """Monitor Claude conversation history and display updates."""

    def __init__(self):
        self.last_position = 0
        self.last_file: Optional[Path] = None
        self.seen_uuids: Set[str] = set()
        self._stop_event = asyncio.Event()

    def reset(self):
        """Reset the monitor state for a new Claude execution."""
        self.last_position = 0
        self.last_file = None
        self.seen_uuids.clear()
        self._stop_event.clear()

    def stop(self):
        """Signal the monitor to stop."""
        self._stop_event.set()

    def read_new_messages(self) -> List[Dict]:
        """Read new messages from the history file.

        Returns:
            List of new parsed messages
        """
        history_folder = get_claude_history_folder()
        if not history_folder:
            return []

        latest_file = get_latest_history_file(history_folder)
        if not latest_file:
            return []

        # If the file changed, reset position but keep seen_uuids
        if self.last_file != latest_file:
            self.last_file = latest_file
            self.last_position = 0

        messages = []
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                f.seek(self.last_position)
                for line in f:
                    if line.strip():
                        # Check UUID to avoid duplicates
                        try:
                            data = json.loads(line.strip())
                            uuid = data.get("uuid")
                            if uuid and uuid in self.seen_uuids:
                                continue
                            if uuid:
                                self.seen_uuids.add(uuid)
                        except json.JSONDecodeError:
                            pass

                        msg = parse_history_message(line)
                        if msg:
                            messages.append(msg)
                self.last_position = f.tell()
        except (OSError, IOError):
            pass

        return messages

    async def monitor_loop(self, interval: float = 1.0):
        """Continuously monitor for new messages.

        Args:
            interval: Time between checks in seconds
        """
        while not self._stop_event.is_set():
            messages = self.read_new_messages()
            for msg in messages:
                formatted = format_history_message(msg)
                click.echo(click.style(f"   📜 {formatted}", fg="magenta"))

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass


# Global history monitor instance
_history_monitor = ClaudeHistoryMonitor()


def parse_yaml_config(file_path: Path) -> AutoAgentConfig:
    """Parse autoagent.yaml file to extract configuration.

    Args:
        file_path: Path to the YAML configuration file

    Returns:
        AutoAgentConfig object with parsed configuration

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If YAML is invalid or missing required fields
    """
    logger.info(f"📖 Parsing configuration file: {file_path}")

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format: {e}")

    if not data:
        raise ValueError("Empty configuration file")

    # Extract defaults
    defaults = data.get('defaults', {})
    default_model = defaults.get('model', 'sonnet')
    default_agent = defaults.get('agent', 'claude')
    default_branch_strategy = defaults.get('branch_strategy', 'separate')
    default_auto_push = defaults.get('auto_push', False)

    # Parse tasks
    tasks_data = data.get('tasks', [])
    if not tasks_data:
        raise ValueError("No tasks defined in configuration")

    tasks = []
    for task_data in tasks_data:
        if not isinstance(task_data, dict):
            raise ValueError(f"Invalid task format: {task_data}")

        name = task_data.get('name')
        prompt = task_data.get('prompt')
        prompt_file = task_data.get('prompt_file')
        command = task_data.get('command')
        task_type = task_data.get('type', 'prompt')  # Default to 'prompt'

        if not name:
            raise ValueError("Task missing required 'name' field")

        # Get goto_step for goto tasks
        goto_step = task_data.get('goto_step')

        # Validate that either prompt or prompt_file is provided for prompt tasks
        if task_type == 'prompt':
            if prompt and prompt_file:
                raise ValueError(f"Task '{name}' cannot have both 'prompt' and 'prompt_file' - use only one")
            if not prompt and not prompt_file:
                raise ValueError(f"Task '{name}' of type 'prompt' requires either 'prompt' or 'prompt_file' field")

            # If prompt_file is specified, we'll read it at execution time (not now)
            # This allows the file to be created/updated during execution (e.g., by prepare_next_prompt)
            if prompt_file:
                logger.info(f"   📄 Will read prompt from file at execution time: {prompt_file}")
                # Don't read the file now - it will be read when the task executes
                prompt = None  # Clear prompt since we'll read from file later
        if task_type == 'command' and not command:
            raise ValueError(f"Task '{name}' of type 'command' missing required 'command' field")
        if task_type == 'goto' and goto_step is None:
            raise ValueError(f"Task '{name}' of type 'goto' missing required 'goto_step' field")
        if task_type == 'goto' and not isinstance(goto_step, int):
            raise ValueError(f"Task '{name}' has invalid 'goto_step' value. Must be an integer")

        # Get plan_file for prepare_next_prompt tasks
        plan_file = task_data.get('plan_file')
        if task_type == 'prepare_next_prompt':
            if not plan_file:
                raise ValueError(f"Task '{name}' of type 'prepare_next_prompt' missing required 'plan_file' field")
            if not prompt_file:
                raise ValueError(f"Task '{name}' of type 'prepare_next_prompt' missing required 'prompt_file' field")

        if task_type not in ['prompt', 'command', 'goto', 'prepare_next_prompt']:
            raise ValueError(f"Task '{name}' has invalid type '{task_type}'. Must be 'prompt', 'command', 'goto', or 'prepare_next_prompt'")

        # Get prompt_flags for prompt tasks
        prompt_flags = task_data.get('prompt_flags')
        if prompt_flags is not None and not isinstance(prompt_flags, str):
            raise ValueError(f"Task '{name}' has invalid 'prompt_flags' value. Must be a string")

        task = TaskConfig(
            name=name,
            task_type=task_type,
            prompt=prompt.strip() if prompt else None,
            prompt_file=prompt_file,
            command=command.strip() if command else None,
            model=task_data.get('model', default_model),
            agent=task_data.get('agent', default_agent),
            branch=task_data.get('branch'),
            depends_on=task_data.get('depends_on', []),
            share_branch_with=task_data.get('share_branch_with'),
            auto_push=task_data.get('auto_push', default_auto_push),
            working_directory=task_data.get('working_directory'),
            timeout=task_data.get('timeout', 300),
            execution_step=task_data.get('execution_step', 1),
            goto_step=goto_step,
            prompt_flags=prompt_flags.strip() if prompt_flags else None,
            plan_file=plan_file,
        )
        tasks.append(task)

    logger.info(f"✅ Parsed {len(tasks)} task(s) successfully")

    return AutoAgentConfig(version=data.get('version', '1.0'), defaults=defaults, tasks=tasks)


async def execute_task(task: TaskConfig, step_num: int, total_steps: int, verbose: bool = False) -> Tuple[bool, str, Optional[str]]:
    """Execute a single task (prompt, command, goto, or prepare_next_prompt).

    Args:
        task: TaskConfig to execute
        step_num: Current step number (1-indexed)
        total_steps: Total number of steps
        verbose: Whether to show verbose output

    Returns:
        Tuple of (success: bool, output: str, error_type: Optional[str])
        error_type can be 'rate_limit', 'auth_error', 'generic', 'goto', 'no_more_prompts', or None
        For goto tasks, error_type is 'goto' and output contains the step number to jump to
    """
    logger.info(f"🚀 Starting step {step_num}/{total_steps}: {task.name}")
    logger.info(f"   Type: {task.task_type}")

    if task.branch:
        logger.info(f"   Branch: {task.branch}")

    try:
        if task.task_type == 'goto':
            # Goto task - signal to jump to specified step
            logger.info(f"   Goto step: {task.goto_step}")
            return True, str(task.goto_step), 'goto'
        elif task.task_type == 'prepare_next_prompt':
            # Prepare next prompt task - mark current complete and save next to file
            logger.info(f"   Plan file: {task.plan_file}")
            logger.info(f"   Prompt file: {task.prompt_file}")
            success, output, error_type = await execute_prepare_next_prompt(task.plan_file, task.prompt_file)
        elif task.task_type == 'command':
            # Execute shell command
            if verbose:
                logger.info(f"   Command: {task.command}")
            if task.working_directory:
                logger.info(f"   Working directory: {task.working_directory}")
            logger.info(f"   Timeout: {task.timeout}s")

            success, output, error_type = await execute_shell_command(task.command, task.working_directory, task.timeout)
        else:
            # Execute LLM prompt
            logger.info(f"   Model: {task.model}, Agent: {task.agent}")

            # Read prompt from file if prompt_file is specified
            prompt_to_execute = task.prompt
            if task.prompt_file:
                logger.info(f"   Reading prompt from file: {task.prompt_file}")
                try:
                    prompt_file_path = Path(task.prompt_file)
                    if not prompt_file_path.exists():
                        return False, f"Prompt file not found: {task.prompt_file}", 'file_not_found'

                    with open(prompt_file_path, 'r') as pf:
                        prompt_to_execute = pf.read()

                    if not prompt_to_execute or not prompt_to_execute.strip():
                        return False, f"Prompt file is empty: {task.prompt_file}", 'empty_prompt_file'

                    logger.info(f"   ✅ Successfully read prompt from file")
                except Exception as e:
                    return False, f"Failed to read prompt file '{task.prompt_file}': {e}", 'file_read_error'

            if task.prompt_flags:
                logger.info(f"   Prompt flags: {task.prompt_flags}")

            # Always print the full prompt to console
            click.echo(click.style(f"\n📝 Prompt:", fg="blue", bold=True))
            click.echo(click.style("-" * 40, fg="blue"))
            click.echo(prompt_to_execute)
            click.echo(click.style("-" * 40, fg="blue"))

            # For now, we only support claude agent
            if task.agent.lower() != 'claude':
                logger.warning(f"⚠️  Agent '{task.agent}' not yet supported, falling back to 'claude'")

            success, output, error_type = await execute_claude_prompt(prompt_to_execute, task.model, task.prompt_flags)

        if success:
            logger.info(f"✅ Step {step_num}/{total_steps} completed successfully: {task.name}")
        else:
            logger.error(f"❌ Step {step_num}/{total_steps} failed: {task.name}")
            if error_type:
                logger.error(f"   Error type: {error_type}")

        return success, output, error_type

    except Exception as e:
        logger.error(f"❌ Step {step_num}/{total_steps} failed with exception: {task.name}")
        logger.error(f"   Exception: {str(e)}")
        return False, str(e), 'generic'


async def execute_shell_command(command: str, working_directory: Optional[str] = None, timeout: int = 300) -> Tuple[bool, str, Optional[str]]:
    """Execute a shell command and return the result.

    Args:
        command: The shell command to execute
        working_directory: Optional working directory for the command
        timeout: Timeout in seconds (default: 300)

    Returns:
        Tuple of (success: bool, output: str, error_type: Optional[str])
    """
    try:
        logger.debug(f"Executing command: {command}")

        # Set working directory if specified
        cwd = working_directory if working_directory else None

        # Execute command
        proc = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd)

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return False, f"Command timed out after {timeout} seconds", 'timeout'

        # Combine stdout and stderr
        output = ""
        if stdout:
            output += stdout.decode()
        if stderr:
            if output:
                output += "\n--- STDERR ---\n"
            output += stderr.decode()

        output = output.strip() if output else "Command completed with no output"

        if proc.returncode == 0:
            return True, output, None
        else:
            # Command failed - check for specific error patterns
            error_type = 'generic'
            output_lower = output.lower()

            # You can add more specific error detection here
            if 'permission denied' in output_lower:
                error_type = 'permission_error'
            elif 'not found' in output_lower or 'command not found' in output_lower:
                error_type = 'command_not_found'

            return False, output, error_type

    except FileNotFoundError:
        return False, f"Working directory not found: {working_directory}", 'directory_not_found'
    except Exception as e:
        return False, f"Command execution failed: {str(e)}", 'generic'


async def execute_claude_prompt(prompt: str, model: str = "sonnet", prompt_flags: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """Execute a Claude prompt and return the result.

    Args:
        prompt: The prompt to send to Claude
        model: The model to use (sonnet, opus, haiku)
        prompt_flags: Optional additional CLI flags for the claude command

    Returns:
        Tuple of (success: bool, output: str, error_type: Optional[str])
    """
    try:
        # Handle None or empty prompt
        if prompt is None:
            return False, "Prompt is None - prompt file may be empty or task configuration is invalid", 'generic'

        # Escape double quotes in prompt
        escaped_prompt = prompt.replace('"', '\\"').replace('$', '\\$')

        # Build command with optional flags
        # Default flags that are always included
        base_cmd = f'claude --model {model}'

        # Add custom prompt_flags if provided, otherwise use default permission mode
        if prompt_flags:
            base_cmd = f'{base_cmd} {prompt_flags}'
        else:
            base_cmd = f'{base_cmd}'

        cmd = f'{base_cmd} -p "{escaped_prompt}"'

        logger.debug(f"Executing command: {base_cmd} -p [prompt]")

        # Reset and start the history monitor
        _history_monitor.reset()
        click.echo(click.style("\n   📡 Monitoring Claude conversation history...", fg="magenta"))

        # Start the history monitor as a background task
        monitor_task = asyncio.create_task(_history_monitor.monitor_loop(interval=1.0))

        try:
            proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
        finally:
            # Stop the monitor
            _history_monitor.stop()
            try:
                await asyncio.wait_for(monitor_task, timeout=2.0)
            except asyncio.TimeoutError:
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass

        click.echo(click.style("   📡 History monitoring complete.", fg="magenta"))

        if proc.returncode == 0:
            output = stdout.decode().strip()
            return True, output, None
        else:
            error = stderr.decode().strip() if stderr else "Unknown error"

            # Detect error types
            error_type = None
            error_lower = error.lower()
            if 'rate limit' in error_lower or 'too many requests' in error_lower:
                error_type = 'rate_limit'
            elif 'auth' in error_lower or 'unauthorized' in error_lower:
                error_type = 'auth_error'
            else:
                error_type = 'generic'

            return False, error, error_type

    except Exception as e:
        return False, str(e), 'generic'


async def execute_prepare_next_prompt(plan_file: str, prompt_file: str) -> Tuple[bool, str, Optional[str]]:
    """Execute prepare_next_prompt: mark current prompt complete and save next prompt to file.

    The plan_file is a YAML file with the following structure:
    ```yaml
    prompts:
      - prompt: "First prompt text"
        status: complete
      - prompt: "Second prompt text"
        status: incomplete
      - prompt: "Third prompt text"
        status: incomplete
    ```

    This function:
    1. Finds the first incomplete prompt and marks it as complete
    2. Saves the updated plan_file
    3. Finds the next incomplete prompt and writes it to prompt_file
    4. If no more incomplete prompts, returns success with 'no_more_prompts' error type

    Args:
        plan_file: Path to YAML file containing prompts with status
        prompt_file: Path to file where the next prompt will be written

    Returns:
        Tuple of (success: bool, output: str, error_type: Optional[str])
        error_type can be 'no_more_prompts' when all prompts are complete
    """
    try:
        plan_path = Path(plan_file)
        prompt_path = Path(prompt_file)

        # Read the plan file
        if not plan_path.exists():
            return False, f"Plan file not found: {plan_file}", 'file_not_found'

        with open(plan_path, 'r') as f:
            plan_data = yaml.safe_load(f)

        if not plan_data or 'prompts' not in plan_data:
            return False, f"Invalid plan file format: missing 'prompts' key", 'invalid_format'

        prompts = plan_data['prompts']
        if not isinstance(prompts, list):
            return False, f"Invalid plan file format: 'prompts' must be a list", 'invalid_format'

        # Find the first incomplete prompt and mark it as complete
        first_incomplete_idx = None
        for idx, item in enumerate(prompts):
            if not isinstance(item, dict):
                return False, f"Invalid prompt entry at index {idx}: must be a dictionary", 'invalid_format'
            if item.get('status') != 'complete':
                first_incomplete_idx = idx
                break

        if first_incomplete_idx is None:
            # All prompts are already complete
            # Clear the prompt file to indicate no more work
            with open(prompt_path, 'w') as f:
                f.write("")
            return True, "All prompts already complete", 'no_more_prompts'

        # Mark the first incomplete prompt as complete
        prompts[first_incomplete_idx]['status'] = 'complete'
        completed_prompt = prompts[first_incomplete_idx].get('prompt', '[no prompt text]')
        logger.info(f"   ✅ Marked prompt {first_incomplete_idx + 1} as complete")

        # Save the updated plan file
        with open(plan_path, 'w') as f:
            yaml.dump(plan_data, f, default_flow_style=False, allow_unicode=True)
        logger.info(f"   💾 Updated plan file: {plan_file}")

        # Find the next incomplete prompt
        next_incomplete_idx = None
        for idx, item in enumerate(prompts):
            if item.get('status') != 'complete':
                next_incomplete_idx = idx
                break

        if next_incomplete_idx is None:
            # No more incomplete prompts
            with open(prompt_path, 'w') as f:
                f.write("")
            return True, f"Completed prompt {first_incomplete_idx + 1}. No more prompts remaining.", 'no_more_prompts'

        # Write the next prompt to prompt_file
        next_prompt = prompts[next_incomplete_idx].get('prompt', '')
        # Ensure next_prompt is a string (not None)
        if next_prompt is None:
            return False, f"Prompt {next_incomplete_idx + 1} in plan file has null/None value", 'invalid_prompt'
        if not isinstance(next_prompt, str):
            return False, f"Prompt {next_incomplete_idx + 1} in plan file must be a string, got {type(next_prompt)}", 'invalid_prompt'
        with open(prompt_path, 'w') as f:
            f.write(next_prompt)
        logger.info(f"   📝 Wrote next prompt ({next_incomplete_idx + 1}) to: {prompt_file}")

        return True, f"Completed prompt {first_incomplete_idx + 1}. Next prompt ({next_incomplete_idx + 1}) saved to {prompt_file}", None

    except yaml.YAMLError as e:
        return False, f"Failed to parse plan file: {e}", 'yaml_error'
    except Exception as e:
        return False, f"Error in prepare_next_prompt: {str(e)}", 'generic'


def build_dependency_graph(tasks: List[TaskConfig]) -> Dict[str, Set[str]]:
    """Build a dependency graph from tasks.

    Args:
        tasks: List of TaskConfig objects

    Returns:
        Dictionary mapping task name to set of tasks it depends on

    Raises:
        ValueError: If there are circular dependencies or missing dependencies
    """
    logger.info("🔗 Building dependency graph...")

    task_names = {task.name for task in tasks}
    graph = {}

    for task in tasks:
        # Check that all dependencies exist
        for dep in task.depends_on:
            if dep not in task_names:
                raise ValueError(f"Task '{task.name}' depends on non-existent task '{dep}'")

        graph[task.name] = set(task.depends_on)

    # Check for circular dependencies using DFS
    def has_cycle(node: str, visited: Set[str], rec_stack: Set[str]) -> bool:
        visited.add(node)
        rec_stack.add(node)

        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                if has_cycle(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True

        rec_stack.remove(node)
        return False

    visited = set()
    for task_name in graph:
        if task_name not in visited:
            if has_cycle(task_name, visited, set()):
                raise ValueError(f"Circular dependency detected involving task '{task_name}'")

    logger.info("✅ Dependency graph validated (no circular dependencies)")
    return graph


def get_execution_order(tasks: List[TaskConfig], dependency_graph: Dict[str, Set[str]]) -> List[List[TaskConfig]]:
    """Get execution order for tasks based on execution_step.

    Returns a list of task batches. Tasks with the same execution_step run in parallel.
    Steps are executed in ascending order (step 1 first, then step 2, etc.).

    Args:
        tasks: List of TaskConfig objects
        dependency_graph: Dependency graph from build_dependency_graph (used for validation)

    Returns:
        List of task batches (each batch is a list of tasks that can run in parallel)
    """
    logger.info("📊 Calculating execution order by step...")

    # Group tasks by execution_step
    step_groups: Dict[int, List[TaskConfig]] = {}
    for task in tasks:
        step = task.execution_step
        if step not in step_groups:
            step_groups[step] = []
        step_groups[step].append(task)

    # Sort by step number and create batches
    sorted_steps = sorted(step_groups.keys())
    batches = [step_groups[step] for step in sorted_steps]

    logger.info(f"✅ Execution order calculated: {len(batches)} step(s)")
    for step in sorted_steps:
        logger.info(f"   Step {step}: {[task.name for task in step_groups[step]]}")

    return batches


async def run_autoagent(file_path: Path, verbose: bool):
    """Run all tasks from autoagent configuration file.

    Tasks are grouped by execution_step and run in parallel within each step.
    Steps are executed in order (step 1 first, then step 2, etc.).

    Args:
        file_path: Path to YAML configuration file
        verbose: Whether to show verbose output
    """
    click.echo(click.style(f"\n🤖 AutoAgent Starting...", fg="cyan", bold=True))
    click.echo(click.style(f"📄 Reading configuration from: {file_path}", fg="blue"))

    try:
        config = parse_yaml_config(file_path)
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        click.echo(click.style(f"❌ Error: {e}", fg="red"))
        return
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        click.echo(click.style(f"❌ Configuration error: {e}", fg="red"))
        return
    except Exception as e:
        logger.error(f"Unexpected error parsing file: {e}")
        click.echo(click.style(f"❌ Error parsing file: {e}", fg="red"))
        return

    # Display configuration summary
    click.echo(click.style(f"\n⚙️  Configuration:", fg="blue", bold=True))
    click.echo(f"   Version: {config.version}")
    click.echo(f"   Default Model: {config.defaults.get('model', 'sonnet')}")
    click.echo(f"   Default Agent: {config.defaults.get('agent', 'claude')}")
    click.echo(f"   Branch Strategy: {config.defaults.get('branch_strategy', 'separate')}")
    click.echo(f"   Auto Push: {config.defaults.get('auto_push', False)}")
    click.echo(f"   Abort on Failure: {config.defaults.get('abort_on_failure', True)}")

    tasks = config.tasks
    click.echo(click.style(f"\n📋 Found {len(tasks)} task(s)", fg="green"))

    # Build dependency graph
    try:
        dependency_graph = build_dependency_graph(tasks)
    except ValueError as e:
        logger.error(f"Dependency error: {e}")
        click.echo(click.style(f"❌ Dependency error: {e}", fg="red"))
        return

    abort_on_failure = config.defaults.get('abort_on_failure', True)

    try:
        # Get batches grouped by execution_step
        batches = get_execution_order(tasks, dependency_graph)
        await run_step_execution(batches, verbose, abort_on_failure)

        click.echo(click.style(f"\n{'='*80}", fg="green"))
        click.echo(click.style(f"✨ AutoAgent completed all task(s)!", fg="green", bold=True))
        click.echo(click.style(f"{'='*80}", fg="green"))

    except TaskAbortException as e:
        logger.error(f"Task execution aborted: {e}")
        click.echo(click.style(f"\n{'='*80}", fg="red"))
        click.echo(click.style(f"🛑 AutoAgent aborted: {e}", fg="red", bold=True))
        click.echo(click.style(f"{'='*80}", fg="red"))
        sys.exit(1)


async def run_step_execution(batches: List[List[TaskConfig]], verbose: bool, abort_on_failure: bool):
    """Run tasks grouped by execution_step.

    Tasks with the same execution_step run in parallel. Steps are executed in order.
    Supports goto tasks that can jump to a specific execution step.

    Args:
        batches: List of task batches (tasks in same step run in parallel)
        verbose: Whether to show verbose output
        abort_on_failure: Whether to abort on task failure
    """
    total_tasks = sum(len(batch) for batch in batches)
    total_steps = len(batches)
    logger.info(f"⚡ Starting step-based execution of {total_tasks} task(s) in {total_steps} step(s)")

    # Build a mapping of execution_step to batch index for goto support
    step_to_batch_idx: Dict[int, int] = {}
    for idx, batch in enumerate(batches):
        # All tasks in a batch have the same execution_step
        if batch:
            step_to_batch_idx[batch[0].execution_step] = idx

    batch_idx = 0

    while batch_idx < len(batches):
        batch = batches[batch_idx]
        step_num = batch_idx + 1

        click.echo(click.style(f"\n{'='*80}", fg="cyan"))
        if len(batch) == 1:
            click.echo(click.style(f"Step {step_num}/{total_steps}: {batch[0].name}", fg="cyan", bold=True))
        else:
            click.echo(click.style(f"Step {step_num}/{total_steps}: {len(batch)} task(s) in parallel", fg="cyan", bold=True))
            click.echo(click.style(f"Tasks: {[task.name for task in batch]}", fg="cyan"))
        click.echo(click.style(f"{'='*80}", fg="cyan"))

        # Execute all tasks in this step concurrently
        results = await asyncio.gather(*[execute_task(task, step_num, total_steps, verbose) for i, task in enumerate(batch)], return_exceptions=True)

        # Track if we need to goto a different step
        goto_target_step: Optional[int] = None

        # Process results
        for i, (task, result) in enumerate(zip(batch, results)):
            if len(batch) > 1:
                click.echo(click.style(f"\n--- Task: {task.name} ---", fg="blue"))

            if isinstance(result, Exception):
                click.echo(click.style(f"❌ Task failed with exception!", fg="red", bold=True))
                click.echo(click.style(f"Error: {str(result)}", fg="red"))

                if abort_on_failure:
                    logger.error(f"Task '{task.name}' failed - aborting")
                    raise TaskAbortException(f"Task '{task.name}' failed with exception")
            else:
                success, output, error_type = result

                # Handle goto task
                if error_type == 'goto' and success:
                    goto_target_step = int(output)
                    click.echo(click.style(f"\n🔀 Goto: Jumping to step {goto_target_step}", fg="yellow", bold=True))
                    continue

                if success:
                    click.echo(click.style(f"\n✅ Task completed successfully!", fg="green", bold=True))
                    if verbose or len(output) < 500:
                        click.echo(click.style(f"\n📤 Output:", fg="blue"))
                        click.echo(output)
                else:
                    click.echo(click.style(f"\n❌ Task failed!", fg="red", bold=True))
                    click.echo(click.style(f"Error: {output}", fg="red"))

                    # Check for critical errors
                    if error_type == 'rate_limit':
                        logger.error("Rate limit exceeded - aborting all tasks")
                        raise TaskAbortException("Rate limit exceeded")

                    if abort_on_failure:
                        logger.error(f"Task '{task.name}' failed - aborting")
                        raise TaskAbortException(f"Task '{task.name}' failed")

        # Handle goto: jump to the target step if specified
        if goto_target_step is not None:
            if goto_target_step in step_to_batch_idx:
                batch_idx = step_to_batch_idx[goto_target_step]
                logger.info(f"🔀 Jumping to execution_step {goto_target_step} (batch index {batch_idx})")
            else:
                # Target step doesn't exist - warn and continue normally
                logger.warning(f"⚠️  Goto target step {goto_target_step} not found, continuing to next step")
                batch_idx += 1
        else:
            batch_idx += 1


@click.command(name="autoagent")
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=False, path_type=Path),
    default="autoagent.yaml",
    help="Path to autoagent YAML configuration file (default: autoagent.yaml)",
)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output and prompts")
def autoagent(file, verbose):
    """Execute tasks from autoagent.yaml configuration file.

    The autoagent.yaml file defines tasks with their prompts, models, dependencies,
    and execution strategy. See autoagent.yaml.example for the format.

    Tasks are grouped by execution_step and run in parallel within each step.
    Steps are executed in order (step 1 first, then step 2, etc.).

    Features:
    - Step-based parallel execution (tasks with same execution_step run in parallel)
    - Task dependencies
    - Multiple AI models (sonnet, opus, haiku)
    - Branch management
    - Automatic abort on rate limits or failures
    """
    if not is_claude_available():
        logger.error("Claude CLI not found in PATH")
        click.echo(click.style("❌ Error: Claude CLI not found in PATH", fg="red"))
        click.echo(click.style("Please install Claude CLI first", fg="yellow"))
        return

    # Set log level based on verbose flag
    if verbose:
        logger.setLevel(logging.DEBUG)

    # Run the async function
    asyncio.run(run_autoagent(file, verbose))
