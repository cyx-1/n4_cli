"""Git repository checker - parallel async operations across multiple git repositories.

This module has been refactored into the git_check package for better organization.
All functionality is now available through the git_check package.
"""

# Import the main command from the refactored package
from .git_check import git_check

__all__ = ["git_check"]
