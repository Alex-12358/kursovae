"""
Worker Coordinator - manages worker registration, health checks, and task dispatch.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from .client import WorkerRPCClient

logger = logging.getLogger(__name__)


@dataclass
class WorkerInfo:
    """Information about a registered worker."""
    name: str
    host: str
    port: int
    models: List[str]
    client: WorkerRPCClient
    is_healthy: bool = True
    last_health_check: float = 0.0

    @property
    def address(self) -> Tuple[str, int]:
        return (self.host, self.port)


class WorkerCoordinator:
    """
    Coordinates multiple worker processes.
    Tracks health, distributes tasks, handles failover.
    """

    def __init__(self):
        """Initialize the coordinator."""
        self.workers: Dict[str, WorkerInfo] = {}
        self.model_to_workers: Dict[str, List[str]] = defaultdict(list)  # model -> [worker_names]
        self.health_check_interval = 30  # seconds
        self.running = False
        logger.info("Initialized WorkerCoordinator")

    def register_worker(
        self,
        name: str,
        host: str,
        port: int,
        models: List[str]
    ) -> None:
        """
        Register a worker.

        Args:
            name: Worker name
            host: Worker host
            port: Worker port
            models: List of models this worker supports
        """
        client = WorkerRPCClient(host, port)
        worker = WorkerInfo(
            name=name,
            host=host,
            port=port,
            models=models,
            client=client
        )

        self.workers[name] = worker

        # Register models
        for model in models:
            if name not in self.model_to_workers[model]:
                self.model_to_workers[model].append(name)

        logger.info(f"Registered worker {name} ({host}:{port}) for models: {models}")

    def unregister_worker(self, name: str) -> None:
        """
        Unregister a worker.

        Args:
            name: Worker name
        """
        if name in self.workers:
            worker = self.workers.pop(name)

            # Remove from model mappings
            for model in worker.models:
                if name in self.model_to_workers[model]:
                    self.model_to_workers[model].remove(name)

            logger.info(f"Unregistered worker {name}")

    async def health_check_loop(self) -> None:
        """
        Continuous health checking loop.
        Marks workers as healthy/unhealthy and removes dead workers.
        """
        while self.running:
            await asyncio.sleep(self.health_check_interval)

            logger.debug("Running health checks...")

            for worker_name, worker in list(self.workers.items()):
                try:
                    is_healthy = await worker.client.health_check()

                    if is_healthy and not worker.is_healthy:
                        logger.info(f"Worker {worker_name} is now HEALTHY")
                        worker.is_healthy = True

                    elif not is_healthy and worker.is_healthy:
                        logger.warning(f"Worker {worker_name} is now UNHEALTHY")
                        worker.is_healthy = False

                except Exception as e:
                    if worker.is_healthy:
                        logger.warning(f"Worker {worker_name} health check failed: {e}")
                        worker.is_healthy = False

    def get_worker_for_model(self, model: str) -> Optional[WorkerInfo]:
        """
        Get a healthy worker that supports the given model.
        Prefers least-loaded worker.

        Args:
            model: Model name

        Returns:
            WorkerInfo or None if no healthy workers available
        """
        worker_names = self.model_to_workers.get(model, [])

        if not worker_names:
            logger.warning(f"No workers registered for model {model}")
            return None

        # Filter healthy workers
        healthy_workers = [
            self.workers[name] for name in worker_names
            if self.workers[name].is_healthy
        ]

        if not healthy_workers:
            logger.warning(f"No healthy workers for model {model}")
            return None

        # Return first healthy worker (could extend to load balancing)
        return healthy_workers[0]

    async def start(self) -> None:
        """Start the coordinator (health check loop)."""
        self.running = True
        logger.info("Starting WorkerCoordinator health check loop")
        await self.health_check_loop()

    def stop(self) -> None:
        """Stop the coordinator."""
        self.running = False
        logger.info("Stopping WorkerCoordinator")

    def get_stats(self) -> Dict[str, any]:
        """
        Get coordinator statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "workers_count": len(self.workers),
            "workers": {
                name: {
                    "address": f"{w.host}:{w.port}",
                    "models": w.models,
                    "is_healthy": w.is_healthy
                }
                for name, w in self.workers.items()
            },
            "models": dict(self.model_to_workers)
        }


# Global coordinator instance
_global_coordinator: Optional[WorkerCoordinator] = None


def get_coordinator() -> WorkerCoordinator:
    """
    Get or create global coordinator instance.

    Returns:
        WorkerCoordinator instance
    """
    global _global_coordinator
    if _global_coordinator is None:
        _global_coordinator = WorkerCoordinator()
    return _global_coordinator


def init_from_config() -> None:
    """
    Initialize coordinator from config.
    """
    from config import WORKERS

    coordinator = get_coordinator()

    for worker_config in WORKERS:
        coordinator.register_worker(
            name=worker_config.get("name"),
            host=worker_config.get("host", "127.0.0.1"),
            port=worker_config.get("port"),
            models=worker_config.get("models", [])
        )

    logger.info(f"Initialized coordinator with {len(WORKERS)} workers from config")
