---
id: Ollama-Guide
aliases: []
tags: []
---

# Ollama Quick‑Start & Model Switching Guide

This short guide supplements **YouTube‑Summarizer** and shows how to

1. install and run **Ollama** locally
2. pull a model image
3. change which model the pipeline uses (CLI flag or code edit)

---

## 1  Install Ollama

| Platform             | Command |
| -------------------- | ------- |
| **macOS (Homebrew)** | ```bash |

brew install ollama

````|
| **Linux (generic)** | ```bash
curl -fsSL https://ollama.ai/install.sh | sh
``` |
| **Windows / Docker** | See <https://ollama.ai/download> |

Verify:

```bash
ollama --version
````

---

## 2  Run the Ollama server

```bash
ollama serve
```

- Runs a local REST API on **<http://localhost:11434>**
- Keeps running until you press **Ctrl‑C**.

---

## 3  Pull a model image

First time only:

```bash
# examples — pick ONE
ollama pull llama3:8b
ollama pull phi3:mini
ollama pull mistral:7b-instruct
```

Images are cached in `~/.ollama`.

> **Tip**Run `ollama list` to see what’s cached.

---

## 4  Switching models **at runtime**

### 4.1 CLI flag (preferred)

`yt-summarizer` accepts `--model <tag>`:

```bash
poetry run yt-summarizer ids.txt --model phi3:mini
```

So you can test multiple models without touching any code.

### 4.2 Code edit (hard‑coded)

Open `src/yt_summarizer/pipeline.py` and change the constant near the top:

```python
OLLAMA_MODEL = "phi3:mini"   # default was "llama3:8b"
```

Save, re‑run the pipeline.

### 4.3 Global default for ALL Ollama clients

```bash
export OLLAMA_DEFAULT_MODEL="phi3:mini"
ollama serve
```

Any HTTP request that omits the `"model"` field will now use **phi3:mini**.

---

## 5  Common issues

| Symptom                    | Likely cause / fix                                                                            |
| -------------------------- | --------------------------------------------------------------------------------------------- |
| `failed to fetch manifest` | Typo in model tag. Run `ollama list` or pull again.                                           |
| Out‑of‑memory crash        | Model too large; pick a 7‑8 billion parameter variant or set `OLLAMA_NO_GPU=1` to run on CPU. |
| HTTP 404 when generating   | Model not pulled; `ollama pull <tag>` then retry.                                             |

---

## 6  FAQ

### Can I run multiple models simultaneously?

Yes. Each request specifies its own `model` tag; Ollama loads it on demand. Memory usage grows with loaded models, so keep an eye on resource limits.

### Do I need a GPU?

No. Ollama falls back to CPU automatically, though generation will be slower. Force CPU with:

```bash
export OLLAMA_NO_GPU=1
ollama serve
```

### Where are models stored?

`~/.ollama` (approx. **1–8 GB** per model).

---

Happy summarising!  
Feel free to open issues or PRs if you hit snags.
