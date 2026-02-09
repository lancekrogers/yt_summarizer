# Installation recipes

package_name := "yt-summarizer"

# Show available install commands
[private]
default:
    @just --list --unsorted --justfile {{source_file()}}

# Install for development (editable)
[no-cd]
dev:
    uv sync

# Install system-wide via pipx (recommended)
[no-cd]
pipx:
    pipx install --force .
    @echo "✅ {{package_name}} installed via pipx"
    @echo "Run 'yt-summarizer' from anywhere"

# Install via pipx in editable mode
[no-cd]
pipx-dev:
    pipx install --force -e .
    @echo "✅ {{package_name}} installed via pipx (editable)"

# Uninstall from pipx
[no-cd]
pipx-uninstall:
    pipx uninstall {{package_name}}

# Install via pip (user install)
[no-cd]
pip:
    pip install --user .
    @echo "✅ {{package_name}} installed via pip --user"
    @echo "Ensure ~/.local/bin is in your PATH"

# Install via pip in editable mode
[no-cd]
pip-dev:
    pip install --user -e .
    @echo "✅ {{package_name}} installed via pip --user (editable)"

# Uninstall from pip
[no-cd]
pip-uninstall:
    pip uninstall {{package_name}}

# Build distribution packages
[no-cd]
build:
    uv build
    @echo "✅ Built packages in dist/"
    @ls -la dist/

# Publish to PyPI (requires auth)
[no-cd]
publish:
    uv publish

# Check if installed and show version
[no-cd]
check:
    @which yt-summarizer && yt-summarizer --help || echo "yt-summarizer not found in PATH"
