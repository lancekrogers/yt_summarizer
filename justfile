#!/usr/bin/env just --justfile
# YouTube Summarizer - CLI tool for batch YouTube transcript summarization

set dotenv-load := true

# Configuration
package_name := "yt-summarizer"
config_dir := "~/.config/youtube-summarizer"

# Modules
[doc('Development tasks (run, watch)')]
mod dev '.justfiles/dev.just'

[doc('Testing (pytest, coverage)')]
mod test '.justfiles/test.just'

[doc('Installation (poetry, pipx)')]
mod install '.justfiles/install.just'

[doc('Code quality (lint, format, type-check)')]
mod lint '.justfiles/lint.just'

[private]
default:
    #!/usr/bin/env bash
    echo "📼→📝 YouTube Summarizer"
    echo ""
    just --list --unsorted

# Run interactive CLI
run *ARGS:
    poetry run yt-summarizer {{ARGS}}

# Quick start: install deps and run
start: deps run

# Install/update dependencies
deps:
    poetry install

# Update dependencies to latest versions
update:
    poetry update
    poetry lock

# Clean build artifacts and caches
clean:
    rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache .coverage coverage.xml htmlcov/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Show current configuration paths
config:
    @echo "Config directory: {{config_dir}}"
    @echo ""
    @if [ -d {{config_dir}} ]; then \
        echo "Contents:"; \
        ls -la {{config_dir}}; \
    else \
        echo "Config directory does not exist yet. Run 'just run' to create it."; \
    fi

# Open config file in editor
config-edit:
    ${EDITOR:-vim} {{config_dir}}/config.yaml

# Reset configuration (removes config directory)
config-reset:
    #!/usr/bin/env bash
    read -p "This will delete {{config_dir}}. Continue? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf {{config_dir}}
        echo "Configuration reset. Run 'just run' to create fresh config."
    fi
