"""
Load balancer for distributing requests across multiple backend instances.
Supports least-loaded selection and health monitoring.
"""

import logging
import time
import asyncio
from typing import Dict, Tuple, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class LoadBalancer:
    """
    Load balancer for distributing requests across multiple LLM backend instances.
    Tracks instance health and load metrics.
    """

    def __init__(self, instances: List[Tuple[str, int]]):
        """
        Args:
            instances: List of (host, port) tuples for available instances
        """
        self.instances = instances  # [(host, port), ...]
        self.load_metrics: Dict[Tuple[str, int], float] = defaultdict(float)  # address -> current_load
        self.last_health_check: Dict[Tuple[str, int], float] = defaultdict(float)
        self.health_status: Dict[Tuple[str, int], bool] = {addr: True for addr in instances}
        self.health_check_interval = 30  # seconds
        logger.info(f"Initialized LoadBalancer with {len(instances)} instances: {instances}")

    def get_least_loaded_instance(self) -> Tuple[str, int]:
        """
        Get the instance with the least load.
        Prefers healthy instances.

        Returns:
            (host, port) tuple of least loaded instance
        """
        # Filter healthy instances
        healthy = [addr for addr in self.instances if self.health_status.get(addr, False)]

        if not healthy:
            # Fallback to first instance if all unhealthy
            logger.warning("No healthy instances, using first one")
            return self.instances[0]

        # Return instance with minimum load
        least_loaded = min(healthy, key=lambda addr: self.load_metrics.get(addr, 0))
        load = self.load_metrics.get(least_loaded, 0)
        logger.debug(f"Selected instance {least_loaded} with load {load:.2f}")

        return least_loaded

    def increment_load(self, instance: Tuple[str, int], delta: float = 1.0) -> None:
        """
        Increment load metric for an instance.

        Args:
            instance: (host, port) tuple
            delta: Load delta (default 1.0 per request)
        """
        current = self.load_metrics.get(instance, 0)
        self.load_metrics[instance] = current + delta
        logger.debug(f"Load for {instance}: {self.load_metrics[instance]:.2f}")

    def decrement_load(self, instance: Tuple[str, int], delta: float = 1.0) -> None:
        """
        Decrement load metric for an instance.

        Args:
            instance: (host, port) tuple
            delta: Load delta
        """
        current = self.load_metrics.get(instance, 0)
        self.load_metrics[instance] = max(0, current - delta)

    def mark_health_status(self, instance: Tuple[str, int], healthy: bool) -> None:
        """
        Mark an instance as healthy or unhealthy.

        Args:
            instance: (host, port) tuple
            healthy: True if instance is healthy
        """
        old_status = self.health_status.get(instance, True)
        self.health_status[instance] = healthy
        if old_status != healthy:
            status_str = "HEALTHY" if healthy else "UNHEALTHY"
            logger.info(f"Instance {instance} marked as {status_str}")

    def get_stats(self) -> Dict[str, any]:
        """
        Get load balancer statistics.

        Returns:
            Dictionary with instance metrics
        """
        return {
            "instances": self.instances,
            "load_metrics": dict(self.load_metrics),
            "health_status": dict(self.health_status)
        }
