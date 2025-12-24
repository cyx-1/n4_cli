#!/usr/bin/env python3
"""
Simple script that reads from clipboard and echoes it to the console.
"""

import pyperclip


def main():
    """Read clipboard content and print it to console."""
    clipboard_content = pyperclip.paste()
    print(clipboard_content)


if __name__ == "__main__":
    main()
