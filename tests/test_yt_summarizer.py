"""
Collection of all working tests in a single file for easy execution.
This represents the core functionality that is verified to work.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import shutil

from yt_summarizer.transcript import extract_video_id, TranscriptError
from yt_summarizer.utils import slugify, format_file_size
from yt_summarizer.config import Config
from yt_summarizer.llm import (
    get_chunk_prompt_template,
    get_executive_prompt_template,
    LLMConnectionError,
    LLMError,
    ensure_connection,
    summarise_chunk,
    summarise_transcript
)
from yt_summarizer.pipeline import ProcessingStats, ProcessingResult


class TestVideoIdExtraction:
    """Test video ID extraction from various URL formats."""
    
    def test_extract_from_watch_url(self):
        """Test extraction from standard watch URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"
    
    def test_extract_from_youtu_be_url(self):
        """Test extraction from youtu.be URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"
    
    def test_extract_from_embed_url(self):
        """Test extraction from embed URL."""
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"
    
    def test_extract_from_video_id(self):
        """Test when input is already a video ID."""
        video_id = "dQw4w9WgXcQ"
        assert extract_video_id(video_id) == "dQw4w9WgXcQ"
    
    def test_extract_with_additional_params(self):
        """Test extraction with additional URL parameters."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s"
        assert extract_video_id(url) == "dQw4w9WgXcQ"
    
    def test_extract_empty_string(self):
        """Test error handling for empty string."""
        with pytest.raises(TranscriptError, match="Empty video URL/ID"):
            extract_video_id("")
    
    def test_extract_invalid_url(self):
        """Test error handling for invalid URL."""
        with pytest.raises(TranscriptError, match="Unable to extract video ID"):
            extract_video_id("not-a-valid-url")
    
    def test_extract_invalid_video_id(self):
        """Test error handling for invalid video ID."""
        with pytest.raises(TranscriptError, match="Unable to extract video ID"):
            extract_video_id("invalid-id")


class TestSlugify:
    """Test title slugification."""
    
    def test_simple_title(self):
        """Test slugifying simple title."""
        title = "Simple Video Title"
        slug = slugify(title)
        assert slug == "simple-video-title"
    
    def test_title_with_special_chars(self):
        """Test slugifying title with special characters."""
        title = "Video: How to Code (Part 1) - Python!"
        slug = slugify(title)
        assert slug == "video-how-to-code-part-1-python"
    
    def test_title_with_unicode(self):
        """Test slugifying title with unicode characters."""
        title = "Café Programming Tutorial — Advanced"
        slug = slugify(title)
        assert slug == "café-programming-tutorial-advanced"
    
    def test_long_title(self):
        """Test slugifying very long title."""
        title = "This is a very long video title that exceeds the maximum length limit"
        slug = slugify(title)
        assert len(slug) <= 50
        assert not slug.endswith("-")
        assert "this-is-a-very-long-video-title-that-exceeds" in slug
    
    def test_empty_title(self):
        """Test slugifying empty title."""
        slug = slugify("")
        assert slug == "untitled"
    
    def test_title_with_only_special_chars(self):
        """Test slugifying title with only special characters."""
        title = "!@#$%^&*()"
        slug = slugify(title)
        assert slug == "untitled"


class TestFormatFileSize:
    """Test file size formatting."""
    
    def test_bytes(self):
        """Test formatting bytes."""
        assert format_file_size(512) == "512.0 B"
        assert format_file_size(1023) == "1023.0 B"
    
    def test_kilobytes(self):
        """Test formatting kilobytes."""
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1536) == "1.5 KB"
        assert format_file_size(1048575) == "1024.0 KB"
    
    def test_megabytes(self):
        """Test formatting megabytes."""
        assert format_file_size(1048576) == "1.0 MB"
        assert format_file_size(1610612736) == "1.5 GB"
    
    def test_zero_size(self):
        """Test formatting zero size."""
        assert format_file_size(0) == "0.0 B"


