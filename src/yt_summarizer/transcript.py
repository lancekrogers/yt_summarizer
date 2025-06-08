"""
YouTube transcript fetching with caching and rate limiting.

Handles downloading transcripts via youtube-transcript-api with proper error handling.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import NamedTuple

import requests
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
from youtube_transcript_api.formatters import TextFormatter

from .config import config

logger = logging.getLogger(__name__)

# Video ID extraction regex
_VIDEO_ID_RE = re.compile(r"(?:watch\?v=|youtu\.be/|embed/)([\w\-]{11})")

# Rate limiting
_last_request_time = 0.0


class TranscriptData(NamedTuple):
    """Container for transcript data."""
    video_id: str
    title: str
    text: str
    cached: bool


class TranscriptError(Exception):
    """Base exception for transcript-related errors."""
    pass


class NoTranscriptAvailable(TranscriptError):
    """Raised when no transcript is available for a video."""
    pass


def extract_video_id(url_or_id: str) -> str:
    """
    Extract YouTube video ID from URL or return the ID if already extracted.
    
    Args:
        url_or_id: YouTube URL or video ID.
        
    Returns:
        11-character video ID.
        
    Raises:
        TranscriptError: If unable to extract valid video ID.
    """
    cleaned = url_or_id.strip()
    if not cleaned:
        raise TranscriptError("Empty video URL/ID provided")
    
    # Try to extract from URL
    match = _VIDEO_ID_RE.search(cleaned)
    if match:
        return match.group(1)
    
    # Check if it's already a video ID (11 characters, alphanumeric + hyphens/underscores)
    if len(cleaned) == 11 and re.match(r'^[a-zA-Z0-9_-]+$', cleaned):
        return cleaned
    
    raise TranscriptError(f"Unable to extract video ID from: {url_or_id}")


def _rate_limit() -> None:
    """Apply rate limiting to avoid overwhelming YouTube API."""
    global _last_request_time
    
    elapsed = time.time() - _last_request_time
    if elapsed < config.RATE_LIMIT_DELAY:
        sleep_time = config.RATE_LIMIT_DELAY - elapsed
        logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
        time.sleep(sleep_time)
    
    _last_request_time = time.time()


def _get_cache_path(video_id: str) -> Path:
    """Get the cache file path for a video ID."""
    return config.RAW_DIR / f"{video_id}.txt"


def _load_from_cache(video_id: str) -> str | None:
    """
    Load transcript from cache if available.
    
    Args:
        video_id: YouTube video ID.
        
    Returns:
        Cached transcript text or None if not cached/empty.
    """
    cache_path = _get_cache_path(video_id)
    if cache_path.exists():
        try:
            text = cache_path.read_text(encoding="utf-8")
            # Check if the cached file has actual content
            if text and text.strip():
                logger.debug(f"Loaded {video_id} from cache")
                return text
            else:
                logger.warning(f"Cache file for {video_id} is empty, will fetch fresh transcript")
                # Optionally remove the empty cache file
                try:
                    cache_path.unlink()
                    logger.debug(f"Removed empty cache file for {video_id}")
                except:
                    pass
                return None
        except Exception as e:
            logger.warning(f"Failed to read cache for {video_id}: {e}")
    
    return None


def _save_to_cache(video_id: str, text: str) -> None:
    """
    Save transcript to cache.
    
    Args:
        video_id: YouTube video ID.
        text: Transcript text to cache.
    """
    # Don't save empty transcripts
    if not text or not text.strip():
        logger.warning(f"Refusing to cache empty transcript for {video_id}")
        return
        
    config.create_directories()
    cache_path = _get_cache_path(video_id)
    
    try:
        cache_path.write_text(text, encoding="utf-8")
        logger.debug(f"Cached transcript for {video_id}")
    except Exception as e:
        logger.warning(f"Failed to cache transcript for {video_id}: {e}")


def fetch_video_title(video_id: str) -> str:
    """
    Fetch video title from YouTube using oembed API.
    
    Args:
        video_id: YouTube video ID.
        
    Returns:
        Video title or video_id as fallback.
    """
    try:
        # Use YouTube's oembed API with shortened URL format for better reliability
        url = f"https://www.youtube.com/oembed?url=https://youtu.be/{video_id}&format=json"
        
        response = requests.get(url, timeout=config.YOUTUBE_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        title = data.get("title", video_id)
        
        logger.debug(f"Fetched title for {video_id}: {title}")
        return title
        
    except Exception as e:
        logger.warning(f"Failed to fetch title for {video_id}: {e}")
        return video_id  # Fallback to video ID


def fetch_transcript(video_id: str, use_cache: bool = True) -> TranscriptData:
    """
    Fetch transcript for a YouTube video.
    
    Args:
        video_id: YouTube video ID.
        use_cache: Whether to use/update cache.
        
    Returns:
        TranscriptData with video information and transcript text.
        
    Raises:
        NoTranscriptAvailable: If no transcript is available.
        TranscriptError: If fetching fails for other reasons.
    """
    # Check cache first if enabled
    cached_text = None
    if use_cache:
        cached_text = _load_from_cache(video_id)
        if cached_text:
            # Fetch title even for cached transcripts
            title = fetch_video_title(video_id)
            return TranscriptData(
                video_id=video_id,
                title=title,
                text=cached_text,
                cached=True
            )
        else:
            logger.debug(f"No cached transcript found for {video_id}, fetching from YouTube")
    
    # Apply rate limiting before making request
    _rate_limit()
    
    # Retry logic for transient errors
    max_retries = 2
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            logger.info(f"Fetching transcript for video {video_id} from YouTube API" + (f" (attempt {retry_count + 1}/{max_retries + 1})" if retry_count > 0 else ""))
            
            # Fetch transcript (prefers manual captions over auto-generated)
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            try:
                # Try to get manually created transcript first
                transcript = transcript_list.find_manually_created_transcript(['en'])
                logger.debug(f"Using manual transcript for {video_id}")
            except:
                try:
                    # Fall back to auto-generated transcript
                    transcript = transcript_list.find_generated_transcript(['en'])
                    logger.debug(f"Using auto-generated transcript for {video_id}")
                except:
                    # Try any available transcript
                    transcript = transcript_list[0]
                    logger.debug(f"Using first available transcript for {video_id}")
            
            # Get the actual transcript data
            transcript_data = transcript.fetch()
            
            # Format as plain text
            formatter = TextFormatter()
            text = formatter.format_transcript(transcript_data)
            
            # Validate we got actual content
            if not text or not text.strip():
                raise TranscriptError(f"Received empty transcript for video {video_id}")
            
            # Get video title
            title = fetch_video_title(video_id)
            
            # Save to cache if enabled
            if use_cache:
                _save_to_cache(video_id, text)
            
            logger.info(f"Successfully fetched transcript for {video_id}")
            
            return TranscriptData(
                video_id=video_id,
                title=title,
                text=text,
                cached=False
            )
            
        except NoTranscriptFound:
            logger.warning(f"No transcript available for video {video_id}")
            raise NoTranscriptAvailable(f"No transcript available for video {video_id}")
        
        except Exception as e:
            error_str = str(e).lower()
            # Check for XML parsing errors that might be transient
            if "no element found" in error_str or "xml" in error_str:
                retry_count += 1
                if retry_count <= max_retries:
                    logger.warning(f"XML parsing error for video {video_id}, retrying in {retry_count * 2} seconds...")
                    time.sleep(retry_count * 2)  # Exponential backoff
                    continue
            
            logger.error(f"Failed to fetch transcript for {video_id}: {type(e).__name__}: {e}")
            # Add more context to XML parsing errors
            if "no element found" in error_str:
                logger.error(f"XML parsing error - YouTube may have returned an empty or malformed response for video {video_id}")
            raise TranscriptError(f"Failed to fetch transcript for {video_id}: {e}")


def chunk_text(text: str, max_tokens: int | None = None) -> list[str]:
    """
    Split text into chunks suitable for LLM processing.
    
    Args:
        text: Text to chunk.
        max_tokens: Maximum tokens per chunk, defaults to config.CHUNK_SIZE.
        
    Returns:
        List of text chunks.
    """
    if max_tokens is None:
        max_tokens = config.CHUNK_SIZE
    
    chunks = []
    current_tokens = 0
    current_lines = []
    
    for line in text.splitlines():
        # Rough token estimation (words * 1.3)
        line_tokens = int(len(line.split()) * 1.3)
        
        if current_tokens + line_tokens > max_tokens and current_lines:
            # Start new chunk
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_tokens = line_tokens
        else:
            current_lines.append(line)
            current_tokens += line_tokens
    
    # Add final chunk if any content remains
    if current_lines:
        chunks.append("\n".join(current_lines))
    
    return chunks


def get_cache_stats() -> dict[str, int]:
    """
    Get statistics about cached transcripts.
    
    Returns:
        Dictionary with cache statistics.
    """
    if not config.RAW_DIR.exists():
        return {"total_files": 0, "total_size_bytes": 0}
    
    cache_files = list(config.RAW_DIR.glob("*.txt"))
    total_size = sum(f.stat().st_size for f in cache_files)
    
    return {
        "total_files": len(cache_files),
        "total_size_bytes": total_size
    }


def clear_cache() -> int:
    """
    Clear all cached transcripts.
    
    Returns:
        Number of files deleted.
    """
    if not config.RAW_DIR.exists():
        return 0
    
    cache_files = list(config.RAW_DIR.glob("*.txt"))
    deleted_count = 0
    
    for cache_file in cache_files:
        try:
            cache_file.unlink()
            deleted_count += 1
        except Exception as e:
            logger.warning(f"Failed to delete cache file {cache_file}: {e}")
    
    logger.info(f"Cleared {deleted_count} cached transcripts")
    return deleted_count