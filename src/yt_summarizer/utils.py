"""
Utility functions for file operations, slugification, and markdown generation.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from .config import config


def slugify(text: str, max_length: int = 50) -> str:
    """
    Convert text to a filesystem-safe slug.
    
    Args:
        text: Text to slugify.
        max_length: Maximum length of the resulting slug.
        
    Returns:
        Slugified string safe for use as filename.
    """
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')
    
    # Truncate if too long
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip('-')
    
    # Ensure we have something
    if not slug:
        slug = "untitled"
    
    return slug


def create_markdown_summary(
    video_id: str,
    title: str,
    executive_summary: str,
    chunk_summaries: list[str],
    model: str,
    slug: str | None = None
) -> str:
    """
    Create markdown content with YAML frontmatter.
    
    Args:
        video_id: YouTube video ID.
        title: Video title.
        executive_summary: Executive summary text.
        chunk_summaries: List of chunk summaries.
        model: Model used for summarization.
        slug: Optional slug, will be generated from title if not provided.
        
    Returns:
        Complete markdown content.
    """
    if slug is None:
        slug = slugify(title)
    
    # YAML frontmatter
    frontmatter = f"""---
video_id: {video_id}
url: https://youtu.be/{video_id}
title: "{title}"
slug: "{slug}"
saved: {time.strftime('%Y-%m-%dT%H:%M:%SZ')}
model: {model}
chunk_count: {len(chunk_summaries)}
tags: [youtube, transcript]
---"""

    # Executive summary section
    content = f"\n\n## Executive Summary\n\n{executive_summary}"
    
    # Chunk summaries
    if chunk_summaries:
        content += "\n\n## Part Summaries\n"
        for i, summary in enumerate(chunk_summaries, 1):
            content += f"\n### Part {i}\n\n{summary}\n"
    
    return frontmatter + content


def save_markdown(
    video_id: str,
    title: str,
    executive_summary: str,
    chunk_summaries: list[str],
    model: str,
    slug: str | None = None,
    version: str | None = None
) -> Path:
    """
    Save markdown summary to file.
    
    Args:
        video_id: YouTube video ID.
        title: Video title.
        executive_summary: Executive summary text.
        chunk_summaries: List of chunk summaries.
        model: Model used for summarization.
        slug: Optional slug, will be generated from title if not provided.
        version: Optional version suffix (e.g., "v2", "v3").
        
    Returns:
        Path to the saved file.
    """
    if slug is None:
        slug = slugify(title)
    
    # Handle versioning
    filename = slug
    if version:
        filename = f"{slug}_{version}"
    
    config.create_directories()
    file_path = config.DOCS_DIR / f"{filename}.md"
    
    # Create markdown content
    markdown_content = create_markdown_summary(
        video_id, title, executive_summary, chunk_summaries, model, slug
    )
    
    # Write to file
    file_path.write_text(markdown_content, encoding="utf-8")
    
    return file_path


def log_ingest(
    video_id: str,
    title: str,
    slug: str,
    model: str,
    chunk_count: int,
    status: str,
    error: str | None = None
) -> None:
    """
    Log processing information to JSONL file.
    
    Args:
        video_id: YouTube video ID.
        title: Video title.
        slug: Generated slug.
        model: Model used.
        chunk_count: Number of chunks processed.
        status: Processing status (success, error, skipped).
        error: Optional error message.
    """
    config.create_directories()
    
    log_entry = {
        "timestamp": time.time(),
        "iso_timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "video_id": video_id,
        "title": title,
        "slug": slug,
        "model": model,
        "chunk_count": chunk_count,
        "status": status
    }
    
    if error:
        log_entry["error"] = error
    
    # Append to log file
    with config.LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")


def check_file_exists(file_path: Path) -> bool:
    """Check if a file exists."""
    return file_path.exists()


def get_available_version(base_slug: str) -> str:
    """
    Get the next available version suffix for a slug.
    
    Args:
        base_slug: Base slug name.
        
    Returns:
        Version suffix (e.g., "v2", "v3") or empty string for first version.
    """
    base_path = config.DOCS_DIR / f"{base_slug}.md"
    
    if not base_path.exists():
        return ""
    
    # Find next available version
    version = 2
    while True:
        versioned_path = config.DOCS_DIR / f"{base_slug}_v{version}.md"
        if not versioned_path.exists():
            return f"v{version}"
        version += 1


def read_video_list(file_path: Path) -> list[str]:
    """
    Read and parse a video list file.
    
    Args:
        file_path: Path to the video list file.
        
    Returns:
        List of video URLs/IDs.
        
    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If file is empty or invalid.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Video list file not found: {file_path}")
    
    content = file_path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Video list file is empty: {file_path}")
    
    # Parse lines, skipping empty lines and comments
    videos = []
    for line_num, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if line and not line.startswith('#'):
            videos.append(line)
    
    if not videos:
        raise ValueError(f"No valid video URLs/IDs found in: {file_path}")
    
    return videos


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"