#!/bin/bash
# Stop hook: Run tests before allowing Claude to stop
# This ensures all tests are passing before ending the session
# Maximum 3 iterations to prevent infinite loops

set -e

# Track iteration count using a temporary file
COUNTER_FILE="/tmp/claude_stop_hook_counter_$$"
MAX_ITERATIONS=3

# Initialize or increment counter
if [ -f "$COUNTER_FILE" ]; then
    CURRENT_ITERATION=$(cat "$COUNTER_FILE")
    CURRENT_ITERATION=$((CURRENT_ITERATION + 1))
else
    CURRENT_ITERATION=1
fi
echo "$CURRENT_ITERATION" > "$COUNTER_FILE"

echo "============================================"
echo "Running tests before stopping Claude... (Attempt $CURRENT_ITERATION/$MAX_ITERATIONS)"
echo "============================================"

# Change to project root
cd "$(dirname "$0")/../.."

# Run pytest with verbose output
if python3.12 -m pytest tests/ -v --tb=short; then
    echo ""
    echo "============================================"
    echo "✓ All tests passed! Safe to stop."
    echo "============================================"
    # Clean up counter file on success
    rm -f "$COUNTER_FILE"
    exit 0
else
    echo ""
    echo "============================================"
    echo "✗ Tests failed! Please fix the issues before stopping."
    echo "============================================"
    echo ""

    # Check if we've exceeded max iterations
    if [ "$CURRENT_ITERATION" -ge "$MAX_ITERATIONS" ]; then
        echo "⚠️  WARNING: Reached maximum retry attempts ($MAX_ITERATIONS)."
        echo "Allowing stop despite test failures to prevent infinite loop."
        echo ""
        # Clean up counter file
        rm -f "$COUNTER_FILE"
        exit 0
    fi

    echo "Common fixes:"
    echo "1. Review the test output above for specific failures"
    echo "2. Fix any coding issues in the implementation"
    echo "3. Update tests if the behavior change is intentional"
    echo "4. Run 'python3.12 -m pytest tests/ -v' to verify fixes"
    echo ""
    echo "Retry attempts remaining: $((MAX_ITERATIONS - CURRENT_ITERATION))"
    echo ""
    exit 1
fi
