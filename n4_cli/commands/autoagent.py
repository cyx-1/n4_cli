"""Autoagent command - Execute tasks from autoagent.yaml file."""

import asyncio
import logging
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import click
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class TaskAbortException(Exception):
    """Exception raised when a task needs to abort the entire operation."""
    pass


@dataclass
class TaskConfig:
    """Configuration for a single task."""
    name: str
    prompt: str
    model: str = "sonnet"
    agent: str = "claude"
    branch: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    share_branch_with: Optional[str] = None
    auto_push: bool = False


@dataclass
class AutoAgentConfig:
    """Complete autoagent configuration."""
    version: str
    defaults: Dict
    tasks: List[TaskConfig]


def is_claude_available() -> bool:
    """Check if claude CLI is available."""
    return shutil.which("claude") is not None


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

        if not name:
            raise ValueError("Task missing required 'name' field")
        if not prompt:
            raise ValueError(f"Task '{name}' missing required 'prompt' field")

        task = TaskConfig(
            name=name,
            prompt=prompt.strip(),
            model=task_data.get('model', default_model),
            agent=task_data.get('agent', default_agent),
            branch=task_data.get('branch'),
            depends_on=task_data.get('depends_on', []),
            share_branch_with=task_data.get('share_branch_with'),
            auto_push=task_data.get('auto_push', default_auto_push)
        )
        tasks.append(task)

    logger.info(f"✅ Parsed {len(tasks)} task(s) successfully")

    return AutoAgentConfig(
        version=data.get('version', '1.0'),
        defaults=defaults,
        tasks=tasks
    )


async def execute_task(
    task: TaskConfig,
    task_num: int,
    total_tasks: int,
    verbose: bool = False
) -> Tuple[bool, str, Optional[str]]:
    """Execute a single task.

    Args:
        task: TaskConfig to execute
        task_num: Current task number (1-indexed)
        total_tasks: Total number of tasks
        verbose: Whether to show verbose output

    Returns:
        Tuple of (success: bool, output: str, error_type: Optional[str])
        error_type can be 'rate_limit', 'auth_error', 'generic', or None
    """
    logger.info(f"🚀 Starting task {task_num}/{total_tasks}: {task.name}")
    logger.info(f"   Model: {task.model}, Agent: {task.agent}")

    if task.branch:
        logger.info(f"   Branch: {task.branch}")

    if verbose:
        logger.info(f"   Prompt: {task.prompt[:100]}...")

    try:
        # For now, we only support claude agent
        if task.agent.lower() != 'claude':
            logger.warning(f"⚠️  Agent '{task.agent}' not yet supported, falling back to 'claude'")

        # Execute with Claude CLI
        success, output, error_type = await execute_claude_prompt(
            task.prompt,
            task.model
        )

        if success:
            logger.info(f"✅ Task {task_num}/{total_tasks} completed successfully: {task.name}")
        else:
            logger.error(f"❌ Task {task_num}/{total_tasks} failed: {task.name}")
            if error_type:
                logger.error(f"   Error type: {error_type}")

        return success, output, error_type

    except Exception as e:
        logger.error(f"❌ Task {task_num}/{total_tasks} failed with exception: {task.name}")
        logger.error(f"   Exception: {str(e)}")
        return False, str(e), 'generic'


async def execute_claude_prompt(prompt: str, model: str = "sonnet") -> Tuple[bool, str, Optional[str]]:
    """Execute a Claude prompt and return the result.

    Args:
        prompt: The prompt to send to Claude
        model: The model to use (sonnet, opus, haiku)

    Returns:
        Tuple of (success: bool, output: str, error_type: Optional[str])
    """
    try:
        # Escape double quotes in prompt
        escaped_prompt = prompt.replace('"', '\\"').replace('$', '\\$')

        cmd = f'claude --model {model} -p "{escaped_prompt}"'

        logger.debug(f"Executing command: claude --model {model} -p [prompt]")

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

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


