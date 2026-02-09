# Code quality recipes

src_dir := "src/yt_summarizer"
test_dir := "tests"

# Show available lint commands
[private]
default:
    @just --list --unsorted --justfile {{source_file()}}

# Run all linting and formatting checks
[no-cd]
all: format check types
    @echo "✅ All checks passed"

# Format code with black
[no-cd]
format:
    uv run black {{src_dir}} {{test_dir}}

# Check formatting without changes
[no-cd]
format-check:
    uv run black --check {{src_dir}} {{test_dir}}

# Run type checking with mypy
[no-cd]
types:
    uv run mypy {{src_dir}}

# Run type checking with verbose output
[no-cd]
types-verbose:
    uv run mypy {{src_dir}} --show-error-codes --pretty

# Run all checks (format + types) without modifications
[no-cd]
check: format-check types
    @echo "✅ All checks passed"

# Fix common issues automatically
[no-cd]
fix: format
    @echo "✅ Auto-fixes applied"

# Show code statistics
[no-cd]
stats:
    @echo "=== Code Statistics ==="
    @echo "Source files:"
    @find {{src_dir}} -name "*.py" | wc -l | xargs echo "  Python files:"
    @find {{src_dir}} -name "*.py" -exec cat {} \; | wc -l | xargs echo "  Lines of code:"
    @echo ""
    @echo "Test files:"
    @find {{test_dir}} -name "*.py" | wc -l | xargs echo "  Test files:"
    @find {{test_dir}} -name "*.py" -exec cat {} \; | wc -l | xargs echo "  Lines of tests:"
