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

### Multi-Repository Management

The `multi-repo` command enables parallel async operations across multiple git repositories:

```bash
# Check status of all repos in current directory
n4_cli multi-repo

# Check all repos recursively
n4_cli multi-repo -p ~/projects -r

# Show all repos including clean ones
n4_cli multi-repo -v

# Interactive mode - walk through available actions and execute
n4_cli multi-repo --action
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