# YouTube Summarizer

A CLI tool that fetches YouTube video transcripts and generates concise summaries using local LLM models via Ollama. Supports both an interactive TUI and a pure CLI mode for scripting.

## Features

| Feature                  | Description                                                      |
| ------------------------ | ---------------------------------------------------------------- |
| **Local Processing**     | No API keys required — uses Ollama for 100% local LLM inference  |
| **Research Plans**       | Focused content extraction with corpus aggregation and analysis  |
| **Interactive TUI**      | Guided terminal interface for video processing and plan creation |
| **Pure CLI Mode**        | Scriptable subcommands for automation and pipelines              |
| **Smart Transcripts**    | Prefers manual captions, falls back to auto-generated            |
| **Multiple Inputs**      | Supports `.txt`, `.list`, `.urls`, `.csv` files, or single URLs  |
| **Intelligent Chunking** | Splits long transcripts for high-quality summaries               |
| **Transcript Caching**   | Avoids re-downloading transcripts across runs                    |
| **XDG Configuration**    | Cross-platform config with layered priority (env > YAML > defaults) |
| **Custom Output Paths**  | Write summaries to any directory with `-o`                       |

---

## Prerequisites

- **Python** >= 3.11, < 3.14
- **uv** for dependency management
- **Ollama** runtime (CPU or GPU)

Everything runs locally once transcripts are cached — no external API keys needed.

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/lancekrogers/youtube-summarizer.git
cd youtube-summarizer

# Install dependencies
uv sync

# Allow direnv (if using)
direnv allow
```

### 2. Set up Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model and start the server
ollama pull llama3.2:latest
ollama serve
```

### 3. Run

```bash
# Interactive TUI
uv run yt-summarizer

# Summarize a single video
uv run yt-summarizer summarize https://youtube.com/watch?v=VIDEO_ID

# Batch from file
uv run yt-summarizer summarize -f videos.txt
```

---

## CLI Reference

### Interactive mode (default)

```bash
uv run yt-summarizer
```

Launches the TUI with menus for video processing, research plans, and cache management.

### `summarize` — process videos

```bash
uv run yt-summarizer summarize <url>                  # Single video
uv run yt-summarizer summarize <url> -o ./output/     # Custom output directory
uv run yt-summarizer summarize -f videos.txt          # Batch from file
uv run yt-summarizer summarize <url> -f more.txt      # URL + file combined
uv run yt-summarizer summarize -f list.txt --overwrite # Overwrite existing summaries
```

| Flag             | Description                          |
| ---------------- | ------------------------------------ |
| `<url>`          | YouTube URL or video ID              |
| `-f`, `--file`   | Text file with video URLs            |
| `-o`, `--output` | Output directory for summaries       |
| `-m`, `--model`  | Ollama model name                    |
| `--no-cache`     | Disable transcript cache             |
| `--overwrite`    | Overwrite existing summary files     |

### `plan` — research plans

```bash
uv run yt-summarizer plan list                                   # List plans
uv run yt-summarizer plan run <plan-id>                          # Run a plan
uv run yt-summarizer plan run <plan-id> -o ./out/                # Custom output
uv run yt-summarizer plan create --name "AI Research"            # Create a plan
uv run yt-summarizer plan create --name "AI" --url https://...   # Create with URLs
```

---

## Research Plans

The research plan system enables focused content extraction from YouTube videos with corpus aggregation and analysis.

### How it works

1. **Create a plan** — define your research focus and custom prompts
2. **Process videos** — extract targeted content using plan-specific prompts
3. **Aggregate corpus** — combine individual summaries into a unified document
4. **Analyze patterns** — identify themes and insights across videos

### Plan structure

Plans are stored as YAML files in the research plans directory:

```yaml
research_plan:
  name: "LLM Prompting Techniques"
  description: "Extract specific prompts from LLM-related videos"

videos:
  urls:
    - "https://www.youtube.com/watch?v=VIDEO_ID_1"
  list_file: "videolist.txt"  # Optional

prompts:
  chunk_prompt: |
    Extract only the specific prompts mentioned in this transcript:
    {chunk}

  executive_prompt: |
    Organize the extracted prompts from this video:
    {bullet_summaries}
```

### File organization

```
data/
  videos/              Individual video summaries
  corpus/              Research plan aggregations
    plan_name.md       Combined summaries
    plan_name_summary.md  Final analysis
  raw/                 Cached transcripts

research_plans/        Plan configurations
  my_research.yaml
```

---

## Supported File Formats

| Format  | Description                   | Example                                 |
| ------- | ----------------------------- | --------------------------------------- |
| `.txt`  | One URL/ID per line           | `dQw4w9WgXcQ`                           |
| `.list` | Video list files              | Same as `.txt`                          |
| `.urls` | URL files                     | Same as `.txt`                          |
| `.csv`  | CSV with URLs in first column | `url,title`                             |

Comments (`# comment`), auto header detection, video ID/URL validation, and UTF-8 encoding are all supported.

---

## Ollama Setup

