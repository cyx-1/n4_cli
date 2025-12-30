# n4_cli

A simple CLI tool for various operations.

## Installation

Install using [uv](https://github.com/astral-sh/uv):

```bash
uv tool install git+https://github.com/cyx-1/n4_cli
```

Add these aliases to your shell configuration:

```bash
# ~/.zshrc or ~/.bashrc
alias n4="n4_cli"
alias n4-update="uv tool install --force git+https://github.com/cyx-1/n4_cli"
```

## Quick Start

Alternatively, run directly from GitHub without installation:

```bash
uvx --from git+https://github.com/cyx-1/n4_cli n4_cli
```

## Development

If you want to develop locally:

```bash
# Install dependencies
uv sync

# Run the CLI
uv run n4_cli
```

## Key Features

### AutoAgent - Advanced Task Automation

The `autoagent` command executes tasks from a YAML configuration file using Claude CLI with support for parallel execution, dependencies, and branch management:

```bash
# Run tasks from autoagent.yaml (default)
n4_cli autoagent

# Use a custom file
n4_cli autoagent --file my-tasks.yaml

# Force sequential execution
n4_cli autoagent --sequential

# Show detailed output and prompts
n4_cli autoagent --verbose
```

**Configuration Format:**
Create an `autoagent.yaml` file (see `autoagent.yaml.example` for a complete example):

```yaml
version: "1.0"

defaults:
  model: sonnet              # sonnet, opus, haiku
  agent: claude              # claude, codex
  execution_mode: sequential # sequential or parallel
  branch_strategy: separate  # separate or main
  auto_push: false          # push to remote after success
  abort_on_failure: true    # abort all tasks on failure

tasks:
  - name: Check Python version
    prompt: |
      What version of Python is recommended for this project?
      Check the pyproject.toml file.
    model: opus  # override default

  - name: List CLI commands
    prompt: "List all available CLI commands"
    branch: feature/cli-commands

  - name: Suggest improvements
    prompt: "Review and suggest improvements"
    depends_on:
      - List CLI commands  # waits for this task
    share_branch_with: List CLI commands
    auto_push: true
```

**Features:**
- ⚡ **Parallel execution** - run independent tasks simultaneously
- 🔗 **Task dependencies** - define which tasks must complete before others
- 🤖 **Multiple AI models** - choose between sonnet, opus, or haiku per task
- 🌿 **Branch management** - automatic branch creation and sharing
- 🚀 **Auto-push** - optionally push changes to remote after completion
- ⚠️ **Smart error handling** - auto-abort on rate limits, configurable failure behavior
- 📊 **Comprehensive logging** - detailed execution logs with timestamps
- 🛑 **Abort mechanism** - tasks can abort the entire operation (e.g., rate limits)
- ✅ **Circular dependency detection** - validates task dependencies before execution

### Git Repository Checker

The `git-check` command enables parallel async operations across multiple git repositories:

```bash
# Check status of all repos in current directory
n4_cli git-check

# Check all repos recursively
n4_cli git-check -p ~/projects -r

# Show all repos including clean ones
n4_cli git-check -v

# Interactive mode - walk through available actions and execute
n4_cli git-check --action
```

**Features:**
- 🚀 **Parallel async execution** - all repositories checked simultaneously
- 📝 **File enumeration** - lists all changed/uncommitted files
- 🔄 **Branch tracking** - shows branches behind remote with commit count
- 🗑️ **Merged branch detection** - identifies branches merged to main/master
- ✅ **Action confirmation** - clear review before executing batch operations
- ⚠️ **Conflict handling** - skips repos with merge conflicts for manual resolution
- 🔁 **Auto-retry** - exponential backoff for network failures (2s, 4s, 8s, 16s)

## Requirements

- Python 3.12+
- pyperclip (automatically installed via uv)