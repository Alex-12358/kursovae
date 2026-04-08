# Distributed Worker Deployment Guide

## Quick Start

### 1. Start Worker Processes

In separate terminals, start workers:

```bash
# Writer worker
python -m workers start --name writer_1 --host 127.0.0.1 --port 9501

# Critic worker
python -m workers start --name critic_1 --host 127.0.0.1 --port 9502

# Add more workers as needed
python -m workers start --name writer_2 --host 127.0.0.1 --port 9503
```

### 2. Configure Course Generator

Edit `config.py`:

```python
WORKER_ENABLED = True
WORKER_COORDINATOR_PORT = 9500

WORKERS = [
    {"name": "writer_1", "host": "127.0.0.1", "port": 9501, "models": ["qwen-course"]},
    {"name": "critic_1", "host": "127.0.0.1", "port": 9502, "models": ["deepseek-course"]},
    {"name": "writer_2", "host": "127.0.0.1", "port": 9503, "models": ["qwen-course"]},
]

WORKER_FALLBACK_TO_LOCAL = True  # Fallback to local backend if workers fail
```

### 3. Verify Workers

```bash
python -m workers list
```

Output:
```
=== Registered Workers ===

writer_1 ✓ HEALTHY
  Address: 127.0.0.1:9501
  Models: qwen-course

critic_1 ✓ HEALTHY
  Address: 127.0.0.1:9502
  Models: deepseek-course

Total workers: 3
```

### 4. Run Course Generation

```bash
python main.py data/input/task.json
```

## Remote Workers

To run workers on different machines:

### On Remote Machine
```bash
# Ensure SSH access is available
python -m workers start --name remote_writer_1 --host 0.0.0.0 --port 9501
```

### On Main Machine
Configure in `config.py`:
```python
WORKERS = [
    {"name": "local_writer", "host": "127.0.0.1", "port": 9501, "models": ["qwen-course"]},
    {"name": "remote_writer", "host": "192.168.1.100", "port": 9501, "models": ["qwen-course"]},
    {"name": "remote_critic", "host": "192.168.1.101", "port": 9502, "models": ["deepseek-course"]},
]
```

## Architecture

### Local Setup (Single PC, Multiple Processes)

```
Main Process (Orchestrator)
    ├── Writer Worker 1 (port 9501) → LLM Backend instance 1
    ├── Writer Worker 2 (port 9503) → LLM Backend instance 2
    └── Critic Worker (port 9502) → LLM Backend instance 3
```

**Benefits:**
- Parallel chapter generation (2-3 concurrent)
- Better resource utilization
- No network overhead

### Distributed Setup (Multiple PCs)

```
Main PC
    └── Orchestrator
        ├── Remote Writer (192.168.1.100:9501)
        ├── Remote Critic (192.168.1.101:9502)
        └── Local Writer (127.0.0.1:9501)

Remote PC 1 (192.168.1.100)
    └── Writer Worker → LLM Backend (qwen-course)

Remote PC 2 (192.168.1.101)
    └── Critic Worker → LLM Backend (deepseek-course)
```

**Benefits:**
- Distribute load across multiple machines
- Use different GPUs for different models
- Scales easily to more workers

## Monitoring Workers

### CLI Commands

```bash
# List all workers
python -m workers list

# Check worker health
python -m workers health

# Show configuration
python -m workers config
```

### Logs

Watch worker logs:
```bash
tail -f logs/generator.log | grep "worker\|Worker"
```

## Troubleshooting

### Worker Connection Failed
- Check if worker is running: `python -m workers list`
- Verify port is open: `netstat -an | grep 9501`
- Check firewall settings

### Worker Timeout
- Increase timeout in `workers/client.py`: `timeout=1200`
- Check network latency for remote workers
- Reduce model complexity or context size

### Uneven Load Distribution
- Workers are assigned round-robin currently
- Monitor `current_load` in health checks
- Add more workers if needed

## Performance Tips

1. **Match Worker Capabilities to Models**
   - High-VRAM GPU for deepseek (8B model)
   - Regular GPU for qwen (4-7B model)

2. **Scale Horizontally**
   - Start with 1-2 workers per model
   - Monitor load, add more if bottleneck detected
   - Use different machines for maximum throughput

3. **Network Optimization**
   - Use wired Ethernet for remote workers
   - Keep workers on same local network
   - Minimize network round-trips

## Graceful Shutdown

```bash
# Stop a worker gracefully
python -m workers stop --name writer_1

# Or kill the process
pkill -f "python -m workers start"
```
