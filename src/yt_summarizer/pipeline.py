"""
End-to-end processing pipeline for YouTube video summarization.

Orchestrates the entire process from video URL to markdown summary.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

from yaspin import yaspin

from .config import config
from .llm import LLMConnectionError, LLMError, ensure_connection, summarise_chunk, summarise_transcript
from .transcript import (
    TranscriptData,
    TranscriptError,
    NoTranscriptAvailable,
    extract_video_id,
    fetch_transcript,
    chunk_text
)
from .utils import save_markdown, log_ingest, slugify, get_available_version

logger = logging.getLogger(__name__)


class ProcessingResult(NamedTuple):
    """Result of processing a single video."""
    video_id: str
    title: str
    slug: str
    success: bool
    chunk_count: int
    error: str | None = None
    output_path: Path | None = None


class ProcessingStats(NamedTuple):
    """Statistics for a batch processing run."""
    total_videos: int
    successful: int
    failed: int
    skipped: int


def process_single_video(
    url_or_id: str,
    model: str | None = None,
    use_cache: bool = True,
    auto_overwrite: bool = False
) -> ProcessingResult:
    """
    Process a single video from URL/ID to markdown summary.
    
    Args:
        url_or_id: YouTube URL or video ID.
        model: LLM model to use, defaults to config.OLLAMA_MODEL.
        use_cache: Whether to use cached transcripts.
        auto_overwrite: Whether to overwrite existing files automatically.
        
    Returns:
        ProcessingResult with outcome details.
    """
    if model is None:
        model = config.OLLAMA_MODEL
    
    try:
        # Extract video ID
        video_id = extract_video_id(url_or_id)
        logger.info(f"Processing video {video_id}")
        
        # Fetch transcript
        with yaspin(text=f"Fetching transcript for {video_id}...", color="cyan") as spinner:
            transcript_data = fetch_transcript(video_id, use_cache=use_cache)
            spinner.ok("✓")
        
        # Create slug for filename
        slug = slugify(transcript_data.title)
        
        # Check if output file already exists
        output_path = config.DOCS_DIR / f"{slug}.md"
        if output_path.exists() and not auto_overwrite:
            # For now, just use versioning - in the full CLI we'll prompt the user
            version = get_available_version(slug)
            if version:
                slug = f"{slug}_{version}"
                output_path = config.DOCS_DIR / f"{slug}.md"
        
        # Chunk the transcript
        chunks = chunk_text(transcript_data.text)
        logger.info(f"Split transcript into {len(chunks)} chunks")
        
        # Process each chunk
        chunk_summaries = []
        with yaspin(text=f"Summarizing {len(chunks)} chunks...", color="yellow") as spinner:
            for i, chunk in enumerate(chunks, 1):
                spinner.text = f"Summarizing chunk {i}/{len(chunks)}..."
                summary = summarise_chunk(chunk, model)
                chunk_summaries.append(summary)
            spinner.ok("✓")
        
        # Generate executive summary
        with yaspin(text="Generating executive summary...", color="green") as spinner:
            executive_summary = summarise_transcript(chunk_summaries, model)
            spinner.ok("✓")
        
        # Save markdown file
        output_path = save_markdown(
            video_id=video_id,
            title=transcript_data.title,
            executive_summary=executive_summary,
            chunk_summaries=chunk_summaries,
            model=model,
            slug=slug
        )
        
        # Log success
        log_ingest(
            video_id=video_id,
            title=transcript_data.title,
            slug=slug,
            model=model,
            chunk_count=len(chunk_summaries),
            status="success"
        )
        
        logger.info(f"✓ {video_id}: {len(chunk_summaries)} chunks summarized → {output_path}")
        
        return ProcessingResult(
            video_id=video_id,
            title=transcript_data.title,
            slug=slug,
            success=True,
            chunk_count=len(chunk_summaries),
            output_path=output_path
        )
        
    except NoTranscriptAvailable as e:
        error_msg = f"No transcript available for {url_or_id}"
        logger.warning(error_msg)
        
        # Try to extract video_id for logging, fallback to url_or_id
        try:
            video_id = extract_video_id(url_or_id)
        except:
            video_id = url_or_id[:11]  # Truncate for safety
        
        log_ingest(
            video_id=video_id,
            title="Unknown",
            slug="unknown",
            model=model or config.OLLAMA_MODEL,
            chunk_count=0,
            status="no_transcript",
            error=str(e)
        )
        
        return ProcessingResult(
            video_id=video_id,
            title="Unknown",
            slug="unknown",
            success=False,
            chunk_count=0,
            error=error_msg
        )
        
    except (TranscriptError, LLMError) as e:
        error_msg = f"Processing failed for {url_or_id}: {e}"
        logger.error(error_msg)
        
        try:
            video_id = extract_video_id(url_or_id)
        except:
            video_id = url_or_id[:11]
        
        log_ingest(
            video_id=video_id,
            title="Unknown",
            slug="unknown",
            model=model or config.OLLAMA_MODEL,
            chunk_count=0,
            status="error",
            error=str(e)
        )
        
        return ProcessingResult(
            video_id=video_id,
            title="Unknown",
            slug="unknown",
            success=False,
            chunk_count=0,
            error=error_msg
        )
        
    except Exception as e:
        error_msg = f"Unexpected error processing {url_or_id}: {e}"
        logger.error(error_msg, exc_info=True)
        
        try:
            video_id = extract_video_id(url_or_id)
        except:
            video_id = url_or_id[:11]
        
        log_ingest(
            video_id=video_id,
            title="Unknown",
            slug="unknown",
            model=model or config.OLLAMA_MODEL,
            chunk_count=0,
            status="error",
            error=str(e)
        )
        
        return ProcessingResult(
            video_id=video_id,
            title="Unknown",
            slug="unknown",
            success=False,
            chunk_count=0,
            error=error_msg
        )


def process_video_list(
    video_urls: list[str],
    model: str | None = None,
    use_cache: bool = True,
    auto_overwrite: bool = False
) -> ProcessingStats:
    """
    Process a list of video URLs/IDs.
    
    Args:
        video_urls: List of YouTube URLs or video IDs.
        model: LLM model to use, defaults to config.OLLAMA_MODEL.
        use_cache: Whether to use cached transcripts.
        auto_overwrite: Whether to overwrite existing files automatically.
        
    Returns:
        ProcessingStats with batch processing results.
    """
    if model is None:
        model = config.OLLAMA_MODEL
    
    logger.info(f"Processing {len(video_urls)} videos with model {model}")
    
    successful = 0
    failed = 0
    skipped = 0
    
    for i, url_or_id in enumerate(video_urls, 1):
        print(f"\n--- Processing video {i}/{len(video_urls)} ---")
        
        result = process_single_video(
            url_or_id=url_or_id,
            model=model,
            use_cache=use_cache,
            auto_overwrite=auto_overwrite
        )
        
        if result.success:
            successful += 1
            print(f"✓ {result.video_id}: {result.chunk_count} chunks → {result.output_path}")
        else:
            failed += 1
            print(f"✗ {result.video_id}: {result.error}")
    
    stats = ProcessingStats(
        total_videos=len(video_urls),
        successful=successful,
        failed=failed,
        skipped=skipped
    )
    
    print(f"\n--- Batch Processing Complete ---")
    print(f"Total: {stats.total_videos}")
    print(f"Successful: {stats.successful}")
    print(f"Failed: {stats.failed}")
    if stats.skipped > 0:
        print(f"Skipped: {stats.skipped}")
    
    return stats


def check_prerequisites() -> bool:
    """
    Check if all prerequisites are met before processing.
    
    Returns:
        True if all checks pass, False otherwise.
    """
    try:
        with yaspin(text="Checking Ollama connection...", color="blue") as spinner:
            if not ensure_connection():
                spinner.fail("✗")
                print(f"❌ Ollama connection failed")
                return False
            spinner.ok("✓")
        
        # Create necessary directories
        config.create_directories()
        
        return True
        
    except LLMConnectionError as e:
        print(f"❌ {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during prerequisite check: {e}")
        return False


# Legacy function for backwards compatibility
def main() -> None:
    """Legacy main function for backwards compatibility."""
    import argparse
    from .utils import read_video_list
    
    parser = argparse.ArgumentParser(description="YouTube transcript → Ollama summary")
    parser.add_argument("list_file", help="Text file of YouTube URLs/IDs")
    parser.add_argument("--model", default=config.OLLAMA_MODEL, help="Ollama model tag")
    args = parser.parse_args()
    
    # Check prerequisites
    if not check_prerequisites():
        return
    
    try:
        # Read video list
        video_urls = read_video_list(Path(args.list_file))
        
        # Process videos
        process_video_list(video_urls, model=args.model)
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()