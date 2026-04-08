"""
Abstract LLM Backend interface.
All backends must implement this interface.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class LLMBackend(ABC):
    """
    Abstract base class for LLM backends.
    Defines the interface that all backends (Ollama, llama.cpp, etc.) must implement.
    """

    @abstractmethod
    async def generate(
        self,
        model: str,
        prompt: str,
        **kwargs
    ) -> str:
        """
        Generate text from a prompt.

        Args:
            model: Model name
            prompt: Input prompt
            **kwargs: Additional parameters (temperature, top_p, max_tokens, etc.)

        Returns:
            Generated text
        """
        pass

    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """
        Chat endpoint - sends message history, gets response.

        Args:
            model: Model name
            messages: List of dicts with "role" and "content" keys
            **kwargs: Additional parameters (temperature, top_p, max_tokens, etc.)

        Returns:
            Assistant response text
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the backend is available and responsive.

        Returns:
            True if healthy, False otherwise
        """
        pass

    @abstractmethod
    async def get_models(self) -> List[str]:
        """
        Get list of available models.

        Returns:
            List of model names
        """
        pass

    @abstractmethod
    async def unload_model(self, model: str, keep_alive: int = 0) -> None:
        """
        Unload a model from memory (optional, may not be supported by all backends).

        Args:
            model: Model name to unload
            keep_alive: Keep-alive timeout in seconds
        """
        pass
