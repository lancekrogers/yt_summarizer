"""
High-level summarization orchestration module.

Coordinates transcript fetching, chunking, and summarization into a unified workflow.
"""

from __future__ import annotations

import logging
from typing import List, NamedTuple, Optional

from .config import config
from .io_utils import validate_url, validate_model_name, ValidationError
from .llm import summarise_chunk, summarise_transcript, LLMError
from .transcript import fetch_transcript, chunk_text, TranscriptData, TranscriptError
from .utils import slugify, create_markdown_summary, save_markdown

logger = logging.getLogger(__name__)


class SummarizationResult(NamedTuple):
    """Result of summarizing a video."""
    success: bool
    video_id: str
    title: str
    error: Optional[str] = None
    output_path: Optional[str] = None
    chunk_count: int = 0


class VideoSummarizer:
    """High-level video summarization orchestrator."""
    
    def __init__(self, model: str = None, use_cache: bool = True):
        """
        Initialize the summarizer.
        
        Args:
            model: Ollama model to use for summarization.
            use_cache: Whether to use transcript caching.
        """
        self.model = model or config.OLLAMA_MODEL
        self.use_cache = use_cache
        
        # Validate model name
        try:
            self.model = validate_model_name(self.model)
        except ValidationError as e:
            raise ValueError(f"Invalid model name: {e}")
    
    def summarize_video(self, video_url: str, overwrite: bool = False) -> SummarizationResult:
        """
        Summarize a single video from URL or ID.
        
        Args:
            video_url: YouTube URL or video ID.
            overwrite: Whether to overwrite existing summaries.
            
        Returns:
            SummarizationResult with outcome and details.
        """
        try:
            # Validate input
            validated_url = validate_url(video_url)
            
            # Fetch transcript
            logger.info(f"Fetching transcript for: {validated_url}")
            transcript_data = fetch_transcript(
                validated_url, 
                use_cache=self.use_cache
            )
            
            # Check if summary already exists
            if not overwrite:
                slug = slugify(transcript_data.title)
                summary_path = config.DOCS_DIR / f"{slug}.md"
                if summary_path.exists():
                    logger.info(f"Summary already exists for {transcript_data.video_id}, skipping")
                    return SummarizationResult(
                        success=False,
                        video_id=transcript_data.video_id,
                        title=transcript_data.title,
                        error="Summary already exists (use overwrite=True to replace)"
                    )
            
            # Chunk the transcript
            chunks = chunk_text(transcript_data.text)
            logger.info(f"Split transcript into {len(chunks)} chunks")
            
            # Summarize each chunk
            chunk_summaries = []
            for i, chunk in enumerate(chunks, 1):
                logger.info(f"Summarizing chunk {i}/{len(chunks)}")
                try:
                    summary = summarise_chunk(chunk, self.model)
                    chunk_summaries.append(summary)
                except LLMError as e:
                    logger.error(f"Failed to summarize chunk {i}: {e}")
                    return SummarizationResult(
                        success=False,
                        video_id=transcript_data.video_id,
                        title=transcript_data.title,
                        error=f"Failed to summarize chunk {i}: {e}"
                    )
            
            # Generate executive summary
            logger.info("Generating executive summary")
            try:
                executive_summary = summarise_transcript(chunk_summaries, self.model)
            except LLMError as e:
                logger.error(f"Failed to generate executive summary: {e}")
                return SummarizationResult(
                    success=False,
                    video_id=transcript_data.video_id,
                    title=transcript_data.title,
                    error=f"Failed to generate executive summary: {e}"
                )
            
            # Save markdown summary
            try:
                output_path = save_markdown(
                    transcript_data.video_id,
                    transcript_data.title,
                    executive_summary,
                    chunk_summaries,
                    self.model
                )
                
                logger.info(f"Saved summary to: {output_path}")
                
                return SummarizationResult(
                    success=True,
                    video_id=transcript_data.video_id,
                    title=transcript_data.title,
                    output_path=str(output_path),
                    chunk_count=len(chunks)
                )
                
            except Exception as e:
                logger.error(f"Failed to save summary: {e}")
                return SummarizationResult(
                    success=False,
                    video_id=transcript_data.video_id,
                    title=transcript_data.title,
                    error=f"Failed to save summary: {e}"
                )
        
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            return SummarizationResult(
                success=False,
                video_id="unknown",
                title="unknown",
                error=f"Validation error: {e}"
            )
        
        except TranscriptError as e:
            logger.error(f"Transcript error: {e}")
            return SummarizationResult(
                success=False,
                video_id="unknown",
                title="unknown", 
                error=f"Transcript error: {e}"
            )
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return SummarizationResult(
                success=False,
                video_id="unknown",
                title="unknown",
                error=f"Unexpected error: {e}"
            )
    
    def summarize_videos(self, video_urls: List[str], overwrite: bool = False) -> List[SummarizationResult]:
        """
        Summarize multiple videos.
        
        Args:
            video_urls: List of YouTube URLs or video IDs.
            overwrite: Whether to overwrite existing summaries.
            
        Returns:
            List of SummarizationResult for each video.
        """
        results = []
        
        for i, video_url in enumerate(video_urls, 1):
            logger.info(f"Processing video {i}/{len(video_urls)}: {video_url}")
            result = self.summarize_video(video_url, overwrite=overwrite)
            results.append(result)
            
            if result.success:
                logger.info(f"✓ Successfully summarized: {result.title}")
            else:
                logger.warning(f"✗ Failed to summarize {video_url}: {result.error}")
        
        return results
    
    def get_summary_stats(self, results: List[SummarizationResult]) -> dict:
        """
        Get statistics from summarization results.
        
        Args:
            results: List of summarization results.
            
        Returns:
            Dictionary with statistics.
        """
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        total_chunks = sum(r.chunk_count for r in results if r.success)
        
        return {
            "total": len(results),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(results) if results else 0,
            "total_chunks_processed": total_chunks
        }


def quick_summarize(video_url: str, model: str = None, use_cache: bool = True, overwrite: bool = False) -> SummarizationResult:
    """
    Quick function to summarize a single video.
    
    Args:
        video_url: YouTube URL or video ID.
        model: Ollama model to use.
        use_cache: Whether to use caching.
        overwrite: Whether to overwrite existing summaries.
        
    Returns:
        SummarizationResult with outcome.
    """
    summarizer = VideoSummarizer(model=model, use_cache=use_cache)
    return summarizer.summarize_video(video_url, overwrite=overwrite)


def batch_summarize(video_urls: List[str], model: str = None, use_cache: bool = True, overwrite: bool = False) -> List[SummarizationResult]:
    """
    Batch summarize multiple videos.
    
    Args:
        video_urls: List of YouTube URLs or video IDs.
        model: Ollama model to use.
        use_cache: Whether to use caching.
        overwrite: Whether to overwrite existing summaries.
        
    Returns:
        List of SummarizationResult for each video.
    """
    summarizer = VideoSummarizer(model=model, use_cache=use_cache)
    return summarizer.summarize_videos(video_urls, overwrite=overwrite)