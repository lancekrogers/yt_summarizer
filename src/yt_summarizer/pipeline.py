#!/usr/bin/env python3
"""
pipeline.py
===========

End‑to‑end pipeline:

1. **Reads** a text file of YouTube URLs/IDs (one per line).
2. **Fetches** the *full caption text* for each video (prefers manual → auto).
3. **Stores** that plain‑text transcript under **data/**  (one `.txt` per video).
4. **Chunks and summarises** the transcript with a local **Ollama** model
   (`llama3.2:latest` by default).
5. **Writes** a Markdown summary document to **docs/**.

Run::

    poetry run yt_summarizer videos.txt
"""

from __future__ import annotations

import argparse
import json
import re
import textwrap
import time
from pathlib import Path
from typing import Iterable, List

import requests
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound

# ---------------------------------------------------------------------------- #
# Paths
# ---------------------------------------------------------------------------- #
DATA_DIR = Path("data/raw")  # full transcript .txt files
DOCS_DIR = Path("data/docs/")  # markdown summaries
LOG_FILE = Path("data/logs/ingest.jsonl")

# ---------------------------------------------------------------------------- #
# LLM configuration
# ---------------------------------------------------------------------------- #
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2:latest"
TOKENS_PER_CHUNK = 2048

# CHUNK_PROMPT_TEMPLATE = (
#     "You are a precise research assistant. Summarize the following transcript "
#     "chunk in <=150 words, focusing on key facts and arguments.\n\n{chunk}\n"
# )
CHUNK_PROMPT_TEMPLATE = (
    "You are a precise research assistant. Your goal is to extract the"
    "prompts discussed in this transcript"
    "chunk, focusing on specific mentions of prompts the writer finds helpful.\n\n{chunk}\n"
)


FINAL_PROMPT_TEMPLATE = (
    "Combine these chunk summaries into a concise executive overview:"
    "\n\n{bullet_summaries}"
)

# ---------------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------------- #
_VIDEO_ID_RE = re.compile(r"(?:watch\?v=|youtu\.be/|embed/)([\w\-]{11})")


def extract_video_id(url_or_id: str) -> str:
    match = _VIDEO_ID_RE.search(url_or_id)
    return match.group(1) if match else url_or_id.strip()


def fetch_transcript_text(video_id: str) -> str:
    """
    Return *plain text* transcript for `video_id`, using cache in data/.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = DATA_DIR / f"{video_id}.txt"
    if cache_path.exists():
        return cache_path.read_text()

    raw_snippets = YouTubeTranscriptApi().fetch(video_id).to_raw_data()
    full_text = "\n".join(snippet["text"] for snippet in raw_snippets)
    cache_path.write_text(full_text, encoding="utf-8")
    return full_text


def chunk_text(text: str, limit: int = TOKENS_PER_CHUNK) -> Iterable[str]:
    words: int = 0
    buffer: list[str] = []
    for line in text.splitlines():
        w = len(line.split())
        if words + w > limit:
            yield "\n".join(buffer)
            buffer, words = [], 0
        buffer.append(line)
        words += w
    if buffer:
        yield "\n".join(buffer)


def call_ollama(prompt: str, model: str = DEFAULT_MODEL) -> str:
    payload = {"model": model, "prompt": prompt, "stream": False}
    r = requests.post(OLLAMA_URL, json=payload, timeout=300)
    r.raise_for_status()
    return r.json()["response"].strip()


def write_markdown(
    video_id: str, exec_summary: str, chunk_summaries: List[str]
) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = DOCS_DIR / f"{video_id}.md"
    front_matter = textwrap.dedent(
        f"""        ---
        video_id: {video_id}
        saved: {time.strftime('%Y-%m-%dT%H:%M:%SZ')}
        url: https://youtu.be/{video_id}
        model: {DEFAULT_MODEL}
        tags: [youtube, transcript]
        ---
    """
    )
    chunks_md = "\n\n".join(
        f"### Chunk {i+1}\n{summary}" for i, summary in enumerate(chunk_summaries)
    )
    body = f"## Executive Summary\n{exec_summary}\n\n## Chunk Summaries\n{chunks_md}"
    md_path.write_text(front_matter + "\n" + body, encoding="utf-8")


def append_log(entry: dict) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------- #
# Pipeline
# ---------------------------------------------------------------------------- #
def process_video(video_id: str, model: str) -> None:
    try:
        transcript_text = fetch_transcript_text(video_id)
    except NoTranscriptFound:
        print(f"✗ {video_id}: no public captions")
        return

    chunk_summaries: List[str] = []
    for chunk in chunk_text(transcript_text):
        summary = call_ollama(CHUNK_PROMPT_TEMPLATE.format(chunk=chunk), model)
        chunk_summaries.append(summary)

    bullets = "\n\n".join(chunk_summaries)
    executive_summary = call_ollama(
        FINAL_PROMPT_TEMPLATE.format(bullet_summaries=bullets), model
    )

    write_markdown(video_id, executive_summary, chunk_summaries)
    append_log(
        {
            "video_id": video_id,
            "chunks": len(chunk_summaries),
            "model": model,
            "timestamp": time.time(),
        }
    )
    print(f"✓ {video_id}: {len(chunk_summaries)} chunks summarised")


# ---------------------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube transcript → Ollama summary")
    parser.add_argument("list_file", help="Text file of YouTube URLs/IDs")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model tag")
    args = parser.parse_args()

    for line in Path(args.list_file).read_text().splitlines():
        vid = extract_video_id(line.strip())
        if vid:
            process_video(vid, args.model)


if __name__ == "__main__":
    main()
