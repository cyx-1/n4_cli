# Agent Instructions for n4_cli

## Project Overview

**n4_cli** is a modular command-line tool written in Python that provides various utilities for developers. The project features an interactive command selection interface with fuzzy search and typeahead completion.

### Key Features

- **Interactive CLI**: Dynamic command selection with fuzzy matching and keyboard navigation
- **Git Repository Management**: Parallel async operations across multiple git repositories
  - Status checking across multiple repos simultaneously
  - Batch operations (push, pull, prune merged branches)
  - AI-generated commit messages
  - Conflict detection and auto-retry with exponential backoff
- **Modular Architecture**: Commands are auto-loaded from the `n4_cli/commands` directory
- **Text Processing Utilities**: Various text manipulation commands (beautify, trim, flatten, etc.)

## Development Environment

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) - Modern Python package manager

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd n4_cli

# Install dependencies using uv
uv sync

# Run the CLI
uv run n4_cli
```

## Package Management with uv

**CRITICAL**: This project uses `uv` for dependency management. **DO NOT use pip or requirements.txt**.

### Adding Dependencies

To add a new package dependency:

```bash
# Add a runtime dependency
uv add <package-name>

# Add a development dependency
uv add --dev <package-name>

# Examples:
uv add requests
uv add --dev pytest-cov
```

### Project Dependencies

Current dependencies are managed in `pyproject.toml`:

**Runtime dependencies:**
- click (CLI framework)
- prompt-toolkit (interactive UI)
- pyperclip (clipboard operations)
- pyyaml (YAML parsing)
- questionary (interactive prompts)
- requests (HTTP requests)
- rich (rich text formatting)

**Development dependencies:**
- pytest (testing framework)
- pytest-asyncio (async test support)
- pytest-mock (mocking utilities)

## Testing Requirements

**CRITICAL**: Always run tests before committing changes.

```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_git_service.py

# Run tests with coverage
uv run pytest --cov=n4_cli
```

### Testing Best Practices

1. **Always run tests after making changes** - This is non-negotiable
2. **All tests must pass** - Do not commit if tests are failing
3. **Write tests for new features** - Keep test coverage high
4. **Use pytest fixtures** - For shared test setup
5. **Mock external dependencies** - Use pytest-mock for git operations, network calls, etc.

### Test Configuration

Tests are configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
```

## Project Structure

```
n4_cli/
├── n4_cli/
│   ├── __init__.py
│   ├── main.py                      # CLI entry point & interactive mode
│   ├── git_service.py               # Git operations abstraction
│   ├── text_processor.py            # Text processing utilities
│   ├── assets/                      # Static assets (HTML, etc.)
│   └── commands/                    # Command modules (auto-loaded)
│       ├── __init__.py
│       ├── git_check/               # Git repository checker (subpackage)
│       │   ├── __init__.py
│       │   ├── actions.py           # Action executors (push/pull/prune)
│       │   ├── checker.py           # Repository status checking
│       │   ├── cli.py               # CLI command definition
│       │   ├── commit_message.py    # AI commit message generation
│       │   ├── display.py           # Output formatting
│       │   ├── interactive.py       # Interactive selection UI
│       │   └── models.py            # Data models
│       ├── beautify_text.py
│       ├── claude_code.py
│       ├── clipboard.py
│       ├── codex.py
│       ├── convert_slash.py
│       ├── fetch.py
│       ├── flatten_lines_add_quotes.py
│       ├── git_merge_latest.py
│       ├── github_copilot_cli.py
│       ├── remove_blanks.py
│       └── trim_lines.py
├── tests/
│   ├── __init__.py
│   ├── test_git_service.py
│   └── test_multi_repo.py
├── pyproject.toml                   # Project config & dependencies
├── uv.lock                          # Dependency lock file
└── README.md
```

## Adding New Commands

Commands are automatically discovered and loaded. To add a new command:

1. Create a new file in `n4_cli/commands/`
2. Define a Click command using `@click.command()`
3. Add a docstring (first line becomes the description in interactive mode)
4. The command will be auto-loaded and available

**Example:**

```python
import click

@click.command(name="my-command")
def my_command():
    """Short description shown in interactive mode.

    Longer description with more details about what the command does.
    """
    click.echo("Hello from my command!")
```

### Complex Commands (Subpackages)

For complex commands like `git-check`, create a subpackage:

1. Create directory: `n4_cli/commands/my_feature/`
2. Add `__init__.py` with command export
3. Structure code into logical modules (cli.py, actions.py, models.py, etc.)
4. Export the main command in `__init__.py`

## Coding Guidelines

### General Principles

1. **Use async/await for I/O operations** - Especially for git operations across multiple repos
2. **Rich terminal output** - Use click.style() and rich library for colored output
3. **Error handling** - Handle git errors gracefully, skip problematic repos with warnings
4. **Type hints** - Use type annotations for better code clarity
5. **Docstrings** - Document all functions and commands

### Git Operations

- Use `git_service.py` abstraction for all git operations
- Operations should be async for parallel execution
- Implement retry logic with exponential backoff for network operations
- Always check for merge conflicts before operations

### Interactive UI

- Use `prompt_toolkit` for rich interactive interfaces
- Support both keyboard navigation and number selection
- Provide clear feedback and confirmation prompts
- Support Ctrl+C gracefully

### Code Style

Follow standard Python conventions:
- PEP 8 style guide
- 4 spaces for indentation
- Max line length: 120 characters
- Descriptive variable names
- Use module level import at top section of a python file instead of lazy loading of import

## Common Development Tasks

### Running the CLI Locally

```bash
# Run the main CLI
uv run n4_cli

# Run a specific command
uv run n4_cli git-check
uv run n4_cli git-check --help

# Run in development mode (with auto-reload)
uv run python -m n4_cli.main
```

### Debugging

```bash
# Run with Python debugger
uv run python -m pdb -m n4_cli.main

# Run specific command with verbose output
uv run n4_cli git-check -v
```

### Installing Locally for Testing

```bash
# Install in development mode
uv pip install -e .

# Or use as a tool
uv tool install .
```

## Git Workflow

1. Create a feature branch
2. Make your changes
3. **Run tests**: `uv run pytest`
4. Commit your changes
5. Push and create a pull request

## Common Issues

### Issue: Tests fail with import errors
**Solution**: Run `uv sync` to ensure all dependencies are installed

### Issue: Command not showing up in interactive mode
**Solution**: Check that your command file is in `n4_cli/commands/` and has a proper Click command decorator

### Issue: Git operations timing out
**Solution**: Check the retry logic in git_service.py - it should have exponential backoff

## Additional Resources

- [Click Documentation](https://click.palletsprojects.com/)
- [prompt-toolkit Documentation](https://python-prompt-toolkit.readthedocs.io/)
- [uv Documentation](https://github.com/astral-sh/uv)
- [pytest Documentation](https://docs.pytest.org/)

## Contact & Support

For issues or questions, refer to the project's GitHub repository.

---

**Remember**:
- ✅ Use `uv` for all package management
- ✅ Always run `uv run pytest` before committing
- ❌ Never use pip or requirements.txt
- ❌ Never commit failing tests
