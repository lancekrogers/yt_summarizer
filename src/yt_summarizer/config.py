"""
Configuration management for yt-summarizer.

Loads settings from .env file with sensible defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


class Config:
    """Configuration settings for the application."""
    
    # Ollama settings
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
    
    # Model context settings
    # Context window size of your LLM (used for reference/validation)
    CONTEXT_WINDOW: int = int(os.getenv("CONTEXT_WINDOW", "120000"))

    # Processing settings
    # Chunk size should be ~25-50% of context window to leave room for prompt + response
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "2048"))
    # Overlap between chunks for better context continuity (0 = no overlap)
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    RATE_LIMIT_DELAY: float = float(os.getenv("RATE_LIMIT_DELAY", "2.0"))
    
    # Directory settings
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))
    RAW_DIR: Path = DATA_DIR / "raw"
    DOCS_DIR: Path = Path(os.getenv("DOCS_DIR", "data/docs"))
    LOGS_DIR: Path = Path(os.getenv("LOGS_DIR", "logs"))
    
    # File settings
    LOG_FILE: Path = LOGS_DIR / "ingest.jsonl"
    DEFAULT_VIDEO_LIST: str = os.getenv("DEFAULT_VIDEO_LIST", "videos.txt")
    
    # Timeout settings
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "300"))
    YOUTUBE_TIMEOUT: int = int(os.getenv("YOUTUBE_TIMEOUT", "30"))
    
    @classmethod
    def create_directories(cls) -> None:
        """Create necessary directories if they don't exist."""
        cls.RAW_DIR.mkdir(parents=True, exist_ok=True)
        cls.DOCS_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_ollama_api_url(cls, endpoint: str = "generate") -> str:
        """Get the full Ollama API URL for the given endpoint."""
        return f"{cls.OLLAMA_URL.rstrip('/')}/api/{endpoint}"


# Global config instance
config = Config()