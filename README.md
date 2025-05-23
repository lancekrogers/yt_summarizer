# YouTube Summarizer 📼→📝

A powerful, interactive CLI tool that fetches YouTube video transcripts and generates concise summaries using local LLM models via Ollama. Perfect for researchers, content creators, and anyone who needs to quickly digest video content.

## ✨ Key Features

| Feature                       | Description                                                       |
| ----------------------------- | ----------------------------------------------------------------- |
| **Local Processing**          | No API keys required - uses Ollama for 100% local LLM processing  |
| **Smart Transcript Fetching** | Prefers manual captions, falls back to auto-generated transcripts |
| **Interactive TUI**           | Beautiful terminal interface with guided workflows                |
| **Multiple Input Formats**    | Supports `.txt`, `.list`, `.urls`, and `.csv` files               |
| **Intelligent Chunking**      | Automatically splits long videos for high-quality summaries       |
| **Caching System**            | Caches transcripts to avoid re-downloading                        |
| **Progress Tracking**         | Real-time progress indicators and status updates                  |
| **Flexible Output**           | Markdown summaries with YAML frontmatter                          |
| **Comprehensive Logging**     | JSON logs for processing history and debugging                    |

---

## 🎯 Perfect For

- **Researchers** analyzing video content
- **Content creators** studying competitor videos
- **Students** summarizing lecture recordings
- **Professionals** processing meeting recordings
- **Anyone** who needs to quickly understand video content

---

## 🔧 Prerequisites

- **Python** ≥ 3.11 < 3.14
- **Poetry** for dependency management
- **Ollama** runtime (CPU or GPU)

> **Zero external APIs** - everything runs locally once transcripts are cached!

---

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd youtube-summarizer

# Install dependencies
poetry install

# Allow direnv (if using)
direnv allow
```

### 2. Setup Ollama

```bash
# Install Ollama (macOS)
brew install ollama

# Or Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model
ollama pull llama3.2:latest

# Start Ollama server
ollama serve
```

### 3. Run the Tool

```bash
# Interactive mode (recommended)
./run

# Or use Poetry directly
poetry run yt-summarizer
```

---

## 🎯 Ergonomic Usage

**Option 1: Run Script (Recommended)**

```bash
./run                    # Interactive mode
./run videos.txt         # Legacy mode with file
```

**Option 2: Shell Alias**

```bash
# Add to ~/.zshrc or ~/.bashrc:
alias yts="cd /path/to/youtube-summarizer && poetry run yt-summarizer"
```

**Option 3: Direct Poetry**

```bash
poetry run yt-summarizer
```

---

## 🖥️ Interactive Mode

The interactive TUI provides a guided experience:

### Input Source Selection

- **📋 Default file** (`videos.txt` if present)
- **📄 Custom file** (smart file browser with format filtering)
- **🔗 Single URL** (paste any YouTube URL)

### Smart File Selection

When choosing custom files, you'll see:

- **Only compatible formats** (`.txt`, `.list`, `.urls`, `.csv`)
- **Visual file browser** with icons
- **Directory browsing** option
- **Manual path entry** fallback

### Processing Options

- **Model selection** with defaults
- **Cache preferences**
- **File conflict handling** (overwrite/skip/version)

### Post-Run Actions

- **➕ Summarize more videos**
- **🧹 Clean transcript cache**
- **🚪 Quit**

---

## 📂 Supported File Formats

| Format  | Description                   | Example                                 |
| ------- | ----------------------------- | --------------------------------------- |
| `.txt`  | One URL/ID per line           | `dQw4w9WgXcQ`<br>`https://youtu.be/...` |
| `.list` | Video list files              | Same as `.txt`                          |
| `.urls` | URL files                     | Same as `.txt`                          |
| `.csv`  | CSV with URLs in first column | `url,title`<br>`dQw4w9WgXcQ,Rick Roll`  |

**Features:**

- Comments supported (`# comment`)
- Auto-detects CSV headers
- Validates video IDs/URLs
- UTF-8 encoding

---

## 🖥️ Ollama Setup

