"""
Input/output utilities for file handling and validation.

Provides secure file operations and input validation for the YouTube summarizer.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from .transcript import extract_video_id, TranscriptError


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_file_path(path: str | Path) -> Path:
    """
    Validate and sanitize a file path for security.
    
    Args:
        path: File path to validate.
        
    Returns:
        Validated Path object.
        
    Raises:
        ValidationError: If path is invalid or unsafe.
    """
    if isinstance(path, str):
        path = Path(path)
    
    # Convert to absolute path to prevent directory traversal
    try:
        resolved_path = path.resolve()
    except (OSError, RuntimeError) as e:
        raise ValidationError(f"Invalid path: {e}")
    
    # Check for path traversal attempts
    if ".." in str(path) or str(path).startswith("/"):
        # Allow absolute paths but be careful with .. sequences
        if ".." in path.parts:
            raise ValidationError("Path traversal detected in file path")
    
    # Check if path contains invalid characters
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
    if any(char in str(path) for char in invalid_chars):
        raise ValidationError(f"Invalid characters in path: {path}")
    
    return resolved_path


def validate_url(url: str) -> str:
    """
    Validate a YouTube URL or video ID.
    
    Args:
        url: URL or video ID to validate.
        
    Returns:
        Validated URL/ID string.
        
    Raises:
        ValidationError: If URL is invalid.
    """
    if not url or not isinstance(url, str):
        raise ValidationError("URL cannot be empty")
    
    url = url.strip()
    
    # Check for common malicious patterns
    suspicious_patterns = [
        r'javascript:',
        r'data:',
        r'vbscript:',
        r'file:',
        r'ftp:',
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            raise ValidationError(f"Suspicious URL pattern detected: {pattern}")
    
    # If it looks like a URL, validate it
    if url.startswith(('http://', 'https://')):
        parsed = urlparse(url)
        if not parsed.netloc:
            raise ValidationError("Invalid URL format")
        
        # Only allow YouTube domains
        allowed_domains = ['youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com']
        if parsed.netloc.lower() not in allowed_domains:
            raise ValidationError(f"Only YouTube URLs are allowed, got: {parsed.netloc}")
    
    # Validate that we can extract a video ID
    try:
        extract_video_id(url)
    except TranscriptError as e:
        raise ValidationError(f"Invalid YouTube URL/ID: {e}")
    
    return url


def validate_model_name(model: str) -> str:
    """
    Validate an Ollama model name.
    
    Args:
        model: Model name to validate.
        
    Returns:
        Validated model name.
        
    Raises:
        ValidationError: If model name is invalid.
    """
    if not model or not isinstance(model, str):
        raise ValidationError("Model name cannot be empty")
    
    model = model.strip()
    
    # Basic validation - model names should be alphanumeric with : . - _
    if not re.match(r'^[a-zA-Z0-9\.\-_:]+$', model):
        raise ValidationError(f"Invalid model name format: {model}")
    
    # Prevent obviously malicious names
    if any(bad in model.lower() for bad in ['..', '/', '\\', 'script', 'exec']):
        raise ValidationError(f"Suspicious model name: {model}")
    
    return model


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename for safe filesystem usage.
    
    Args:
        filename: Filename to sanitize.
        max_length: Maximum allowed filename length.
        
    Returns:
        Sanitized filename.
        
    Raises:
        ValidationError: If filename cannot be sanitized.
    """
    if not filename:
        raise ValidationError("Filename cannot be empty")
    
    # Remove/replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)  # Remove control characters
    sanitized = sanitized.strip('. ')  # Remove leading/trailing dots and spaces
    
    # Ensure filename is not too long
    if len(sanitized) > max_length:
        name, ext = os.path.splitext(sanitized)
        max_name_length = max_length - len(ext)
        sanitized = name[:max_name_length] + ext
    
    # Ensure we have a valid filename
    if not sanitized or sanitized in ['.', '..']:
        raise ValidationError("Invalid filename after sanitization")
    
    return sanitized


def validate_video_list(videos: List[str]) -> List[str]:
    """
    Validate a list of video URLs/IDs.
    
    Args:
        videos: List of video URLs/IDs to validate.
        
    Returns:
        List of validated URLs/IDs.
        
    Raises:
        ValidationError: If any video URL/ID is invalid.
    """
    if not videos:
        raise ValidationError("Video list cannot be empty")
    
    if len(videos) > 1000:  # Reasonable limit
        raise ValidationError("Too many videos in list (max 1000)")
    
    validated = []
    for i, video in enumerate(videos):
        try:
            validated_video = validate_url(video)
            validated.append(validated_video)
        except ValidationError as e:
            raise ValidationError(f"Invalid video at position {i+1}: {e}")
    
    return validated


def check_disk_space(path: Path, required_mb: int = 100) -> bool:
    """
    Check if there's enough disk space for operations.
    
    Args:
        path: Path to check disk space for.
        required_mb: Required space in megabytes.
        
    Returns:
        True if enough space is available.
    """
    try:
        import shutil
        free_bytes = shutil.disk_usage(path).free
        required_bytes = required_mb * 1024 * 1024
        return free_bytes >= required_bytes
    except Exception:
        # If we can't check, assume we have space
        return True


def safe_read_file(path: Path, max_size_mb: int = 10) -> str:
    """
    Safely read a file with size limits.
    
    Args:
        path: Path to file to read.
        max_size_mb: Maximum file size in megabytes.
        
    Returns:
        File contents as string.
        
    Raises:
        ValidationError: If file is too large or cannot be read safely.
    """
    validated_path = validate_file_path(path)
    
    if not validated_path.exists():
        raise ValidationError(f"File does not exist: {path}")
    
    if not validated_path.is_file():
        raise ValidationError(f"Path is not a file: {path}")
    
    # Check file size
    file_size = validated_path.stat().st_size
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if file_size > max_size_bytes:
        raise ValidationError(f"File too large: {file_size} bytes (max {max_size_bytes})")
    
    try:
        return validated_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        raise ValidationError("File is not valid UTF-8 text")
    except Exception as e:
        raise ValidationError(f"Error reading file: {e}")


def safe_write_file(path: Path, content: str, max_size_mb: int = 10) -> None:
    """
    Safely write content to a file with validation.
    
    Args:
        path: Path to write to.
        content: Content to write.
        max_size_mb: Maximum content size in megabytes.
        
    Raises:
        ValidationError: If content is too large or path is invalid.
    """
    validated_path = validate_file_path(path)
    
    # Check content size
    content_size = len(content.encode('utf-8'))
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if content_size > max_size_bytes:
        raise ValidationError(f"Content too large: {content_size} bytes (max {max_size_bytes})")
    
    # Check disk space
    if not check_disk_space(validated_path.parent):
        raise ValidationError("Insufficient disk space")
    
    # Ensure parent directory exists
    validated_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        validated_path.write_text(content, encoding='utf-8')
    except Exception as e:
        raise ValidationError(f"Error writing file: {e}")