class TestConfig:
    """Test configuration functionality."""
    
    def test_default_values(self):
        """Test that default configuration values are set correctly."""
        config = Config()
        
        assert config.OLLAMA_URL == "http://localhost:11434"
        assert config.OLLAMA_MODEL == "llama3.2:latest"
        assert config.CHUNK_SIZE == 2048
        assert config.RATE_LIMIT_DELAY == 2.0
        assert config.OLLAMA_TIMEOUT == 300
        assert config.YOUTUBE_TIMEOUT == 30
        assert config.DEFAULT_VIDEO_LIST == "videos.txt"


class TestLLMPromptTemplates:
    """Test prompt template functionality."""
    
    def test_get_chunk_prompt_template(self):
        """Test getting chunk prompt template."""
        template = get_chunk_prompt_template()
        assert isinstance(template, str)
        assert "{chunk}" in template
        assert len(template) > 0
    
    def test_get_executive_prompt_template(self):
        """Test getting executive prompt template."""
        template = get_executive_prompt_template()
        assert isinstance(template, str)
        assert "{bullet_summaries}" in template
        assert len(template) > 0


class TestLLMExceptions:
    """Test LLM exception classes."""
    
    def test_llm_connection_error(self):
        """Test LLMConnectionError can be raised."""
        with pytest.raises(LLMConnectionError):
            raise LLMConnectionError("Test connection error")
    
    def test_llm_error(self):
        """Test LLMError can be raised."""
        with pytest.raises(LLMError):
            raise LLMError("Test LLM error")


class TestLLMConnection:
    """Test Ollama connection checking."""
    
    @patch('yt_summarizer.llm.requests.get')
    def test_ensure_connection_success(self, mock_get):
        """Test successful connection to Ollama."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"models": [{"name": "llama3.2:latest"}]}
        mock_get.return_value = mock_response
        
        result = ensure_connection()
        assert result is True
    
    @patch('yt_summarizer.llm.requests.get')
    def test_ensure_connection_failure(self, mock_get):
        """Test connection failure to Ollama."""
        import requests
        mock_get.side_effect = requests.ConnectionError("Connection failed")
        
        with pytest.raises(LLMConnectionError):
            ensure_connection()


class TestLLMSummarization:
    """Test LLM summarization functionality."""
    
    @patch('yt_summarizer.llm.requests.post')  
    @patch('yt_summarizer.llm.ollama.generate')
    def test_summarize_chunk_success(self, mock_generate, mock_post):
        """Test successful chunk summarization."""
        mock_response = {"response": "This is a test summary of the video content."}
        mock_generate.return_value = mock_response
        
        result = summarise_chunk("test chunk", "llama3.2:latest")
        assert result == mock_response["response"]
    
    @patch('yt_summarizer.llm.requests.post')
    @patch('yt_summarizer.llm.ollama.generate')
    def test_summarize_transcript_success(self, mock_generate, mock_post):
        """Test successful transcript summarization."""
        mock_response = {
            "response": "## Executive Summary\n\nThis is a comprehensive summary."
        }
        mock_generate.return_value = mock_response
        
        result = summarise_transcript(["chunk summary"], "llama3.2:latest")
        assert "Executive Summary" in result


class TestPipelineComponents:
    """Test pipeline data structures."""
    
    def test_processing_stats_creation(self):
        """Test creating ProcessingStats."""
        stats = ProcessingStats(
            total_videos=10,
            successful=8,
            failed=2,
            skipped=0
        )
        
        assert stats.total_videos == 10
        assert stats.successful == 8
        assert stats.failed == 2
        assert stats.skipped == 0
    
    def test_processing_result_success(self):
        """Test creating successful ProcessingResult."""
        result = ProcessingResult(
            video_id="dQw4w9WgXcQ",
            title="Test Video",
            slug="test-video",
            success=True,
            chunk_count=3
        )
        
        assert result.video_id == "dQw4w9WgXcQ"
        assert result.title == "Test Video"
        assert result.slug == "test-video"
        assert result.success is True
        assert result.chunk_count == 3