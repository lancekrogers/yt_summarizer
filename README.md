# YouTube-Summarizer 📼→📝

A lightweight research utility that

1. **fetches** closed-caption transcripts for any public YouTube video
2. **summarises** them locally with an **Ollama-hosted LLM** (no cloud tokens)
3. **stores** the results as Markdown "context docs" and an audit log for later use.

It's a self-contained side project—drop the generated corpus into Guild _when you're ready_, or keep it separate for ad-hoc analysis.

---

## ✨ Key Features

| Capability       | Detail                                                                                                      |
| ---------------- | ----------------------------------------------------------------------------------------------------------- |
| Transcript fetch | Uses [`youtube-transcript-api`](https://pypi.org/project/youtube-transcript-api/) – no Selenium, no API key |
| Local LLM        | Any model Ollama can serve (Llama 3, Phi‑3, Mistral, etc.)                                                  |
| Chunking         | Splits long videos into ≤ _N_ tokens for high‑quality summaries                                             |
| Outputs          | `data/raw/*.json` (cache) • `data/corpus/*.md` (summaries) • `logs/ingest.jsonl`                            |
| CLI-first        | `yt-summarizer ids.txt --model llama3:8b`                                                                   |

---

## 🔧 Requirements

- Python ≥ 3.11 < 3.14
- **Poetry** for dependency/venv management
- **Ollama** runtime (runs on CPU or GPU)

> **No external APIs** – everything runs locally once transcripts are cached.

---

## 🏁 Quick Start

```bash
# clone wherever you like
git clone https://github.com/your-user/youtube-summarizer.git
cd youtube-summarizer

# create venv + install deps
poetry install

# (recommended) let direnv auto-activate the venv
direnv allow         # if .envrc is present

# pull an Ollama model (first time only)
ollama pull llama3:8b

# fire up the Ollama server in a separate terminal
ollama serve         # listens on  http://localhost:11434

# run the pipeline on a list of video IDs / URLs
echo "dQw4w9WgXcQ" > ids.txt
poetry run yt-summarizer ids.txt --model llama3:8b
```

Results:

```bash
✓ dQw4w9WgXcQ: 3 chunks summarised
data/
 ├─ raw/dQw4w9WgXcQ.json         # full transcript
 └─ corpus/dQw4w9WgXcQ.md        # nicely formatted summary
logs/ingest.jsonl               # run log
```

---

## 🖥️ Using Ollama

| Step                   | Command                                                                            | Notes                                           |
| ---------------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------- |
| **Install** Ollama     | macOS: `brew install ollama`<br>Linux: `curl -fsSL https://ollama.ai/install.sh \| sh` | See <https://ollama.ai> for other platforms. |
| **Pull** a model image | `ollama pull phi3:mini`                                                            | Downloads once; stored in `~/.ollama`           |
| **Serve** locally      | `ollama serve`                                                                     | Runs HTTP API on **11434** until you stop it.  |
| **Switch models**      | Add `--model <tag>` flag when you run `yt-summarizer`, e.g.<br>`--model phi3:mini` | Any tag shown by `ollama list` works.           |
| **Custom default**     | `export OLLAMA_DEFAULT_MODEL="phi3:mini"` before `ollama serve`                    | Requests that omit `"model"` will use this tag. |

> Memory-bound? Use a 7‑8 billion‑param model (e.g. `phi3:mini`, `mistral:7b-instruct`) or run on CPU with `OLLAMA_NO_GPU=1`.

---

## ⚙️ CLI Reference

```bash
yt-summarizer IDS_FILE [options]

Positional:
  IDS_FILE          Text file with one YouTube ID or URL per line

Options:
  --model TAG       Ollama model tag   [default: llama3:8b]
  --chunk-size N    Max tokens per chunk before summarising (2048 default)
  --help            Show this help
```

_The script automatically caches transcripts; re-running on the same IDs costs only LLM time._

---

## 📂 Data Layout

```
data/
 ├─ raw/                  # untouched transcripts (.json)
 └─ corpus/               # Markdown summaries
logs/
 └─ ingest.jsonl          # one JSON object per video processed
```

The Markdown front-matter includes:

```yaml
---
video_id: dQw4…
url: https://youtu.be/dQw4…
saved: 2025-05-22T02:17:45Z
tags: [youtube, transcript]
---
```

Guild's Corpus loader can ingest these without changes when you're ready.

---

## 🛠️ Troubleshooting

| Symptom                                             | Fix                                                                      |
| --------------------------------------------------- | ------------------------------------------------------------------------ |
| `NoTranscriptFound`                                 | Video has no public captions; nothing we can do.                         |
| `HTTP 404` / `failed to fetch manifest` from Ollama | Mistyped model tag – run `ollama list` or `ollama pull <tag>`.           |
| Out-of-memory crash                                 | Use a smaller model (`phi3:mini`, `llama3:8b`) or set `OLLAMA_NO_GPU=1`. |
| Poetry solver complains about Python 3.14           | Project pins Python to `<3.14`; use 3.11‑3.13.                           |

---

## 📝 License

MIT © Lance Rogers  
Contributions welcome—open a PR or discussion!