#!/usr/bin/env python3
"""yt_summarizer.py
--------------------

End‑to‑end mini‑pipeline that:

1. **Downloads** YouTube transcripts (manual ▸ auto) with *youtube‑transcript‑api*
2. **Chunks & summarises** them locally via an **Ollama** model
3. **Stores** the raw caption JSON, Markdown summaries, and an ingest log.

Run:

    poetry run python yt_summarizer.py video_ids.txt --model llama3:8b
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

import requests
from youtube_transcript_api import NoTranscriptFound, YouTubeTranscriptApi

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

RAW_DIR = Path("data/raw")
MD_DIR = Path("data/corpus")
LOG_PATH = Path("logs/ingest.jsonl")

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3:8b"

TOKENS_PER_CHUNK = 2048
CHUNK_PROMPT = (
    "You are a precise research assistant. Summarise the following \n"
    "transcript chunk in <=150 words, focusing on key facts.\n\n{chunk}\n"
)

# --------------------------------------------------------------------------- #
# Helper regex
# --------------------------------------------------------------------------- #

_VIDEO_ID_RE = re.compile(r"(?:watch\?v=|youtu\.be/|embed/)([\w\-]{11})")


def extract_video_id(url_or_id: str) -> str:
    """Return the raw 11‑character YouTube ID from a URL or ID."""
    match = _VIDEO_ID_RE.search(url_or_id)
    return match.group(1) if match else url_or_id.strip()


# --------------------------------------------------------------------------- #
# Transcript utilities
# --------------------------------------------------------------------------- #


def download_transcript(video_id: str) -> List[Dict[str, Any]]:
    """Fetch transcript or read cached copy as list[dict]."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = RAW_DIR / f"{video_id}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text())

    fetched = YouTubeTranscriptApi().fetch(video_id).to_raw_data()
    cache_file.write_text(json.dumps(fetched, ensure_ascii=False))
    return fetched


def transcript_to_text(snippets: List[Dict[str, Any]]) -> str:
    """Join snippet texts into one large string."""
    return "\n".join(snippet["text"] for snippet in snippets)


# --------------------------------------------------------------------------- #
# Chunk + summarise via Ollama
# --------------------------------------------------------------------------- #


def iter_chunks(text: str, token_limit: int = TOKENS_PER_CHUNK) -> Iterable[str]:
    word_count, buffer = 0, []
    for line in text.splitlines():
        w = len(line.split())
        if word_count + w > token_limit:
            yield "\n".join(buffer)
            buffer, word_count = [], 0
        buffer.append(line)
        word_count += w
    if buffer:
        yield "\n".join(buffer)


def llm_complete(prompt: str, model: str) -> str:
    payload = {"model": model, "prompt": prompt, "stream": False}
    resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["response"].strip()


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #


def save_markdown(video_id: str, exec_summary: str, chunk_summaries: List[str]) -> None:
    MD_DIR.mkdir(parents=True, exist_ok=True)
    md_path = MD_DIR / f"{video_id}.md"

    front_matter = "\n".join(
        [
            "---",
            f"video_id: {video_id}",
            f"saved: {time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"url: https://youtu.be/{video_id}",
            "tags: [youtube, transcript]",
            "---",
            "",
        ]
    )

    body_parts = [
        "## Executive Summary",
        exec_summary,
        "",
        "## Chunk Summaries",
    ] + [f"### Chunk {i + 1}\n{summary}" for i, summary in enumerate(chunk_summaries)]

    md_path.write_text(front_matter + "\n\n".join(body_parts))


def append_log(entry: Dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as log_fp:
        log_fp.write(json.dumps(entry) + "\n")


# --------------------------------------------------------------------------- #
# Ingest pipeline
# --------------------------------------------------------------------------- #


def process_video(video_id: str, model: str) -> None:
    try:
        raw_snippets = download_transcript(video_id)
    except NoTranscriptFound as exc:
        print(f"✗ {video_id}: {exc}")
        return

    full_text = transcript_to_text(raw_snippets)

    chunk_summaries = [
        llm_complete(CHUNK_PROMPT.format(chunk=chunk), model)
        for chunk in iter_chunks(full_text)
    ]

    executive_summary = llm_complete(
        "Combine these bullet summaries into a 200‑word executive overview:\n\n"
        + "\n\n".join(chunk_summaries),
        model,
    )

    save_markdown(video_id, executive_summary, chunk_summaries)
    append_log(
        {
            "video_id": video_id,
            "chunks": len(chunk_summaries),
            "model": model,
            "timestamp": time.time(),
        }
    )
    print(f"✓ {video_id}: {len(chunk_summaries)} chunks summarised")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="YouTube → transcript → Ollama summary"
    )
    parser.add_argument(
        "ids_file", help="Text file with YouTube IDs/URLs, one per line"
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model tag to use (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    for line in Path(args.ids_file).read_text().splitlines():
        vid = extract_video_id(line)
        process_video(vid, args.model)


if __name__ == "__main__":
    cli()
