"""
LLM Worker - subprocess that listens for RPC requests and forwards them to HOST backend.
Workers participate in inference by routing requests to the central HOST backend.
This enables Model Consolidation: models are stored only on HOST.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
import socket
import aiohttp
import os

logger = logging.getLogger(__name__)


class LLMWorkerServer:
    """
    Worker server that accepts TCP connections and forwards requests to HOST backend.
    This worker does NOT have a local backend - it routes to the central HOST backend.
    Model Consolidation: models are stored only on HOST.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9500, worker_name: str = "worker",
                 host_backend_url: Optional[str] = None):
        """
        Args:
            host: Server host (0.0.0.0 for remote access)
            port: Server port
            worker_name: Worker identifier
            host_backend_url: URL to HOST backend (e.g., http://100.64.0.1:11434 or :8000)
        """
        self.host = host
        self.port = port
        self.worker_name = worker_name

        # Get HOST backend URL from parameter or config
        if host_backend_url is None:
            from config import HOST_BACKEND_URL
            self.host_backend_url = HOST_BACKEND_URL
        else:
            self.host_backend_url = host_backend_url

        self.current_load = 0.0
        self.processed_tasks = 0
        self.server = None
        self.http_session: Optional[aiohttp.ClientSession] = None

        logger.info(f"Initialized LLMWorkerServer: {worker_name} at {host}:{port}")
        logger.info(f"Will route requests to HOST backend: {self.host_backend_url}")

    async def start(self) -> None:
        """Start the TCP server and accept connections."""
        logger.info(f"Starting worker server on {self.host}:{self.port}...")

        # Create HTTP session for HOST backend calls
        self.http_session = aiohttp.ClientSession()

        # Start periodic health reporting
        asyncio.create_task(self._health_heartbeat())

        # Start TCP server
        self.server = await asyncio.start_server(
            self._handle_connection,
            self.host,
            self.port
        )

        logger.info(f"Worker server listening on {self.host}:{self.port}")
        try:
            await self.server.serve_forever()
        finally:
            if self.http_session:
                await self.http_session.close()

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle incoming TCP connection."""
        client_addr = writer.get_extra_info('peername')
        logger.debug(f"New connection from {client_addr}")

        try:
            while True:
                # Read request (JSON lines protocol)
                line = await reader.readline()
                if not line:
                    # Connection closed
                    logger.debug(f"Connection closed by {client_addr}")
                    break

                try:
                    request = json.loads(line.decode('utf-8'))
                    logger.debug(f"Received request from {client_addr}: {request.get('type', 'unknown')}")

                    # Process request
                    response = await self._process_request(request)

                    # Send response
                    response_line = json.dumps(response, ensure_ascii=False) + "\n"
                    writer.write(response_line.encode('utf-8'))
                    await writer.drain()

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from {client_addr}: {e}")
                    error_response = {"error": f"Invalid JSON: {e}"}
                    writer.write((json.dumps(error_response) + "\n").encode('utf-8'))
                    await writer.drain()

        except Exception as e:
            logger.error(f"Error handling connection from {client_addr}: {e}")

        finally:
            writer.close()
            await writer.wait_closed()
            logger.debug(f"Connection closed: {client_addr}")

    async def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming RPC request.

        Args:
            request: {"type": "chat|generate|health", "model": "...", "content": {}}

        Returns:
            Response dict
        """
        request_type = request.get("type", "unknown")
        request_id = request.get("id", "unknown")

        try:
            if request_type == "chat":
                return await self._handle_chat(request, request_id)

            elif request_type == "generate":
                return await self._handle_generate(request, request_id)

            elif request_type == "health":
                return await self._handle_health(request_id)

            elif request_type == "stop":
                logger.info("Stop command received")
                return {"status": "stopping", "id": request_id}

            else:
                return {"error": f"Unknown request type: {request_type}", "id": request_id}

        except Exception as e:
            logger.error(f"Error processing request {request_id}: {e}")
            return {"error": str(e), "id": request_id}

    async def _call_host_backend(self, method: str, **kwargs) -> Dict[str, Any]:
        """
        Call HOST backend via HTTP.

        Args:
            method: "chat" or "generate"
            **kwargs: Backend method parameters (model, prompt/messages, params, etc.)

        Returns:
            Response from HOST backend

        Raises:
            Exception if HOST backend is unreachable
        """
        if not self.http_session:
            raise RuntimeError("HTTP session not initialized")

        # Determine which endpoint to use
        if method == "chat":
            endpoint = f"{self.host_backend_url}/api/chat"
        elif method == "generate":
            endpoint = f"{self.host_backend_url}/api/generate"
        else:
            raise ValueError(f"Unknown method: {method}")

        logger.debug(f"Calling HOST backend: {endpoint}")

        try:
            async with self.http_session.post(endpoint, json=kwargs, timeout=aiohttp.ClientTimeout(total=600)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"HOST backend returned {resp.status}: {error_text}")

                result = await resp.json()
                return result

        except asyncio.TimeoutError:
            logger.error(f"Timeout calling HOST backend at {endpoint}")
            raise
        except aiohttp.ClientError as e:
            logger.error(f"Error calling HOST backend: {e}")
            raise RuntimeError(f"Cannot reach HOST backend at {self.host_backend_url}: {e}")

    async def _handle_chat(self, request: Dict[str, Any], request_id: str) -> Dict[str, Any]:
        """
        Handle chat request by forwarding to HOST backend.

        Args:
            request: Must contain "model" and "messages" keys
            request_id: Request ID for tracking

        Returns:
            Response with completion from HOST backend
        """
        model = request.get("model", "unknown")
        messages = request.get("messages", [])
        params = request.get("params", {})

        logger.info(f"Chat request {request_id} for model {model} → forwarding to HOST")

        self.current_load += 1.0

        try:
            start_time = time.time()

            # Call HOST backend
            response = await self._call_host_backend(
                "chat",
                model=model,
                messages=messages,
                **params
            )

            elapsed = time.time() - start_time
            self.processed_tasks += 1

            logger.info(f"Chat {request_id} completed in {elapsed:.2f}s")

            return {
                "id": request_id,
                "status": "success",
                "content": response,
                "elapsed": elapsed
            }

        except Exception as e:
            logger.error(f"Chat {request_id} failed: {e}")
            return {
                "id": request_id,
                "status": "error",
                "error": str(e)
            }

        finally:
            self.current_load = max(0, self.current_load - 1.0)

    async def _handle_generate(self, request: Dict[str, Any], request_id: str) -> Dict[str, Any]:
        """
        Handle generate request by forwarding to HOST backend.

        Args:
            request: Must contain "model" and "prompt" keys
            request_id: Request ID

        Returns:
            Response with completion from HOST backend
        """
        model = request.get("model", "unknown")
        prompt = request.get("prompt", "")
        params = request.get("params", {})

        logger.info(f"Generate request {request_id} for model {model} → forwarding to HOST")

        self.current_load += 1.0

        try:
            start_time = time.time()

            # Call HOST backend
            response = await self._call_host_backend(
                "generate",
                model=model,
                prompt=prompt,
                **params
            )

            elapsed = time.time() - start_time
            self.processed_tasks += 1

            logger.info(f"Generate {request_id} completed in {elapsed:.2f}s")

            return {
                "id": request_id,
                "status": "success",
                "content": response,
                "elapsed": elapsed
            }

        except Exception as e:
            logger.error(f"Generate {request_id} failed: {e}")
            return {
                "id": request_id,
                "status": "error",
                "error": str(e)
            }

        finally:
            self.current_load = max(0, self.current_load - 1.0)

    async def _handle_health(self, request_id: str) -> Dict[str, Any]:
        """
        Handle health check request.
        Checks if HOST backend is reachable.

        Args:
            request_id: Request ID

        Returns:
            Health status
        """
        is_healthy = await self._check_host_backend_health()

        return {
            "id": request_id,
            "status": "healthy" if is_healthy else "unhealthy",
            "worker_name": self.worker_name,
            "current_load": self.current_load,
            "processed_tasks": self.processed_tasks,
            "host_backend_url": self.host_backend_url
        }

    async def _check_host_backend_health(self) -> bool:
        """
        Check if HOST backend is reachable.

        Returns:
            True if reachable, False otherwise
        """
        if not self.http_session:
            return False

        try:
            # Try to call /health or GET root
            health_url = f"{self.host_backend_url}/health"
            async with self.http_session.get(health_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200

        except Exception as e:
            logger.warning(f"HOST backend health check failed: {e}")
            return False

    async def _health_heartbeat(self) -> None:
        """
        Periodic heartbeat to monitor HOST backend health.
        """
        while True:
            await asyncio.sleep(5)

            is_healthy = await self._check_host_backend_health()
            status = "HEALTHY" if is_healthy else "UNHEALTHY"

            if self.current_load > 0 or not is_healthy:
                logger.debug(
                    f"{self.worker_name} - Status: {status}, "
                    f"Load: {self.current_load:.2f}, Tasks: {self.processed_tasks}"
                )

    def stop(self) -> None:
        """Stop the server."""
        if self.server:
            self.server.close()
            logger.info(f"Worker {self.worker_name} stopped")


async def run_worker(host: str = "127.0.0.1", port: int = 9500, worker_name: str = "worker",
                     host_backend_url: Optional[str] = None) -> None:
    """
    Run a worker server that forwards requests to HOST backend.

    Args:
        host: Server host (0.0.0.0 for remote access)
        port: Server port
        worker_name: Worker identifier
        host_backend_url: URL to HOST backend (e.g., http://100.64.0.1:11434)
    """
    import logging.config

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    server = LLMWorkerServer(host=host, port=port, worker_name=worker_name,
                             host_backend_url=host_backend_url)

    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
        server.stop()


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="LLM Worker Server")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=9500, help="Server port")
    parser.add_argument("--name", default="worker", help="Worker name")

    args = parser.parse_args()

    asyncio.run(run_worker(host=args.host, port=args.port, worker_name=args.name))
