"""LLM client abstraction for OpenAI-compatible APIs."""

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Literal, Optional

try:
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError(
        "openai package is required. Install it with: pip install openai"
    )

from . import settings


BackendName = Literal["gemini", "openai"]


@dataclass
class ModelConfig:
    """Configuration for an LLM model."""
    
    backend: BackendName
    model_name: str
    api_key: str
    base_url: str
    requests_per_minute: int = 60
    
    def create_async_client(self) -> AsyncOpenAI:
        """
        Create and return an AsyncOpenAI client configured with this config's settings.
        
        Returns:
            AsyncOpenAI: Configured async OpenAI client
        """
        return AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )


class ModelClient:
    """
    Client for making LLM API calls with rate limiting.
    
    This client wraps the OpenAI AsyncClient and provides rate limiting
    to respect API rate limits.
    """
    
    def __init__(self, config: ModelConfig):
        """
        Initialize the ModelClient with a ModelConfig.
        
        Args:
            config: ModelConfig instance with API settings
        """
        self.config = config
        self._client = config.create_async_client()
        
        # Rate limiting setup
        self._requests_per_minute = config.requests_per_minute
        self._min_interval = 60.0 / self._requests_per_minute  # seconds between requests
        self._last_request_time: Optional[float] = None
        self._semaphore = asyncio.Semaphore(1)  # Ensure sequential rate limiting
    
    async def generate(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> dict:
        """
        Call the chat completion endpoint and return the full response dict.
        
        This method normalizes messages so that:
        - `role` is preserved
        - `content` is always a string or a list of content parts
        - tool-related fields (tool_calls, tool_call_id, name) are preserved
        
        Args:
            messages: List of message dictionaries for the chat completion
            tools: Optional list of tool definitions for function calling
            **kwargs: Additional arguments to pass to chat.completions.create
            
        Returns:
            dict: The full response dictionary from the API
        """
        async with self._semaphore:
            # Rate limiting: ensure minimum time between requests
            if self._last_request_time is not None:
                elapsed = time.time() - self._last_request_time
                if elapsed < self._min_interval:
                    await asyncio.sleep(self._min_interval - elapsed)

            # --- IMPORTANT PART: normalize messages ---
            normalized_messages: list[dict] = []
            for m in messages:
                role = m.get("role")
                if role == "tool":
                    role = "assistant"
                raw_content = m.get("content", "")

                # If content is already a list (content parts), keep it;
                # otherwise, coerce to string so OpenAI never sees non-string content.
                if isinstance(raw_content, list):
                    norm_content = raw_content
                else:
                    norm_content = str(raw_content)

                msg: dict = {
                    "role": role,
                    "content": norm_content,
                }

                # Preserve tool-related metadata if present
                if "tool_calls" in m and m["tool_calls"] is not None:
                    msg["tool_calls"] = m["tool_calls"]
                if "tool_call_id" in m and m["tool_call_id"] is not None:
                    msg["tool_call_id"] = m["tool_call_id"]
                if "name" in m and m["name"] is not None:
                    msg["name"] = m["name"]

                normalized_messages.append(msg)
            # ------------------------------------------

            # Prepare the request parameters
            params = {
                "model": self.config.model_name,
                "messages": normalized_messages,
                **kwargs,
            }
            
            if tools is not None:
                params["tools"] = tools
                # Let the model decide when to call tools
                params.setdefault("tool_choice", "auto")
            
            # Make the API call
            response = await self._client.chat.completions.create(**params)
            
            # Update last request time
            self._last_request_time = time.time()
            
            # Convert response to dict
            if hasattr(response, "model_dump"):
                return response.model_dump()
            elif hasattr(response, "dict"):
                return response.dict()
            else:
                # Fallback: convert to dict manually
                return {
                    "id": response.id,
                    "object": response.object,
                    "created": response.created,
                    "model": response.model,
                    "choices": [
                        {
                            "index": choice.index,
                            "message": {
                                "role": choice.message.role,
                                "content": choice.message.content,
                                "tool_calls": getattr(choice.message, "tool_calls", None),
                            },
                            "finish_reason": choice.finish_reason,
                        }
                        for choice in response.choices
                    ],
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    } if hasattr(response, "usage") and response.usage else None,
                }


def get_default_model_config() -> ModelConfig:
    """
    Create a ModelConfig using default settings from environment variables.
    
    Uses settings.get_default_backend_name() and get_default_model_name() to
    determine the backend and model. Configures the appropriate API key and
    base URL based on the backend:
    
    - For "gemini": Uses GOOGLE_API_KEY and OpenAI-compatible Gemini endpoint
    - For "openai": Uses OPENAI_API_KEY and default OpenAI endpoint
    
    Returns:
        ModelConfig: Configured model configuration instance
        
    Raises:
        ValueError: If required API keys are missing for the selected backend
    """
    backend_name = settings.get_default_backend_name()
    model_name = settings.get_default_model_name()
    
    # Get requests per minute from environment or use default
    requests_per_minute = int(os.getenv("LLM_REQUESTS_PER_MINUTE", "60"))
    
    if backend_name == "gemini":
        api_key = settings.get_google_api_key()
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    elif backend_name == "openai":
        api_key = settings.get_openai_api_key()
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required for OpenAI backend "
                "but is not set. Please set it in your .env file or environment."
            )
        # Use default OpenAI base URL or from environment
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    else:
        raise ValueError(f"Unknown backend: {backend_name}")
    
    return ModelConfig(
        backend=backend_name,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        requests_per_minute=requests_per_minute,
    )


def get_model_config(
    backend_name: str,
    model_name: str | None = None,
) -> ModelConfig:
    """
    Create a ModelConfig for a specific backend and model.
    
    Args:
        backend_name: Backend name ("gemini" or "openai")
        model_name: Model name (defaults to environment variable or backend-specific default)
        
    Returns:
        ModelConfig: Configured model configuration instance
        
    Raises:
        ValueError: If required API keys are missing for the selected backend
    """
    # Get model name from parameter or environment or use default
    if model_name is None:
        model_name = os.getenv("LLM_MODEL_NAME")
        if model_name is None:
            # Use backend-specific defaults
            if backend_name == "gemini":
                model_name = "gemini-pro"
            elif backend_name == "openai":
                model_name = "gpt-4o-mini"
            else:
                model_name = "gpt-4o-mini"  # Fallback default
    
    # Get requests per minute from environment or use default
    requests_per_minute = int(os.getenv("LLM_REQUESTS_PER_MINUTE", "60"))
    
    if backend_name == "gemini":
        api_key = settings.get_google_api_key()
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    elif backend_name == "openai":
        api_key = settings.get_openai_api_key()
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required for OpenAI backend "
                "but is not set. Please set it in your .env file or environment."
            )
        # Use default OpenAI base URL or from environment
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    else:
        raise ValueError(f"Unknown backend: {backend_name}")
    
    return ModelConfig(
        backend=backend_name,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        requests_per_minute=requests_per_minute,
    )


def get_default_model_client() -> ModelClient:
    """
    Create a ModelClient using default configuration from environment variables.
    
    This is a convenience function that creates a ModelConfig using
    get_default_model_config() and returns a ModelClient initialized with it.
    
    Returns:
        ModelClient: Configured model client instance
        
    Raises:
        ValueError: If required API keys are missing for the selected backend
    """
    config = get_default_model_config()
    return ModelClient(config)