def get_execution_order(
    tasks: List[TaskConfig],
    dependency_graph: Dict[str, Set[str]]
) -> List[List[TaskConfig]]:
    """Get execution order for tasks based on dependencies.

    Returns a list of task batches. Tasks in the same batch can be executed in parallel.

    Args:
        tasks: List of TaskConfig objects
        dependency_graph: Dependency graph from build_dependency_graph

    Returns:
        List of task batches (each batch is a list of tasks that can run in parallel)
    """
    logger.info("📊 Calculating execution order...")

    task_map = {task.name: task for task in tasks}
    completed = set()
    batches = []

    while len(completed) < len(tasks):
        # Find tasks that can be executed (all dependencies completed)
        ready = []
        for task in tasks:
            if task.name not in completed:
                deps = dependency_graph.get(task.name, set())
                if deps.issubset(completed):
                    ready.append(task)

        if not ready:
            raise ValueError("Deadlock detected - no tasks can proceed")

        batches.append(ready)
        completed.update(task.name for task in ready)

    logger.info(f"✅ Execution order calculated: {len(batches)} batch(es)")
    for i, batch in enumerate(batches, 1):
        logger.info(f"   Batch {i}: {[task.name for task in batch]}")

    return batches


async def run_autoagent(
    file_path: Path,
    verbose: bool,
    force_sequential: bool = False
):
    """Run all tasks from autoagent configuration file.

    Args:
        file_path: Path to YAML configuration file
        verbose: Whether to show verbose output
        force_sequential: Force sequential execution even if tasks can run in parallel
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
    click.echo(f"   Execution Mode: {config.defaults.get('execution_mode', 'sequential')}")
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

    # Determine execution mode
    execution_mode = config.defaults.get('execution_mode', 'sequential')
    if force_sequential:
        execution_mode = 'sequential'
        logger.info("Forced sequential execution mode")

    abort_on_failure = config.defaults.get('abort_on_failure', True)

    try:
        if execution_mode == 'parallel':
            # Get batches for parallel execution
            batches = get_execution_order(tasks, dependency_graph)
            await run_parallel_execution(
                batches,
                verbose,
                abort_on_failure
            )
        else:
            # Sequential execution
            await run_sequential_execution(
                tasks,
                verbose,
                abort_on_failure
            )

        click.echo(click.style(f"\n{'='*80}", fg="green"))
        click.echo(click.style(f"✨ AutoAgent completed all task(s)!", fg="green", bold=True))
        click.echo(click.style(f"{'='*80}", fg="green"))

    except TaskAbortException as e:
        logger.error(f"Task execution aborted: {e}")
        click.echo(click.style(f"\n{'='*80}", fg="red"))
        click.echo(click.style(f"🛑 AutoAgent aborted: {e}", fg="red", bold=True))
        click.echo(click.style(f"{'='*80}", fg="red"))
        sys.exit(1)


async def run_sequential_execution(
    tasks: List[TaskConfig],
    verbose: bool,
    abort_on_failure: bool
):
    """Run tasks sequentially.

    Args:
        tasks: List of tasks to execute
        verbose: Whether to show verbose output
        abort_on_failure: Whether to abort on task failure
    """
    logger.info(f"▶️  Starting sequential execution of {len(tasks)} task(s)")

    for i, task in enumerate(tasks, 1):
        click.echo(click.style(f"\n{'='*80}", fg="cyan"))
        click.echo(click.style(f"Task {i}/{len(tasks)}: {task.name}", fg="cyan", bold=True))
        click.echo(click.style(f"{'='*80}", fg="cyan"))

        success, output, error_type = await execute_task(task, i, len(tasks), verbose)

        if success:
            click.echo(click.style(f"\n✅ Task completed successfully!", fg="green", bold=True))
            if verbose or len(output) < 500:
                click.echo(click.style(f"\n📤 Output:", fg="blue"))
                click.echo(output)
        else:
            click.echo(click.style(f"\n❌ Task failed!", fg="red", bold=True))
            click.echo(click.style(f"Error: {output}", fg="red"))

            # Check if we should abort
            if error_type == 'rate_limit':
                logger.error("Rate limit exceeded - aborting all tasks")
                raise TaskAbortException("Rate limit exceeded")

            if abort_on_failure:
                logger.error("Task failed and abort_on_failure is True - aborting")
                raise TaskAbortException(f"Task '{task.name}' failed")

            # Ask user if they want to continue
            if i < len(tasks):
                if not click.confirm(
                    click.style("\n⚠️  Continue with next task?", fg="yellow"),
                    default=True
                ):
                    logger.info("User chose to stop execution")
                    raise TaskAbortException("Stopped by user")


async def run_parallel_execution(
    batches: List[List[TaskConfig]],
    verbose: bool,
    abort_on_failure: bool
):
    """Run tasks in parallel batches.

    Args:
        batches: List of task batches (tasks in same batch run in parallel)
        verbose: Whether to show verbose output
        abort_on_failure: Whether to abort on task failure
    """
    total_tasks = sum(len(batch) for batch in batches)
    logger.info(f"⚡ Starting parallel execution of {total_tasks} task(s) in {len(batches)} batch(es)")

    completed_count = 0

    for batch_num, batch in enumerate(batches, 1):
        click.echo(click.style(f"\n{'='*80}", fg="cyan"))
        click.echo(click.style(
            f"Batch {batch_num}/{len(batches)}: {len(batch)} task(s) in parallel",
            fg="cyan",
            bold=True
        ))
        click.echo(click.style(f"Tasks: {[task.name for task in batch]}", fg="cyan"))
        click.echo(click.style(f"{'='*80}", fg="cyan"))

        # Execute all tasks in this batch concurrently
        results = await asyncio.gather(
            *[
                execute_task(task, completed_count + i + 1, total_tasks, verbose)
                for i, task in enumerate(batch)
            ],
            return_exceptions=True
        )

        # Process results
        for i, (task, result) in enumerate(zip(batch, results)):
            click.echo(click.style(f"\n--- Task: {task.name} ---", fg="blue"))

            if isinstance(result, Exception):
                click.echo(click.style(f"❌ Task failed with exception!", fg="red", bold=True))
                click.echo(click.style(f"Error: {str(result)}", fg="red"))

                if abort_on_failure:
                    logger.error(f"Task '{task.name}' failed - aborting")
                    raise TaskAbortException(f"Task '{task.name}' failed with exception")
            else:
                success, output, error_type = result

                if success:
                    click.echo(click.style(f"✅ Task completed successfully!", fg="green", bold=True))
                    if verbose or len(output) < 500:
                        click.echo(click.style(f"\n📤 Output:", fg="blue"))
                        click.echo(output)
                else:
                    click.echo(click.style(f"❌ Task failed!", fg="red", bold=True))
                    click.echo(click.style(f"Error: {output}", fg="red"))

                    # Check for critical errors
                    if error_type == 'rate_limit':
                        logger.error("Rate limit exceeded - aborting all tasks")
                        raise TaskAbortException("Rate limit exceeded")

                    if abort_on_failure:
                        logger.error(f"Task '{task.name}' failed - aborting")
                        raise TaskAbortException(f"Task '{task.name}' failed")

        completed_count += len(batch)


@click.command(name="autoagent")
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=False, path_type=Path),
    default="autoagent.yaml",
    help="Path to autoagent YAML configuration file (default: autoagent.yaml)"
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed output and prompts"
)
@click.option(
    "--sequential",
    "-s",
    is_flag=True,
    help="Force sequential execution (ignore parallel mode in config)"
)
def autoagent(file, verbose, sequential):
    """Execute tasks from autoagent.yaml configuration file.

    The autoagent.yaml file defines tasks with their prompts, models, dependencies,
    and execution strategy. See autoagent.yaml.example for the format.

    Features:
    - Sequential or parallel execution
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
    asyncio.run(run_autoagent(file, verbose, sequential))
