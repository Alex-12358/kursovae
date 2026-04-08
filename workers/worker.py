"""
LLM Worker - subprocess that listens for RPC requests and executes LLM tasks.
Each worker runs a single LLM backend instance and serves requests.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
import socket

logger = logging.getLogger(__name__)


class LLMWorkerServer:
    """
    Worker server that accepts TCP connections and processes LLM requests.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9500, worker_name: str = "worker"):
        """
        Args:
            host: Server host
            port: Server port
            worker_name: Worker identifier
        """
        self.host = host
        self.port = port
        self.worker_name = worker_name

        # Initialize LLM backend
        from llm import create_backend
        self.backend = create_backend()

        self.current_load = 0.0
        self.processed_tasks = 0
        self.server = None
        logger.info(f"Initialized LLMWorkerServer: {worker_name} at {host}:{port}")

    async def start(self) -> None:
        """Start the TCP server and accept connections."""
        logger.info(f"Starting worker server on {self.host}:{self.port}...")

        # Start periodic health reporting
        asyncio.create_task(self._health_heartbeat())

        # Start TCP server
        self.server = await asyncio.start_server(
            self._handle_connection,
            self.host,
            self.port
        )

        logger.info(f"Worker server listening on {self.host}:{self.port}")
        await self.server.serve_forever()

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

    async def _handle_chat(self, request: Dict[str, Any], request_id: str) -> Dict[str, Any]:
        """
        Handle chat request.

        Args:
            request: Must contain "model" and "messages" keys
            request_id: Request ID for tracking

        Returns:
            Response with completion
        """
        model = request.get("model", "unknown")
        messages = request.get("messages", [])
        params = request.get("params", {})

        logger.info(f"Chat request {request_id} for model {model}")

        self.current_load += 1.0

        try:
            start_time = time.time()
            response = await self.backend.chat(model, messages, **params)
            elapsed = time.time() - start_time

            self.processed_tasks += 1
            logger.info(f"Chat {request_id} completed in {elapsed:.2f}s")

            return {
                "id": request_id,
                "status": "success",
                "content": response,
                "elapsed": elapsed
            }

        finally:
            self.current_load = max(0, self.current_load - 1.0)

    async def _handle_generate(self, request: Dict[str, Any], request_id: str) -> Dict[str, Any]:
        """
        Handle generate request.

        Args:
            request: Must contain "model" and "prompt" keys
            request_id: Request ID

        Returns:
            Response with completion
        """
        model = request.get("model", "unknown")
        prompt = request.get("prompt", "")
        params = request.get("params", {})

        logger.info(f"Generate request {request_id} for model {model}")

        self.current_load += 1.0

        try:
            start_time = time.time()
            response = await self.backend.generate(model, prompt, **params)
            elapsed = time.time() - start_time

            self.processed_tasks += 1
            logger.info(f"Generate {request_id} completed in {elapsed:.2f}s")

            return {
                "id": request_id,
                "status": "success",
                "content": response,
                "elapsed": elapsed
            }

        finally:
            self.current_load = max(0, self.current_load - 1.0)

    async def _handle_health(self, request_id: str) -> Dict[str, Any]:
        """
        Handle health check request.

        Args:
            request_id: Request ID

        Returns:
            Health status
        """
        is_healthy = await self.backend.health_check()

        return {
            "id": request_id,
            "status": "healthy" if is_healthy else "unhealthy",
            "worker_name": self.worker_name,
            "current_load": self.current_load,
            "processed_tasks": self.processed_tasks
        }

    async def _health_heartbeat(self) -> None:
        """
        Periodic heartbeat to report health status.
        Can be extended to report to a coordinator.
        """
        while True:
            await asyncio.sleep(5)

            is_healthy = await self.backend.health_check()
            status = "HEALTHY" if is_healthy else "UNHEALTHY"

            if self.current_load > 0:
                logger.debug(
                    f"{self.worker_name} - Status: {status}, "
                    f"Load: {self.current_load:.2f}, Tasks: {self.processed_tasks}"
                )

    def stop(self) -> None:
        """Stop the server."""
        if self.server:
            self.server.close()
            logger.info(f"Worker {self.worker_name} stopped")


async def run_worker(host: str = "127.0.0.1", port: int = 9500, worker_name: str = "worker") -> None:
    """
    Run a worker server.

    Args:
        host: Server host
        port: Server port
        worker_name: Worker identifier
    """
    import logging.config

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    server = LLMWorkerServer(host=host, port=port, worker_name=worker_name)

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
