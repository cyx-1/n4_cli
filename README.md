# n4_cli

A simple CLI tool for clipboard operations.

## Features

- **test.py**: A script that reads content from the system clipboard and echoes it to the console.

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install dependencies
uv sync
```

## Usage

### test.py - Clipboard Echo

Copy any text to your clipboard, then run:

```bash
uv run python test.py
```

The script will read from your clipboard and print the content to the console.

## Requirements

- Python 3.12+
- pyperclip (automatically installed via uv)
- On Linux: xclip, xsel, or wl-clipboard for clipboard support