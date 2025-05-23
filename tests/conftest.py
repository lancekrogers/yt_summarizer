"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch

from yt_summarizer.config import Config


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_config(temp_dir):
    """Mock config with temporary directories."""
    config = Config()
    config.DATA_DIR = temp_dir / "data"
    config.RAW_DIR = config.DATA_DIR / "raw"
    config.DOCS_DIR = temp_dir / "docs"
    config.LOGS_DIR = temp_dir / "logs"
    config.LOG_FILE = config.LOGS_DIR / "ingest.jsonl"
    return config


@pytest.fixture
def mock_ollama_response():
    """Mock successful Ollama response."""
    return {
        "response": "This is a test summary of the video content.",
        "done": True
    }


@pytest.fixture
def mock_youtube_transcript():
    """Mock YouTube transcript data."""
    return [
        {"text": "Hello everyone", "start": 0.0, "duration": 2.0},
        {"text": "Welcome to my channel", "start": 2.0, "duration": 3.0},
        {"text": "Today we will learn about Python", "start": 5.0, "duration": 4.0}
    ]


@pytest.fixture
def mock_video_title():
    """Mock YouTube video title."""
    return "Learn Python in 10 Minutes"


@pytest.fixture
def sample_video_id():
    """Sample YouTube video ID for testing."""
    return "dQw4w9WgXcQ"