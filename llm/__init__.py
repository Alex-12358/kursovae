"""LLM модули - взаимодействие с различными backend'ами (Ollama, llama.cpp и т.д.)"""

import logging
from typing import Optional
from config import LLM_BACKEND_TYPE, OLLAMA_HOST, OLLAMA_PORT, LLAMACPP_INSTANCES

logger = logging.getLogger(__name__)


def create_backend(backend_type: Optional[str] = None):
    """
    Factory function to create LLM backend instance.

    Args:
        backend_type: "ollama" or "llamacpp". If None, uses config.LLM_BACKEND_TYPE

    Returns:
        Backend instance (OllamaBackend or LlamaCppBackend)
    """
    backend = backend_type or LLM_BACKEND_TYPE

    if backend == "ollama":
        from .backends import OllamaBackend
        logger.info("Creating OllamaBackend")
        return OllamaBackend(host=OLLAMA_HOST, port=OLLAMA_PORT)

    elif backend == "llamacpp":
        from .backends.llamacpp_backend import LlamaCppBackend
        logger.info("Creating LlamaCppBackend")
        return LlamaCppBackend(instances=LLAMACPP_INSTANCES)

    else:
        raise ValueError(f"Unknown backend type: {backend}")


def create_gateway(backend_type: Optional[str] = None):
    """
    Factory function to create LLM gateway/backend instance.
    Maintains backward compatibility with existing code that expects OllamaGateway.

    Args:
        backend_type: Backend type. If None, uses config value.

    Returns:
        Backend instance that supports the gateway interface
    """
    backend = create_backend(backend_type)
    # For backward compatibility, we return the backend directly
    # since all backends implement the same interface
    return backend

