#!/usr/bin/env python3
"""
Download or stream YouTube captions (manual ▸ auto ▸ translation) in
JSON, SRT, WebVTT, or plain-text with zero API key.

Usage examples
--------------
# 1) dump to stdout (default text)
python grab_transcript.py https://youtu.be/dQw4w9WgXcQ

# 2) batch → ./out as SRT
python grab_transcript.py ids.txt -o srt -d out

# 3) prefer Spanish captions, auto-translate to English
python grab_transcript.py URL -l es -t en -o vtt
"""
from __future__ import annotations

import argparse, json, re, sys
from pathlib import Path
from typing import Any, cast

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    CouldNotRetrieveTranscript,
)
from youtube_transcript_api.formatters import (
    Formatter,
    TextFormatter,
    JSONFormatter,
    SRTFormatter,
    WebVTTFormatter,
)

ID_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtu\.be/([^\?&/]+)",
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([^\?&/]+)",
    r"(?:https?://)?(?:www\.)?youtube\.com/embed/([^\?&/]+)",
]

FMT_MAP: dict[str, type[Formatter]] = {
    "text": TextFormatter,
    "json": JSONFormatter,
    "srt": SRTFormatter,
    "vtt": WebVTTFormatter,
}


def extract_id(s: str) -> str:  # URL → ID or raw ID unchanged
    for pat in ID_PATTERNS:
        if m := re.match(pat, s):
            return m.group(1)
    return s.strip()


def choose_transcript(api: YouTubeTranscriptApi, vid: str, langs: list[str] | None):
    tl = api.list(vid)  # ↩︎ TranscriptList
    try:
        return tl.find_transcript(langs or tl._generated_transcripts)
    except NoTranscriptFound:
        # let caller decide – we’ll surface the nicer message below
        raise


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "videos", nargs="+", help="Video URL/ID or txt file w/ one ID per line"
    )
    p.add_argument(
        "-l", "--lang", nargs="*", help="Preferred language codes (ISO-639-1)"
    )
    p.add_argument("-t", "--translate", help="Translate captions to this ISO code")
    p.add_argument("-o", "--output", choices=list(FMT_MAP), default="text")
    p.add_argument("-d", "--dir", default=".", help="Output directory")
    p.add_argument(
        "--preserve-formatting", action="store_true", help="Keep <i>, <b>, etc."
    )
    args = p.parse_args()

    out_dir = Path(args.dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    targets: list[str] = []
    for v in args.videos:
        path = Path(v)
        if path.is_file():
            targets += path.read_text().splitlines()
        else:
            targets.append(v)

    api = YouTubeTranscriptApi()  # ← instance style

    for raw in targets:
        vid = extract_id(raw)
        try:
            tr = choose_transcript(api, vid, args.lang)
            if args.translate:
                if not tr.is_translatable:
                    raise RuntimeError("Transcript not translatable by YouTube")
                tr = tr.translate(args.translate)

            fetched = tr.fetch(preserve_formatting=args.preserve_formatting)
            formatter = FMT_MAP[args.output]()  # instantiate
            data = formatter.format_transcript(fetched)

            if args.output == "text":
                print(f"\n# {vid}\n{data}")
            else:
                file = out_dir / f"{vid}.{args.output}"
                file.write_text(cast(str, data), encoding="utf-8")
                print(f"✔ saved {file}")

        except (TranscriptsDisabled, NoTranscriptFound) as e:
            print(f"[WARN] {vid}: {e}", file=sys.stderr)
        except CouldNotRetrieveTranscript as e:
            print(f"[FAIL] {vid}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[ERR ] {vid}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
