# yt_summarizer

**YouTube transcripts in. Local summaries out. No API key.**

Pulls captions (manual first, auto if that is all there is), chunks
them, and asks [Ollama](https://ollama.com) for a summary. TUI if you
want a menu. Plain CLI if you want a pipeline.

```bash
uv run yt-summarizer summarize 'https://youtube.com/watch?v=dQw4w9WgXcQ'
```

Transcripts cache on disk. The second run does not hit YouTube again.

## Needs

- Python 3.11–3.13
- [uv](https://github.com/astral-sh/uv)
- Ollama with a model pulled (`llama3.2` is the default)

## Install

```bash
git clone https://github.com/lancekrogers/yt_summarizer.git
cd yt_summarizer
uv sync
ollama pull llama3.2:latest
ollama serve
```

## Use

```bash
uv run yt-summarizer                              # TUI
uv run yt-summarizer summarize URL
uv run yt-summarizer summarize URL -o ./out
uv run yt-summarizer summarize -f videos.txt
uv run yt-summarizer summarize URL -m llama3.2:1b
```

| Flag | |
|------|--|
| `-f`, `--file` | URL list |
| `-o`, `--output` | Where to write |
| `-m`, `--model` | Ollama model |
| `--no-cache` | Skip the transcript cache |
| `--overwrite` | Replace existing summaries |

Research plans (`yt-summarizer plan …`) extract one question across a
pile of videos and fold the answers into a corpus. YAML lives in
`research_plans/`.

```bash
uv run yt-summarizer plan create --name "LLM prompts"
uv run yt-summarizer plan run <plan-id>
```

Lists can be `.txt`, `.list`, `.urls`, or a CSV with the URL in the
first column.

## Config

`~/.config/youtube-summarizer/config.yaml` (XDG). Env vars win, then
the YAML, then defaults. `just config` prints the paths.

```yaml
ollama_url: http://localhost:11434
ollama_model: llama3.2:latest
chunk_size: 2048
```

`just` at the repo root is the command menu (`run`, `test all`,
`lint all`).

## License

[MIT](LICENSE)
