"""Configuration and settings management for LLM access."""

import os
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    # If python-dotenv is not installed, define a no-op function
    def load_dotenv(*args, **kwargs):
        pass


def load_env() -> None:
    """
    Load environment variables from a .env file if present.
    
    Does nothing if there is no .env file.
    """
    load_dotenv()


def get_google_api_key() -> str:
    """
    Get the Google API key from environment variables.
    
    Returns:
        str: The Google API key
        
    Raises:
        ValueError: If GOOGLE_API_KEY is not set
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY environment variable is required but not set. "
            "Please set it in your .env file or environment."
        )
    return api_key


def get_openai_api_key() -> Optional[str]:
    """
    Get the OpenAI API key from environment variables.
    
    Returns:
        Optional[str]: The OpenAI API key, or None if not set
    """
    return os.getenv("OPENAI_API_KEY")


def get_default_model_name() -> str:
    """
    Get the default LLM model name from environment variables.
    
    Returns:
        str: The model name, defaults to "gemini-pro" if not set
    """
    return os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")


def get_default_backend_name() -> str:
    """
    Get the default LLM backend name from environment variables.
    
    Returns:
        str: The backend name, defaults to "gemini" if not set
        
    Raises:
        ValueError: If backend is "gemini" but GOOGLE_API_KEY is not set
    """
    backend = os.getenv("LLM_BACKEND_NAME", "openai")
    
    # Validate that GOOGLE_API_KEY is set if using Gemini backend
    if backend == "gemini":
        try:
            get_google_api_key()
        except ValueError as e:
            raise ValueError(
                f"Backend is set to 'gemini' but GOOGLE_API_KEY is missing. "
                f"Please set GOOGLE_API_KEY in your .env file or environment. "
                f"Original error: {e}"
            )
    
    return backend

