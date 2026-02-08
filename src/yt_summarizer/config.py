"""
Configuration management for yt-summarizer.

Supports layered configuration with priority: env vars > YAML config > defaults.
Uses XDG-compliant paths for cross-platform compatibility.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

# Load .env file if it exists (for backwards compatibility)
load_dotenv()


def get_config_dir() -> Path:
    """Get XDG-compliant config directory.

    Priority:
    1. XDG_CONFIG_HOME environment variable
    2. ~/.config/youtube-summarizer (default)

    Returns:
        Path to configuration directory.
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg_config:
        return Path(xdg_config) / "youtube-summarizer"
    return Path.home() / ".config" / "youtube-summarizer"


def get_data_dir() -> Path:
    """Get XDG-compliant data directory.

    Priority:
    1. XDG_DATA_HOME environment variable
    2. ~/.local/share/youtube-summarizer (default)

    Returns:
        Path to data directory.
    """
    xdg_data = os.environ.get("XDG_DATA_HOME", "")
    if xdg_data:
        return Path(xdg_data) / "youtube-summarizer"
    return Path.home() / ".local" / "share" / "youtube-summarizer"


def load_yaml_config() -> Dict[str, Any]:
    """Load configuration from YAML file.

    Returns:
        Dictionary with configuration values, or empty dict if file doesn't exist.
    """
    config_file = get_config_dir() / "config.yaml"

    if not config_file.exists():
        return {}

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, OSError):
        return {}


def get_config_value(key: str, default: Any, yaml_config: Dict[str, Any]) -> Any:
    """Get config value with priority: env var > yaml > default.

    Args:
        key: Configuration key (uppercase for env, lowercase for yaml).
        default: Default value if not found.
        yaml_config: Loaded YAML configuration dictionary.

    Returns:
        Configuration value.
    """
    # Check environment variable (uppercase)
    env_val = os.environ.get(key.upper())
    if env_val is not None:
        return env_val

    # Check YAML config (lowercase with underscores)
    yaml_key = key.lower()
    yaml_val = yaml_config.get(yaml_key)
    if yaml_val is not None:
        return yaml_val

    return default


def resolve_path(path_str: str, default_base: Optional[Path] = None) -> Path:
    """Resolve path, handling relative and absolute paths.

    Args:
        path_str: Path string to resolve.
        default_base: Base path for relative paths (defaults to config dir).

    Returns:
        Resolved absolute Path.
    """
    path = Path(path_str)

    # Already absolute
    if path.is_absolute():
        return path

    # Handle home directory
    if str(path).startswith("~"):
        return path.expanduser()

    # Relative path - resolve from base
    base = default_base or get_config_dir()
    return base / path


def create_default_config() -> Path:
    """Create default configuration file.

    Returns:
        Path to created config file.
    """
    config_dir = get_config_dir()
    config_file = config_dir / "config.yaml"

    default_config = """\
# YouTube Summarizer Configuration
# Documentation: https://github.com/lancekrogers/youtube-summarizer

# Ollama settings
ollama_url: http://localhost:11434
ollama_model: llama3.2:latest
ollama_timeout: 300

# Processing settings
context_window: 120000
chunk_size: 2048
chunk_overlap: 200
rate_limit_delay: 2.0

# YouTube settings
youtube_timeout: 30

# Default video list file name
default_video_list: videos.txt

# Directory settings (uncomment to customize)
# data_dir: ~/Documents/youtube-summarizer/data
# docs_dir: ~/Documents/youtube-summarizer/docs
# logs_dir: ~/Documents/youtube-summarizer/logs
# research_plans_dir: ~/Documents/youtube-summarizer/research_plans
"""

    config_dir.mkdir(parents=True, exist_ok=True)

    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(default_config)

    return config_file


# Configuration directory paths (module-level for easy access)
CONFIG_DIR = get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.yaml"


class Config:
    """Configuration settings with XDG-compliant paths.

    Loads settings with priority: environment variables > YAML config > defaults.
    """

    def __init__(self):
        """Initialize configuration by loading from all sources."""
        self._yaml_config = load_yaml_config()
        self._load_settings()

    def _load_settings(self) -> None:
        """Load all configuration settings."""
        yc = self._yaml_config

        # Ollama settings
        self.OLLAMA_URL: str = get_config_value("OLLAMA_URL", "http://localhost:11434", yc)
        self.OLLAMA_MODEL: str = get_config_value("OLLAMA_MODEL", "llama3.2:latest", yc)
        self.OLLAMA_TIMEOUT: int = int(get_config_value("OLLAMA_TIMEOUT", 300, yc))

        # Model context settings
        self.CONTEXT_WINDOW: int = int(get_config_value("CONTEXT_WINDOW", 120000, yc))

        # Processing settings
        self.CHUNK_SIZE: int = int(get_config_value("CHUNK_SIZE", 2048, yc))
        self.CHUNK_OVERLAP: int = int(get_config_value("CHUNK_OVERLAP", 200, yc))
        self.RATE_LIMIT_DELAY: float = float(get_config_value("RATE_LIMIT_DELAY", 2.0, yc))

        # YouTube settings
        self.YOUTUBE_TIMEOUT: int = int(get_config_value("YOUTUBE_TIMEOUT", 30, yc))

        # File settings
        self.DEFAULT_VIDEO_LIST: str = get_config_value("DEFAULT_VIDEO_LIST", "videos.txt", yc)

        # Directory settings - default to XDG-compliant paths
        default_data_dir = str(get_config_dir() / "data")
        data_dir_str = get_config_value("DATA_DIR", default_data_dir, yc)
        self.DATA_DIR: Path = resolve_path(data_dir_str)

        self.RAW_DIR: Path = self.DATA_DIR / "raw"

        default_docs_dir = str(self.DATA_DIR / "docs")
        docs_dir_str = get_config_value("DOCS_DIR", default_docs_dir, yc)
        self.DOCS_DIR: Path = resolve_path(docs_dir_str)

        default_logs_dir = str(get_config_dir() / "logs")
        logs_dir_str = get_config_value("LOGS_DIR", default_logs_dir, yc)
        self.LOGS_DIR: Path = resolve_path(logs_dir_str)

        self.LOG_FILE: Path = self.LOGS_DIR / "ingest.jsonl"

        # Research plans directory
        default_plans_dir = str(get_config_dir() / "research_plans")
        plans_dir_str = get_config_value("RESEARCH_PLANS_DIR", default_plans_dir, yc)
        self.RESEARCH_PLANS_DIR: Path = resolve_path(plans_dir_str)

    def create_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.RAW_DIR.mkdir(parents=True, exist_ok=True)
        self.DOCS_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.RESEARCH_PLANS_DIR.mkdir(parents=True, exist_ok=True)

    def get_ollama_api_url(self, endpoint: str = "generate") -> str:
        """Get the full Ollama API URL for the given endpoint.

        Args:
            endpoint: API endpoint name.

        Returns:
            Full URL for the endpoint.
        """
        return f"{self.OLLAMA_URL.rstrip('/')}/api/{endpoint}"

    def reload(self) -> None:
        """Reload configuration from files."""
        self._yaml_config = load_yaml_config()
        self._load_settings()


# Global config instance
config = Config()
