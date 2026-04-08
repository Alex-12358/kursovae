"""
RPC client for communicating with remote LLM workers.
Sends JSON requests over TCP and handles responses.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class WorkerRPCClient:
    """
    RPC client for communicating with LLM worker servers.
    """

    def __init__(self, host: str, port: int, timeout: float = 600):
        """
        Args:
            host: Worker host
            port: Worker port
            timeout: Request timeout in seconds
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.address = (host, port)

    async def call(self, request_type: str, **kwargs) -> Dict[str, Any]:
        """
        Send RPC request to worker.

        Args:
            request_type: "chat" or "generate" or "health"
            **kwargs: Additional request parameters

        Returns:
            Response from worker
        """
        request_id = str(uuid.uuid4())[:8]

        request = {
            "id": request_id,
            "type": request_type,
            **kwargs
        }

        logger.debug(f"Sending {request_type} request to {self.host}:{self.port}")

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout
            )

            # Send request
            request_line = json.dumps(request, ensure_ascii=False) + "\n"
            writer.write(request_line.encode('utf-8'))
            await writer.drain()

            # Receive response
            response_line = await asyncio.wait_for(
                reader.readline(),
                timeout=self.timeout
            )

            if not response_line:
                raise RuntimeError("Connection closed by worker")

            response = json.loads(response_line.decode('utf-8'))

            writer.close()
            await writer.wait_closed()

            if response.get("error"):
                raise RuntimeError(f"Worker error: {response.get('error')}")

            logger.debug(f"Received response for {request_type} request")
            return response

        except asyncio.TimeoutError:
            raise RuntimeError(f"Worker timeout {self.host}:{self.port}")
        except ConnectionRefusedError:
            raise RuntimeError(f"Worker unavailable {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"RPC call failed: {e}")
            raise

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """
        Send chat request to worker.

        Args:
            model: Model name
            messages: Message history
            **kwargs: temperature, top_p, max_tokens, etc.

        Returns:
            Assistant response
        """
        response = await self.call(
            "chat",
            model=model,
            messages=messages,
            params=kwargs
        )
        return response.get("content", "")

    async def generate(
        self,
        model: str,
        prompt: str,
        **kwargs
    ) -> str:
        """
        Send generate request to worker.

        Args:
            model: Model name
            prompt: Input prompt
            **kwargs: temperature, top_p, max_tokens, etc.

        Returns:
            Generated text
        """
        response = await self.call(
            "generate",
            model=model,
            prompt=prompt,
            params=kwargs
        )
        return response.get("content", "")

    async def health_check(self) -> bool:
        """
        Check worker health.

        Returns:
            True if worker is healthy
        """
        try:
            response = await self.call("health")
            return response.get("status") == "healthy"
        except Exception as e:
            logger.debug(f"Health check failed for {self.host}:{self.port}: {e}")
            return False

    async def get_load(self) -> float:
        """
        Get current worker load.

        Returns:
            Current load metric
        """
        try:
            response = await self.call("health")
            return response.get("current_load", 0.0)
        except Exception:
            return float('inf')  # Treat as overloaded on error
