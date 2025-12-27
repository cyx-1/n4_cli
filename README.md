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

## Requirements

- Python 3.12+
- pyperclip (automatically installed via uv)