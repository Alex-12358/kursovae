"""
Tailscale Network Configuration for Workers.
Auto-discovery and failover for Tailscale-connected machines.
"""

import asyncio
import logging
import subprocess
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class TailscaleNode:
    """Tailscale network node info."""
    name: str
    ip: str  # Tailscale IP (100.64.x.x)
    status: str  # running, stopped, etc
    is_self: bool = False


class TailscaleManager:
    """
    Manages Tailscale network connectivity for workers.
    Enables automatic discovery and failover.
    """

    def __init__(self):
        """Initialize Tailscale manager."""
        self.self_ip: Optional[str] = None
        self.nodes: Dict[str, TailscaleNode] = {}
        logger.info("Initialized TailscaleManager")

    async def is_connected(self) -> bool:
        """
        Check if machine is connected to Tailscale.

        Returns:
            True if Tailscale is running and connected
        """
        try:
            output = await self._run_command("sudo tailscale status --json")
            if output:
                return True
            return False
        except Exception as e:
            logger.debug(f"Tailscale not available: {e}")
            return False

    async def get_local_ip(self) -> Optional[str]:
        """
        Get local Tailscale IP of this machine.

        Returns:
            IP in format 100.64.x.x or None
        """
        if self.self_ip:
            return self.self_ip

        try:
            output = await self._run_command("sudo tailscale ip -4")
            if output:
                self.self_ip = output.strip()
                logger.info(f"Local Tailscale IP: {self.self_ip}")
                return self.self_ip
            return None
        except Exception as e:
            logger.warning(f"Could not get Tailscale IP: {e}")
            return None

    async def get_network_nodes(self) -> Dict[str, TailscaleNode]:
        """
        Get all nodes in Tailscale network.

        Returns:
            Dict of {node_name: TailscaleNode}
        """
        try:
            output = await self._run_command("sudo tailscale status --json")
            if not output:
                return {}

            data = json.loads(output)
            nodes = {}

            # Parse peers
            for peer_name, peer_data in data.get("Peer", {}).items():
                ips = peer_data.get("TailscaleIPs", [])
                if not ips:
                    continue

                node = TailscaleNode(
                    name=peer_name,
                    ip=ips[0],
                    status="running" if peer_data.get("Active", False) else "stopped"
                )
                nodes[peer_name] = node

            logger.info(f"Found {len(nodes)} Tailscale nodes")
            self.nodes = nodes
            return nodes

        except Exception as e:
            logger.warning(f"Could not get network nodes: {e}")
            return {}

    async def discover_workers(self, port_range: Tuple[int, int] = (9501, 9510)) -> List[Dict]:
        """
        Auto-discover available workers on Tailscale network.
        Scans common ports on all connected nodes.

        Args:
            port_range: (start_port, end_port) to scan

        Returns:
            List of discovered workers with {name, host, port}
        """
        nodes = await self.get_network_nodes()
        discovered = []

        start_port, end_port = port_range

        for node in nodes.values():
            if not node.ip or node.status != "running":
                continue

            # Scan worker ports
            for port in range(start_port, end_port + 1):
                try:
                    # Non-blocking port check with timeout
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(node.ip, port),
                        timeout=0.5
                    )
                    writer.close()
                    await writer.wait_closed()

                    worker_name = f"worker_{node.name}_{port}"
                    discovered.append({
                        "name": worker_name,
                        "host": node.ip,
                        "port": port,
                        "source": "tailscale_discovery"
                    })

                    logger.info(f"Discovered worker at {node.ip}:{port}")

                except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                    continue  # Port not listening

                except Exception as e:
                    logger.debug(f"Error scanning {node.ip}:{port}: {e}")
                    continue

        return discovered

    async def _run_command(self, cmd: str) -> Optional[str]:
        """
        Run shell command and return output.

        Args:
            cmd: Command to execute

        Returns:
            Command output or None
        """
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await proc.communicate(timeout=10)

            if proc.returncode != 0:
                logger.debug(f"Command failed: {stderr.decode()}")
                return None

            return stdout.decode().strip()

        except asyncio.TimeoutError:
            logger.warning(f"Command timeout: {cmd}")
            return None
        except Exception as e:
            logger.debug(f"Command execution failed: {e}")
            return None


# Global Tailscale manager instance
_tailscale_manager: Optional[TailscaleManager] = None


def get_tailscale_manager() -> TailscaleManager:
    """
    Get or create global Tailscale manager.

    Returns:
        TailscaleManager instance
    """
    global _tailscale_manager
    if _tailscale_manager is None:
        _tailscale_manager = TailscaleManager()
    return _tailscale_manager


async def discover_tailscale_workers(port_range: Tuple[int, int] = (9501, 9510)) -> List[Dict]:
    """
    Discover workers on Tailscale network.

    Args:
        port_range: Ports to scan

    Returns:
        List of discovered worker configs
    """
    manager = get_tailscale_manager()

    if not await manager.is_connected():
        logger.info("Tailscale not connected, skipping discovery")
        return []

    logger.info("Tailscale connected, discovering workers...")
    discovered = await manager.discover_workers(port_range)

    if discovered:
        logger.info(f"Discovered {len(discovered)} workers via Tailscale")
    else:
        logger.info("No workers discovered on Tailscale network")

    return discovered
