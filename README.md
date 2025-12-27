# n4_cli

A simple CLI tool for various operations.

## Quick Start

Run directly from GitHub using [uv](https://github.com/astral-sh/uv):

```bash
uvx --from git+https://github.com/cyx-1/n4_cli n4_cli
```

It is a good idea to set up an alias:

```
# ~/.zshrc or ~/.bashrc
alias n4="uvx --from git+https://github.com/cyx-1/n4_cli n4_cli"
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

# Commit and push changes to all repos with uncommitted files
n4_cli multi-repo --action push

# Pull all branches that are behind remote
n4_cli multi-repo --action pull

# Delete merged branches
n4_cli multi-repo --action prune
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