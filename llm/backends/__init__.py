"""
LLM Backends abstraction layer.
Supports multiple backends: Ollama, llama.cpp, etc.
"""

from .base import LLMBackend
from .ollama_backend import OllamaBackend

__all__ = ["LLMBackend", "OllamaBackend"]
