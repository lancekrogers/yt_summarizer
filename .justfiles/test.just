# Testing recipes

# Show available test commands
[private]
default:
    @just --list --unsorted --justfile {{source_file()}}

# Run all tests
[no-cd]
all:
    uv run pytest

# Run tests with verbose output
[no-cd]
verbose:
    uv run pytest -v

# Run tests with extra verbose output
[no-cd]
vv:
    uv run pytest -vv

# Run specific test file
[no-cd]
file FILE:
    uv run pytest {{FILE}} -v

# Run tests matching pattern
[no-cd]
match PATTERN:
    uv run pytest -k "{{PATTERN}}" -v

# Run tests with coverage report
[no-cd]
coverage:
    uv run pytest --cov=yt_summarizer --cov-report=term-missing

# Generate HTML coverage report
[no-cd]
coverage-html:
    uv run pytest --cov=yt_summarizer --cov-report=html
    @echo "Coverage report: htmlcov/index.html"

# Run tests and stop on first failure
[no-cd]
fail-fast:
    uv run pytest -x

# Run only failed tests from last run
[no-cd]
failed:
    uv run pytest --lf

# Run tests in parallel (requires pytest-xdist)
[no-cd]
parallel:
    uv run pytest -n auto

# Watch for changes and run tests
[no-cd]
watch:
    uv run ptw --clear -- -v
