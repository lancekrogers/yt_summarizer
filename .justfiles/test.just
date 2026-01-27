# Testing recipes

# Show available test commands
[private]
default:
    @just --list --unsorted --justfile {{source_file()}}

# Run all tests
[no-cd]
all:
    poetry run pytest

# Run tests with verbose output
[no-cd]
verbose:
    poetry run pytest -v

# Run tests with extra verbose output
[no-cd]
vv:
    poetry run pytest -vv

# Run specific test file
[no-cd]
file FILE:
    poetry run pytest {{FILE}} -v

# Run tests matching pattern
[no-cd]
match PATTERN:
    poetry run pytest -k "{{PATTERN}}" -v

# Run tests with coverage report
[no-cd]
coverage:
    poetry run pytest --cov=yt_summarizer --cov-report=term-missing

# Generate HTML coverage report
[no-cd]
coverage-html:
    poetry run pytest --cov=yt_summarizer --cov-report=html
    @echo "Coverage report: htmlcov/index.html"

# Run tests and stop on first failure
[no-cd]
fail-fast:
    poetry run pytest -x

# Run only failed tests from last run
[no-cd]
failed:
    poetry run pytest --lf

# Run tests in parallel (requires pytest-xdist)
[no-cd]
parallel:
    poetry run pytest -n auto

# Watch for changes and run tests
[no-cd]
watch:
    poetry run ptw --clear -- -v
