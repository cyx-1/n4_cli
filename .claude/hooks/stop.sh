#!/bin/bash
# Stop hook: Run tests before allowing Claude to stop
# This ensures all tests are passing before ending the session

set -e

echo "============================================"
echo "Running tests before stopping Claude..."
echo "============================================"

# Change to project root
cd "$(dirname "$0")/../.."

# Run pytest with verbose output
if python3.12 -m pytest tests/ -v --tb=short; then
    echo ""
    echo "============================================"
    echo "✓ All tests passed! Safe to stop."
    echo "============================================"
    exit 0
else
    echo ""
    echo "============================================"
    echo "✗ Tests failed! Please fix the issues before stopping."
    echo "============================================"
    echo ""
    echo "Common fixes:"
    echo "1. Review the test output above for specific failures"
    echo "2. Fix any coding issues in the implementation"
    echo "3. Update tests if the behavior change is intentional"
    echo "4. Run 'python3.12 -m pytest tests/ -v' to verify fixes"
    echo ""
    exit 1
fi
