"""
Ollama LLM Backend implementation.
Wraps Ollama HTTP API with retry logic, streaming support, and error handling.
"""

import json
import logging
import time
import asyncio
import aiohttp
from typing import Dict, Any, List, Optional

from .base import LLMBackend

logger = logging.getLogger(__name__)

# Retry parameters
RETRY_COUNT = 3
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff
REQUEST_TIMEOUT = 600  # 10 minutes for text generation


class OllamaBackend(LLMBackend):
    """
    Ollama backend implementation.
    Connects to Ollama HTTP API at localhost:11434 by default.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 11434):
        """
        Args:
            host: Ollama host
            port: Ollama port
        """
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        logger.info(f"Initialized OllamaBackend: {self.base_url}")

    async def generate(
        self,
        model: str,
        prompt: str,
        **kwargs
    ) -> str:
        """
        Generate text through /api/generate endpoint.

        Args:
            model: Model name
            prompt: Input prompt
            **kwargs: temperature, top_p, max_tokens

        Returns:
            Generated text
        """
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {}
        }

        # Add parameters
        if "temperature" in kwargs:
            payload["options"]["temperature"] = kwargs["temperature"]
        if "top_p" in kwargs:
            payload["options"]["top_p"] = kwargs["top_p"]
        if "max_tokens" in kwargs:
            payload["options"]["num_predict"] = kwargs["max_tokens"]

        logger.info(f"Generate request: model={model}, prompt_len={len(prompt)}")
        start_time = time.time()

        # Retry logic
        for attempt in range(RETRY_COUNT):
            try:
                timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            text = data.get("response", "")

                            logger.debug(f"Generate RAW response: {text[:1000]}...")

                            elapsed = time.time() - start_time
                            logger.info(
                                f"Generate success: model={model}, "
                                f"output_len={len(text)}, time={elapsed:.2f}s"
                            )

                            return text
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"Generate HTTP error {response.status}: {error_text}"
                            )

                            if attempt < RETRY_COUNT - 1:
                                delay = RETRY_DELAYS[attempt]
                                logger.info(f"Retry in {delay}s (attempt {attempt + 1}/{RETRY_COUNT})")
                                await asyncio.sleep(delay)
                            else:
                                raise RuntimeError(f"Generate failed after {RETRY_COUNT} attempts")

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error(f"Network/timeout error in generate: {type(e).__name__}: {e}")

                if attempt < RETRY_COUNT - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.info(f"Retry in {delay}s (attempt {attempt + 1}/{RETRY_COUNT})")
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(f"Generate failed after {RETRY_COUNT} attempts: {e}") from e

            except Exception as e:
                logger.error(f"Unexpected error in generate: {type(e).__name__}: {e}")

                if attempt < RETRY_COUNT - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.info(f"Retry in {delay}s (attempt {attempt + 1}/{RETRY_COUNT})")
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(f"Generate failed after {RETRY_COUNT} attempts: {e}") from e

        raise RuntimeError("Generate failed")

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """
        Chat endpoint with streaming support.

        Args:
            model: Model name
            messages: Message history
            **kwargs: temperature, top_p, max_tokens

        Returns:
            Assistant response
        """
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {}
        }

        # Add parameters
        if "temperature" in kwargs:
            payload["options"]["temperature"] = kwargs["temperature"]
        if "top_p" in kwargs:
            payload["options"]["top_p"] = kwargs["top_p"]
        if "max_tokens" in kwargs:
            payload["options"]["num_predict"] = kwargs["max_tokens"]

        logger.info(f"Chat request (streaming): model={model}, messages={len(messages)}")
        logger.debug(f"Chat payload: {json.dumps(payload, ensure_ascii=False, indent=2)[:500]}...")
        start_time = time.time()

        # Retry logic
        for attempt in range(RETRY_COUNT):
            try:
                timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=300)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    logger.debug(f"Sending POST to {url}...")
                    async with session.post(url, json=payload) as response:
                        logger.debug(f"Received HTTP {response.status}")
                        if response.status == 200:
                            logger.debug("Reading streaming response...")

                            full_text = ""
                            chunk_count = 0

                            # Read streaming response line by line
                            async for line in response.content:
                                if not line:
                                    continue

                                try:
                                    chunk = json.loads(line.decode('utf-8'))

                                    # Extract content from chunk
                                    if "message" in chunk:
                                        content = chunk["message"].get("content", "")
                                        if content:
                                            full_text += content
                                            chunk_count += 1

                                    # Check for completion flag
                                    if chunk.get("done", False):
                                        logger.debug(f"Streaming complete: chunks={chunk_count}")
                                        break

                                except json.JSONDecodeError:
                                    continue

                            elapsed = time.time() - start_time

                            logger.info(f"Chat RAW response ({model}): {full_text[:2000]}")
                            logger.info(
                                f"Chat success: model={model}, "
                                f"output_len={len(full_text)}, chunks={chunk_count}, time={elapsed:.2f}s"
                            )

                            return full_text
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"Chat HTTP error {response.status}: {error_text}"
                            )

                            if attempt < RETRY_COUNT - 1:
                                delay = RETRY_DELAYS[attempt]
                                logger.info(f"Retry in {delay}s (attempt {attempt + 1}/{RETRY_COUNT})")
                                await asyncio.sleep(delay)
                            else:
                                raise RuntimeError(f"Chat failed after {RETRY_COUNT} attempts")

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error(f"Network/timeout error in chat: {type(e).__name__}: {e}")

                if attempt < RETRY_COUNT - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.info(f"Retry in {delay}s (attempt {attempt + 1}/{RETRY_COUNT})")
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(f"Chat failed after {RETRY_COUNT} attempts: {e}") from e

            except Exception as e:
                logger.error(f"Unexpected error in chat: {type(e).__name__}: {e}")

                if attempt < RETRY_COUNT - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.info(f"Retry in {delay}s (attempt {attempt + 1}/{RETRY_COUNT})")
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(f"Chat failed after {RETRY_COUNT} attempts: {e}") from e

        raise RuntimeError("Chat failed")

    async def health_check(self) -> bool:
        """
        Check if Ollama is available via /api/tags.

        Returns:
            True if healthy
        """
        url = f"{self.base_url}/api/tags"

        try:
            timeout = aiohttp.ClientTimeout(total=2)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get("models", [])
                        logger.debug(f"Ollama at {self.host}:{self.port} is healthy, models: {len(models)}")
                        return True
                    else:
                        logger.debug(f"Ollama returned status {response.status}")
                        return False
        except asyncio.TimeoutError:
            logger.debug(f"Timeout checking {self.host}:{self.port}")
            return False
        except Exception as e:
            logger.debug(f"Error checking {self.host}:{self.port}: {e}")
            return False

    async def get_models(self) -> List[str]:
        """
        Get list of available models from Ollama.

        Returns:
            List of model names
        """
        url = f"{self.base_url}/api/tags"

        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m.get("name", "") for m in data.get("models", [])]
                        logger.info(f"Found {len(models)} models in Ollama")
                        return models
                    else:
                        logger.error(f"Failed to get models, status {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error getting models: {e}")
            return []

    async def unload_model(self, model: str, keep_alive: int = 0) -> None:
        """
        Unload a model from memory.

        Args:
            model: Model name
            keep_alive: Keep-alive timeout in seconds
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": "",
            "keep_alive": keep_alive
        }

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Model {model} unloaded")
                    else:
                        logger.warning(f"Failed to unload {model}, status {response.status}")
        except Exception as e:
            logger.warning(f"Error unloading {model}: {e}")
