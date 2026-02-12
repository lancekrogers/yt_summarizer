# Development recipes

# Show available dev commands
[private]
default:
    @just --list --unsorted --justfile {{source_file()}}

# Run interactive CLI
[no-cd]
run *ARGS:
    uv run yt-summarizer {{ARGS}}

# Run with specific video URL
[no-cd]
video URL:
    uv run yt-summarizer --interactive <<< $'1\n2\n{{URL}}\n'

# Run with video list file
[no-cd]
batch FILE:
    uv run yt-summarizer {{FILE}}

# Run with custom model
[no-cd]
model MODEL *ARGS:
    OLLAMA_MODEL={{MODEL}} uv run yt-summarizer {{ARGS}}

# Start Python REPL with project imports
[no-cd]
repl:
    uv run python -c "from yt_summarizer import *; import code; code.interact(local=locals())"

# Watch for changes and run tests (requires pytest-watch)
[no-cd]
watch:
    uv run ptw --clear -- -v

# Show Ollama status and available models
[no-cd]
ollama-status:
    @echo "Ollama Status:"
    @curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print('Models:', ', '.join(m['name'] for m in d.get('models',[])))" 2>/dev/null || echo "Ollama not running. Start with: ollama serve"

# Pull a model for use with summarizer
[no-cd]
ollama-pull MODEL="llama3.2:latest":
    ollama pull {{MODEL}}
