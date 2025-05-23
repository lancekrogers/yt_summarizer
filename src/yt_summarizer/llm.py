"""
LLM integration using Ollama for summarization.

Provides functions for connecting to Ollama and generating summaries.
"""

from __future__ import annotations

import logging
from typing import List

import ollama
import requests
from requests.exceptions import ConnectionError, RequestException, Timeout

from .config import config

logger = logging.getLogger(__name__)


class LLMConnectionError(Exception):
    """Raised when unable to connect to Ollama."""
    pass


class LLMError(Exception):
    """Raised when LLM operation fails."""
    pass


# Prompt templates - configurable via environment or parameters
DEFAULT_CHUNK_PROMPT = """You are a helpful assistant that summarizes video transcript content. Please provide a clear, concise summary of the key points discussed in this transcript chunk:

{chunk}

Focus on the main topics, important information, and key takeaways."""

DEFAULT_EXECUTIVE_PROMPT = """Please create a comprehensive executive summary by combining these individual section summaries into a cohesive overview:

{bullet_summaries}

Provide a clear, well-structured summary that captures the overall content and main themes."""

# Allow customization via config
def get_chunk_prompt_template() -> str:
    """Get the chunk summarization prompt template."""
    import os
    return os.getenv("CHUNK_PROMPT_TEMPLATE", DEFAULT_CHUNK_PROMPT)

def get_executive_prompt_template() -> str:
    """Get the executive summary prompt template.""" 
    import os
    return os.getenv("EXECUTIVE_PROMPT_TEMPLATE", DEFAULT_EXECUTIVE_PROMPT)


def ensure_connection() -> bool:
    """
    Check if Ollama server is accessible and the configured model is available.
    
    Returns:
        True if connection successful, False otherwise.
        
    Raises:
        LLMConnectionError: If unable to connect to Ollama server.
    """
    try:
        # Check if server is running
        response = requests.get(
            f"{config.OLLAMA_URL}/api/tags",
            timeout=config.OLLAMA_TIMEOUT
        )
        response.raise_for_status()
        
        # Check if our model is available
        models = response.json().get("models", [])
        model_names = [model["name"] for model in models]
        
        if config.OLLAMA_MODEL not in model_names:
            logger.warning(f"Model {config.OLLAMA_MODEL} not found. Available models: {model_names}")
            return False
            
        logger.info(f"Connected to Ollama. Model {config.OLLAMA_MODEL} is available.")
        return True
        
    except (ConnectionError, Timeout) as e:
        raise LLMConnectionError(f"Cannot connect to Ollama server at {config.OLLAMA_URL}: {e}")
    except RequestException as e:
        raise LLMConnectionError(f"Error checking Ollama connection: {e}")


def summarise_chunk(chunk: str, model: str | None = None) -> str:
    """
    Summarize a single chunk of transcript text.
    
    Args:
        chunk: The text chunk to summarize.
        model: Optional model name, defaults to config.OLLAMA_MODEL.
        
    Returns:
        The generated summary.
        
    Raises:
        LLMError: If summarization fails.
    """
    if model is None:
        model = config.OLLAMA_MODEL
        
    prompt = get_chunk_prompt_template().format(chunk=chunk)
    
    try:
        # Try using the official ollama client first
        try:
            response = ollama.generate(
                model=model,
                prompt=prompt,
                options={"temperature": 0.7}
            )
            return response["response"].strip()
            
        except Exception as ollama_error:
            logger.warning(f"Ollama client failed, falling back to HTTP: {ollama_error}")
            
            # Fallback to raw HTTP request
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7}
            }
            
            response = requests.post(
                config.get_ollama_api_url("generate"),
                json=payload,
                timeout=config.OLLAMA_TIMEOUT
            )
            response.raise_for_status()
            
            return response.json()["response"].strip()
            
    except Exception as e:
        raise LLMError(f"Failed to summarize chunk: {e}")


def summarise_transcript(chunk_summaries: List[str], model: str | None = None) -> str:
    """
    Generate an executive summary from multiple chunk summaries.
    
    Args:
        chunk_summaries: List of individual chunk summaries.
        model: Optional model name, defaults to config.OLLAMA_MODEL.
        
    Returns:
        The executive summary.
        
    Raises:
        LLMError: If summarization fails.
    """
    if model is None:
        model = config.OLLAMA_MODEL
        
    bullet_summaries = "\n\n".join(chunk_summaries)
    prompt = get_executive_prompt_template().format(bullet_summaries=bullet_summaries)
    
    try:
        # Try using the official ollama client first
        try:
            response = ollama.generate(
                model=model,
                prompt=prompt,
                options={"temperature": 0.7}
            )
            return response["response"].strip()
            
        except Exception as ollama_error:
            logger.warning(f"Ollama client failed, falling back to HTTP: {ollama_error}")
            
            # Fallback to raw HTTP request
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7}
            }
            
            response = requests.post(
                config.get_ollama_api_url("generate"),
                json=payload,
                timeout=config.OLLAMA_TIMEOUT
            )
            response.raise_for_status()
            
            return response.json()["response"].strip()
            
    except Exception as e:
        raise LLMError(f"Failed to generate executive summary: {e}")


def test_model_connection(model: str | None = None) -> bool:
    """
    Test if we can successfully generate text with the specified model.
    
    Args:
        model: Optional model name, defaults to config.OLLAMA_MODEL.
        
    Returns:
        True if test successful, False otherwise.
    """
    if model is None:
        model = config.OLLAMA_MODEL
        
    try:
        test_prompt = "Say 'test successful' in exactly two words."
        response = summarise_chunk(test_prompt, model)
        logger.info(f"Model test response: {response}")
        return True
    except Exception as e:
        logger.error(f"Model test failed: {e}")
        return False