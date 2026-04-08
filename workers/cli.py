"""
CLI commands for managing workers.
Usage:
  python -m workers start --name writer_1 --port 9501
  python -m workers list
  python -m workers stop --name writer_1
"""

import asyncio
import argparse
import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    """Setup logging for CLI."""
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )


def cmd_start(args: argparse.Namespace) -> None:
    """Start a worker process that forwards requests to HOST backend."""
    setup_logging()

    from .worker import run_worker

    logger.info(f"Starting worker: {args.name} on {args.host}:{args.port}")
    if args.host_backend_url:
        logger.info(f"Will use HOST backend: {args.host_backend_url}")

    asyncio.run(
        run_worker(
            host=args.host,
            port=args.port,
            worker_name=args.name,
            host_backend_url=args.host_backend_url
        )
    )


def cmd_list(args: argparse.Namespace) -> None:
    """List registered workers."""
    setup_logging()

    from .coordinator import get_coordinator, init_from_config

    init_from_config()
    coordinator = get_coordinator()

    stats = coordinator.get_stats()

    print("\n=== Registered Workers ===")
    for name, info in stats["workers"].items():
        status = "✓ HEALTHY" if info["is_healthy"] else "✗ UNHEALTHY"
        print(f"\n{name} {status}")
        print(f"  Address: {info['address']}")
        print(f"  Models: {', '.join(info['models'])}")

    if not stats["workers"]:
        print("No workers registered")

    print(f"\nTotal workers: {stats['workers_count']}")
    print(f"Models supported: {len(stats['models'])}")


async def cmd_health_check(args: argparse.Namespace) -> None:
    """Check health of all workers."""
    setup_logging()

    from .coordinator import get_coordinator, init_from_config

    init_from_config()
    coordinator = get_coordinator()

    print("\n=== Worker Health Check ===\n")

    for name, worker in coordinator.workers.items():
        try:
            is_healthy = await worker.client.health_check()
            status = "✓ HEALTHY" if is_healthy else "✗ UNHEALTHY"
            print(f"{name}: {status} ({worker.host}:{worker.port})")
        except Exception as e:
            print(f"{name}: ✗ ERROR - {e}")


def cmd_config(args: argparse.Namespace) -> None:
    """Show worker configuration."""
    from config import WORKERS

    print("\n=== Worker Configuration ===\n")

    if WORKERS:
        for i, w in enumerate(WORKERS, 1):
            print(f"{i}. {w['name']}")
            print(f"   Host: {w['host']}")
            print(f"   Port: {w['port']}")
            print(f"   Models: {', '.join(w['models'])}")
    else:
        print("No workers configured in config.py")

    print()


async def cmd_discover_tailscale(args: argparse.Namespace) -> None:
    """Discover workers on Tailscale network."""
    setup_logging()

    from .tailscale import discover_tailscale_workers, get_tailscale_manager

    manager = get_tailscale_manager()

    # Check Tailscale connection
    is_connected = await manager.is_connected()
    if not is_connected:
        print("❌ Tailscale is not connected")
        print("\nTo enable Tailscale:")
        print("  sudo tailscale up")
        return

    my_ip = await manager.get_local_ip()
    print(f"\n=== Tailscale Network ===")
    print(f"Your IP: {my_ip}")

    # Get all nodes
    print(f"\n=== Available Nodes ===\n")
    nodes = await manager.get_network_nodes()

    for name, node in nodes.items():
        status = "🟢 ONLINE" if node.status == "running" else "🔴 OFFLINE"
        print(f"{status} {name:<20} {node.ip}")

    # Discover workers
    print(f"\n=== Discovering Workers (ports 9501-9510) ===\n")

    discovered = await discover_tailscale_workers(port_range=(9501, 9510))

    if discovered:
        print(f"Found {len(discovered)} workers:\n")
        for worker in discovered:
            print(f"  ✓ {worker['name']:<30} {worker['host']}:{worker['port']}")

        # Show how to add to config
        print(f"\n=== Add to config.py ===\n")
        print("WORKERS = [")
        for worker in discovered:
            print(f"    {{{")
            print(f'        "name": "{worker["name"]}", ')
            print(f'        "host": "{worker["host"]}", ')
            print(f'        "port": {worker["port"]}, ')
            print(f'        "models": ["qwen-course"]  # or ["deepseek-course"]')
            print(f"    }},")
        print("]")
    else:
        print("No workers discovered on Tailscale network")
        print("\nMake sure:")
        print("  1. Worker processes are running on other machines")
        print("  2. They're connected to the same Tailscale account")
        print("  3. They're listening on ports 9501-9510")


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="LLM Worker Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m workers start --name writer_1 --port 9501
  python -m workers list
  python -m workers health
  python -m workers config
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start a worker process")
    start_parser.add_argument("--name", required=True, help="Worker name")
    start_parser.add_argument("--host", default="127.0.0.1", help="Worker host (use 0.0.0.0 for remote access)")
    start_parser.add_argument("--port", type=int, required=True, help="Worker port")
    start_parser.add_argument("--host-backend-url", default=None,
                            help="HOST backend URL (e.g., http://100.64.0.1:11434). If not provided, uses config.HOST_BACKEND_URL")
    start_parser.set_defaults(func=cmd_start)

    # List command
    list_parser = subparsers.add_parser("list", help="List registered workers")
    list_parser.set_defaults(func=cmd_list)

    # Health command
    health_parser = subparsers.add_parser("health", help="Check worker health")
    health_parser.set_defaults(func=cmd_health_check)

    # Config command
    config_parser = subparsers.add_parser("config", help="Show worker configuration")
    config_parser.set_defaults(func=cmd_config)

    # Discover command
    discover_parser = subparsers.add_parser("discover", help="Discover workers on Tailscale network")
    discover_parser.set_defaults(func=cmd_discover_tailscale)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if asyncio.iscoroutinefunction(args.func):
            asyncio.run(args.func(args))
        else:
            args.func(args)
        return 0

    except KeyboardInterrupt:
        print("\nShutdown...")
        return 0

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
