# n4_cli

A simple CLI tool for clipboard operations.

## Quick Start

Run directly from GitHub using [uv](https://github.com/astral-sh/uv):

```bash
uvx --from git+https://github.com/cyx-1/n4_cli n4_cli
```

It is a good idea to set up an alias:

```
# ~/zshrc
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

## Requirements

- Python 3.12+
- pyperclip (automatically installed via uv)