| Step              | Command                                                                                | Notes                                                  |
| ----------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| **Install**       | macOS: `brew install ollama`<br>Linux: `curl -fsSL https://ollama.ai/install.sh \| sh` | See [ollama.ai](https://ollama.ai) for other platforms |
| **Pull Model**    | `ollama pull llama3.2:latest`                                                          | Downloads once, stored locally                         |
| **Start Server**  | `ollama serve`                                                                         | Runs API on port **11434**                             |
| **List Models**   | `ollama list`                                                                          | See available models                                   |
| **Switch Models** | Use `--model` flag or interactive selection                                            | Any model from `ollama list`                           |

**Memory Considerations:**

- Use smaller models (`llama3.2:1b`, `phi3:mini`) for limited memory
- Set `OLLAMA_NO_GPU=1` for CPU-only processing
- Larger models (`llama3.2:latest`) provide better summaries

---

## ⚙️ CLI Reference

### Interactive Mode (Default)

```bash
./run
poetry run yt-summarizer
```

### Legacy Mode

```bash
./run videos.txt --model llama3.2:latest
poetry run yt-summarizer videos.txt --model llama3.2:latest

Options:
  --model MODEL    Ollama model tag (default: llama3.2:latest)
  --interactive    Force interactive mode
  --help          Show help message
```

---

## 📁 Project Structure

```
youtube-summarizer/
├── src/yt_summarizer/      # Main package
│   ├── cli.py             # Interactive TUI
│   ├── config.py          # Configuration management
│   ├── llm.py             # Ollama integration
│   ├── pipeline.py        # Processing orchestration
│   ├── transcript.py      # YouTube API handling
│   └── utils.py           # Utilities & markdown
├── data/                  # Generated content
│   ├── raw/              # Cached transcripts (.txt)
│   └── docs/             # Markdown summaries
├── logs/                 # Processing logs
│   └── ingest.jsonl      # Structured activity log
├── .env.example          # Configuration template
└── run                   # Launcher script
```

---

## 📊 Output Format

### Markdown Summaries (`docs/`)

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

## Executive Summary
[Comprehensive overview of the video content]

## Part Summaries

### Part 1
[Summary of first chunk]

### Part 2
[Summary of second chunk]
```

### Processing Logs (`logs/ingest.jsonl`)

```json
{
  "timestamp": 1642867200,
  "video_id": "dQw4w9WgXcQ",
  "title": "Never Gonna Give You Up",
  "status": "success",
  "chunk_count": 3,
  "model": "llama3.2:latest"
}
```

---

## ⚙️ Configuration

### Environment Variables (`.env`)

```bash
# Ollama Configuration
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest

# Processing
CHUNK_SIZE=2048
RATE_LIMIT_DELAY=2.0

# Directories
DATA_DIR=data
DOCS_DIR=docs
LOGS_DIR=logs

# Timeouts
OLLAMA_TIMEOUT=300
YOUTUBE_TIMEOUT=30
```

### Configuration Priority

1. Environment variables (`.env` file)
2. Built-in defaults
3. CLI arguments (legacy mode)

---

## 🛠️ Troubleshooting

| Issue                  | Solution                                                   |
| ---------------------- | ---------------------------------------------------------- |
| `NoTranscriptFound`    | Video has no public captions - try a different video       |
| `LLMConnectionError`   | Start Ollama server: `ollama serve`                        |
| `HTTP 404` from Ollama | Check model exists: `ollama list` or `ollama pull <model>` |
| Out of memory          | Use smaller model (`llama3.2:1b`) or `OLLAMA_NO_GPU=1`     |
| Poetry install fails   | Ensure Python 3.11-3.13, update Poetry                     |
| Rate limiting          | Built-in 2-second delays prevent YouTube API issues        |

### Debug Mode

```bash
# Enable verbose logging
export PYTHONPATH=src
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from yt_summarizer.pipeline import process_single_video
process_single_video('dQw4w9WgXcQ')
"
```

---

## 🧪 Testing

```bash
# Test basic functionality
echo "dQw4w9WgXcQ" > test_videos.txt
./run test_videos.txt

# Test interactive mode
./run

# Test different formats
echo "url,title
dQw4w9WgXcQ,Rick Roll" > test.csv
./run test.csv
```

**Safe Test Videos:**

- `dQw4w9WgXcQ` - Rick Roll (guaranteed captions)
- `jNQXAC9IVRw` - First YouTube video (short)

---

## 🔒 Privacy & Security

- **100% local processing** - no data sent to external APIs
- **Cached transcripts** stored locally in `data/raw/`
- **Rate limiting** prevents overwhelming YouTube's servers
- **No API keys** or authentication required
- **Open source** - inspect all code

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Follow existing code style
5. Submit a pull request

### Development Setup

```bash
poetry install --with dev
poetry run black src/
poetry run mypy src/
poetry run pytest
```

---

## 📄 License

MIT License - see LICENSE file for details.

---

## 🙏 Acknowledgments

- **youtube-transcript-api** for transcript fetching
- **Ollama** for local LLM inference
- **questionary** for beautiful TUI interactions
- **Poetry** for dependency management

---

**Happy Summarizing!** 🎬✨
