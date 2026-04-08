"""
llama.cpp LLM Backend implementation.
Wraps llama.cpp HTTP server API with load balancing support.
"""

import json
import logging
import time
import asyncio
import aiohttp
from typing import Dict, Any, List, Optional, Tuple

from .base import LLMBackend
from .load_balancer import LoadBalancer

logger = logging.getLogger(__name__)

# Retry parameters
RETRY_COUNT = 3
RETRY_DELAYS = [1, 2, 4]
REQUEST_TIMEOUT = 600


class LlamaCppBackend(LLMBackend):
    """
    llama.cpp backend implementation.
    Supports load balancing across multiple llama.cpp server instances.
    """

    def __init__(self, instances: List[Tuple[str, int]]):
        """
        Args:
            instances: List of (host, port) tuples for llama.cpp servers
        """
        self.instances = instances
        self.load_balancer = LoadBalancer(instances)
        logger.info(f"Initialized LlamaCppBackend with {len(instances)} instances: {instances}")

    def _get_instance(self) -> Tuple[str, int]:
        """Get least-loaded healthy instance."""
        return self.load_balancer.get_least_loaded_instance()

    async def _request(
        self,
        endpoint: str,
        host: str,
        port: int,
        payload: Dict,
        **kwargs
    ) -> str:
        """
        Send HTTP request to llama.cpp server.

        Args:
            endpoint: API endpoint (e.g., "/completion", "/chat/completions")
            host: Server host
            port: Server port
            payload: Request payload
            **kwargs: Additional parameters

        Returns:
            Response text
        """
        url = f"http://{host}:{port}{endpoint}"
        instance = (host, port)

        logger.debug(f"Sending {endpoint} to {host}:{port}")

        # Retry logic
        for attempt in range(RETRY_COUNT):
            try:
                self.load_balancer.increment_load(instance, 1.0)
                timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            self.load_balancer.decrement_load(instance, 1.0)
                            self.load_balancer.mark_health_status(instance, True)

                            logger.debug(f"llama.cpp response received from {host}:{port}")
                            return data.get("content", "")  # Adjust based on actual API
                        else:
                            error_text = await response.text()
                            logger.error(f"llama.cpp HTTP error {response.status}: {error_text}")
                            self.load_balancer.decrement_load(instance, 1.0)

                            if attempt < RETRY_COUNT - 1:
                                delay = RETRY_DELAYS[attempt]
                                logger.info(f"Retry in {delay}s (attempt {attempt + 1}/{RETRY_COUNT})")
                                await asyncio.sleep(delay)
                            else:
                                self.load_balancer.mark_health_status(instance, False)
                                raise RuntimeError(f"llama.cpp failed after {RETRY_COUNT} attempts")

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                self.load_balancer.decrement_load(instance, 1.0)
                logger.error(f"Network/timeout error: {type(e).__name__}: {e}")
                self.load_balancer.mark_health_status(instance, False)

                if attempt < RETRY_COUNT - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.info(f"Retry in {delay}s (attempt {attempt + 1}/{RETRY_COUNT})")
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(f"llama.cpp request failed: {e}") from e

            except Exception as e:
                self.load_balancer.decrement_load(instance, 1.0)
                logger.error(f"Unexpected error: {type(e).__name__}: {e}")

                if attempt < RETRY_COUNT - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.info(f"Retry in {delay}s (attempt {attempt + 1}/{RETRY_COUNT})")
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(f"llama.cpp request failed: {e}") from e

        raise RuntimeError("llama.cpp request failed")

    async def generate(
        self,
        model: str,
        prompt: str,
        **kwargs
    ) -> str:
        """
        Generate text (mapped to /completion endpoint).

        Args:
            model: Not used for llama.cpp (single model per instance)
            prompt: Input prompt
            **kwargs: temperature, top_p, max_tokens

        Returns:
            Generated text
        """
        instance = self._get_instance()
        host, port = instance

        payload = {
            "prompt": prompt,
            "stream": False,
        }

        # Map parameters
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "max_tokens" in kwargs:
            payload["n_predict"] = kwargs["max_tokens"]

        logger.info(f"Generate from {host}:{port}, prompt_len={len(prompt)}")
        start_time = time.time()

        try:
            response = await self._request("/completion", host, port, payload)
            elapsed = time.time() - start_time
            logger.info(f"Generate success from {host}:{port}, time={elapsed:.2f}s")
            return response

        except Exception as e:
            logger.error(f"Generate failed: {e}")
            raise

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """
        Chat endpoint mapped to llama.cpp (convert messages to prompt format).

        Args:
            model: Not used
            messages: Message history
            **kwargs: temperature, top_p, max_tokens

        Returns:
            Assistant response
        """
        instance = self._get_instance()
        host, port = instance

        # Convert OpenAI format to llama.cpp format
        # This is a simple conversion; adjust based on actual llama.cpp capabilities
        prompt = self._format_messages_for_llama(messages)

        payload = {
            "prompt": prompt,
            "stream": False,
        }

        # Map parameters
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "max_tokens" in kwargs:
            payload["n_predict"] = kwargs["max_tokens"]

        logger.info(f"Chat from {host}:{port}, messages={len(messages)}")
        start_time = time.time()

        try:
            response = await self._request("/completion", host, port, payload)
            elapsed = time.time() - start_time
            logger.info(f"Chat success from {host}:{port}, time={elapsed:.2f}s")
            return response

        except Exception as e:
            logger.error(f"Chat failed: {e}")
            raise

    def _format_messages_for_llama(self, messages: List[Dict[str, str]]) -> str:
        """
        Convert OpenAI message format to llama.cpp prompt format.

        Args:
            messages: List of messages with role/content

        Returns:
            Formatted prompt string
        """
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                prompt += f"System: {content}\n\n"
            elif role == "user":
                prompt += f"User: {content}\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n"

        # Add assistant prompt for completion
        prompt += "Assistant:"
        return prompt

    async def health_check(self) -> bool:
        """
        Check if any instance is available.

        Returns:
            True if at least one instance is healthy
        """
        for host, port in self.instances:
            url = f"http://{host}:{port}/health"
            try:
                timeout = aiohttp.ClientTimeout(total=2)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            logger.debug(f"llama.cpp at {host}:{port} is healthy")
                            self.load_balancer.mark_health_status((host, port), True)
                            return True
                        else:
                            self.load_balancer.mark_health_status((host, port), False)
            except Exception as e:
                logger.debug(f"llama.cpp health check failed for {host}:{port}: {e}")
                self.load_balancer.mark_health_status((host, port), False)

        return False

    async def get_models(self) -> List[str]:
        """
        Get list of models. For llama.cpp, returns info about loaded model.

        Returns:
            List with model info
        """
        # llama.cpp doesn't have model listing, return generic info
        return ["llama-model"]

    async def unload_model(self, model: str, keep_alive: int = 0) -> None:
        """
        Unload model (not supported by llama.cpp).

        Args:
            model: Model name (ignored)
            keep_alive: Keep alive timeout (ignored)
        """
        logger.info("Model unload not supported by llama.cpp (ignored)")