| Step              | Command                                                                | Notes                          |
| ----------------- | ---------------------------------------------------------------------- | ------------------------------ |
| **Install**       | macOS: `brew install ollama` / Linux: `curl -fsSL https://ollama.ai/install.sh \| sh` | See [ollama.ai](https://ollama.ai) |
| **Pull Model**    | `ollama pull llama3.2:latest`                                          | Downloaded once, stored locally |
| **Start Server**  | `ollama serve`                                                         | Runs on port 11434             |
| **List Models**   | `ollama list`                                                          | See available models            |

Memory considerations:
- Use smaller models (`llama3.2:1b`, `phi3:mini`) for limited memory
- Set `OLLAMA_NO_GPU=1` for CPU-only processing
- Larger models produce better summaries

---

## Configuration

### XDG-compliant paths

Configuration lives at `~/.config/youtube-summarizer/config.yaml` by default (respects `XDG_CONFIG_HOME`). Data is stored under `~/.local/share/youtube-summarizer/` (respects `XDG_DATA_HOME`).

Run `just config` to view current paths, or `just config-edit` to open the config file.

### config.yaml

```yaml
# Ollama settings
ollama_url: http://localhost:11434
ollama_model: llama3.2:latest
ollama_timeout: 300

# Processing settings
context_window: 120000
chunk_size: 2048
chunk_overlap: 200
rate_limit_delay: 2.0

# YouTube settings
youtube_timeout: 30

# Default video list file name
default_video_list: videos.txt

# Directory overrides (uncomment to customize)
# data_dir: ~/Documents/youtube-summarizer/data
# docs_dir: ~/Documents/youtube-summarizer/docs
# logs_dir: ~/Documents/youtube-summarizer/logs
# research_plans_dir: ~/Documents/youtube-summarizer/research_plans
```

### Configuration priority

1. Environment variables (uppercase, e.g. `OLLAMA_MODEL`)
2. YAML config file
3. Built-in defaults

A `.env` file in the project root is also supported for backwards compatibility.

---

## Just Commands

The project uses a modular justfile system. Run `just` at the project root for the full menu.

| Command              | Description                        |
| -------------------- | ---------------------------------- |
| `just run`           | Run interactive CLI                |
| `just deps`          | Install/update dependencies        |
| `just clean`         | Clean build artifacts and caches   |
| `just config`        | Show current configuration paths   |
| `just config-edit`   | Open config file in editor         |
| `just dev run`       | Run CLI via dev module             |
| `just dev watch`     | Watch for changes and run tests    |
| `just test all`      | Run full test suite                |
| `just test coverage` | Run tests with coverage report     |
| `just lint all`      | Run formatting + type checks       |
| `just lint fix`      | Auto-fix formatting issues         |
| `just install dev`   | Install for development (editable) |
| `just install pipx`  | Install system-wide via pipx       |

---

## Project Structure

```
youtube-summarizer/
  src/yt_summarizer/       Main package
    cli.py                 Interactive TUI + CLI subcommands
    config.py              XDG-compliant configuration
    corpus.py              Research corpus aggregation
    llm.py                 Ollama integration
    pipeline.py            Processing orchestration
    research_plan.py       Research plan management
    transcript.py          YouTube transcript fetching
    utils.py               Utilities and markdown formatting
  tests/                   Test suite
  .justfiles/              Modular justfile recipes
    dev.just               Development commands
    test.just              Testing commands
    lint.just              Code quality commands
    install.just           Installation commands
  data/                    Generated content
  research_plans/          Research plan configurations
  logs/                    Processing logs
  justfile                 Root command runner
  pyproject.toml           Project metadata (hatchling build)
  .env.example             Configuration reference
```

---

## Output Format

Summaries are written as markdown with YAML frontmatter:

```yaml
---
video_id: dQw4w9WgXcQ
url: https://youtu.be/dQw4w9WgXcQ
title: "Never Gonna Give You Up"
saved: 2025-05-22T12:34:56Z
model: llama3.2:latest
chunk_count: 3
tags: [youtube, transcript]
---
```

Processing logs are written as JSONL to `logs/ingest.jsonl`.

---

## Testing

```bash
just test all              # Run full suite
just test coverage         # With coverage report
just test fail-fast        # Stop on first failure
just test watch            # Re-run on file changes

# Or directly:
uv run pytest
uv run pytest --cov=yt_summarizer --cov-report=term-missing
```

---

## Troubleshooting

| Issue                | Solution                                                   |
| -------------------- | ---------------------------------------------------------- |
| `NoTranscriptFound`  | Video has no public captions — try a different video        |
| `LLMConnectionError` | Start Ollama: `ollama serve`                               |
| `HTTP 404` from Ollama | Model not found: `ollama list` / `ollama pull <model>`   |
| Out of memory        | Use a smaller model (`llama3.2:1b`) or `OLLAMA_NO_GPU=1`   |
| Install fails        | Ensure Python 3.11-3.13 and uv are installed               |
| Rate limiting        | Built-in 2-second delays prevent YouTube API issues         |

---

## Development

```bash
uv sync                    # Install dependencies
uv run black src/ tests/   # Format code
uv run mypy src/           # Type check
uv run pytest              # Run tests
```

---

## Privacy and Security

- 100% local processing — no data sent to external APIs
- Cached transcripts stored locally
- Built-in rate limiting
- No API keys or authentication required
- Open source

---

## License

MIT License — see LICENSE file for details.

---

## Acknowledgments

- [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) for transcript fetching
- [Ollama](https://ollama.ai) for local LLM inference
- [questionary](https://github.com/tmbo/questionary) for TUI interactions
- [uv](https://github.com/astral-sh/uv) for dependency management
