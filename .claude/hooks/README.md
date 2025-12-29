# Claude Code Hooks

This directory contains hooks that are executed at various points during Claude Code sessions.

## Available Hooks

### stop.sh

**Purpose**: Automatically run all tests before allowing Claude to stop the session.

**Behavior**:
- Runs the full test suite using pytest
- If all tests pass, allows Claude to stop normally
- If any tests fail, prevents stopping and displays:
  - Detailed test failure information
  - Suggestions for common fixes
  - Instructions to run tests manually

**Usage**: This hook runs automatically when Claude attempts to stop. No manual intervention is required.

**Benefits**:
- Ensures code quality before ending a session
- Catches regressions early
- Provides immediate feedback on test failures
- Prevents accidentally leaving broken code

## Running Hooks Manually

You can test any hook manually by executing it directly:

```bash
./.claude/hooks/stop.sh
```

## Hook Requirements

- Hooks must be executable (`chmod +x hook.sh`)
- Hooks should exit with code 0 for success, non-zero for failure
- Hooks have access to the project root directory
