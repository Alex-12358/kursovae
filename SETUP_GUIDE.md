# Course Generator v5 — Complete Setup & Deployment Guide

## Table of Contents
1. **Installation & Configuration**
2. **Backend Selection** (Ollama vs llama.cpp)
3. **Worker System Deployment**
4. **Distributed Setup with Tailscale**
5. **Troubleshooting**
6. **Performance Tuning**

---

## Part 1: Installation & Configuration

### Prerequisites
```bash
python 3.9+
pip install -r requirements.txt
```

### Basic Configuration

Edit `config.py`:

```python
# Backend choice
LLM_BACKEND_TYPE = "ollama"  # or "llamacpp"

# Chapter parallelism (2-3 for safety)
MAX_CONCURRENT_CHAPTERS = 2

# Enable validation
CHAPTER_VALIDATION_ENABLED = True

# Worker system (optional)
WORKER_ENABLED = False  # Set to True for distributed execution
```

### Quick Test
```bash
python main.py --validate-only data/input/task.json
```

---

## Part 2: Backend Selection

### Option A: Ollama (Simplest)

**Pros:** Easy setup, works out of box
**Cons:** Slower than llama.cpp

```bash
# Install Ollama from https://ollama.ai
# Pull models
ollama pull qwen-course
ollama pull deepseek-course

# Verify
curl http://localhost:11434/api/tags

# In config.py
LLM_BACKEND_TYPE = "ollama"
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
```

### Option B: llama.cpp (Recommended)

**Pros:** 20-30% faster, better resource control
**Cons:** More setup required

```bash
# 1. Build llama.cpp
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp && make

# 2. Download GGUF models
# Place in ./models/
models/
├── qwen-course.gguf
└── deepseek-course.gguf

# 3. Start server
./server -m models/qwen-course.gguf \
  -ngl 999 \
  -c 2048 \
  --port 8000 \
  --host 0.0.0.0

# 4. Verify
curl http://localhost:8000/health

# 5. In config.py
LLM_BACKEND_TYPE = "llamacpp"
LLAMACPP_INSTANCES = [("127.0.0.1", 8000)]
```

**Performance Tuning:**
```bash
# GPU acceleration
-ngl 999        # Offload all layers to GPU

# CPU optimization
-t 8            # Number of threads (8-32 depending on CPU)
-b 512          # Batch size

# Context window
-c 2048         # Context (reduce to 1024 if OOM)

# Multi-instance (load balancing)
./server -m models/qwen-course.gguf -ngl 999 --port 8000 &
./server -m models/deepseek-course.gguf -ngl 999 --port 8001 &
```

---

## Part 3: Worker System Deployment

### Local Setup (Single PC)

**Benefit:** 2-3× speedup with parallel chapter generation

#### Step 1: Configure Workers

Edit `config.py`:
```python
WORKER_ENABLED = True
WORKER_COORDINATOR_PORT = 9500

WORKERS = [
    {"name": "writer_1", "host": "127.0.0.1", "port": 9501, "models": ["qwen-course"]},
    {"name": "critic_1", "host": "127.0.0.1", "port": 9502, "models": ["deepseek-course"]},
    # Add more as needed
]

MAX_CONCURRENT_CHAPTERS = 2  # Parallel chapter limit
```

#### Step 2: Start Workers

Terminal 1:
```bash
python -m workers start --name writer_1 --host 127.0.0.1 --port 9501
```

Terminal 2:
```bash
python -m workers start --name critic_1 --host 127.0.0.1 --port 9502
```

#### Step 3: Verify

```bash
python -m workers list

# Output:
# === Registered Workers ===
# writer_1 ✓ HEALTHY
#   Address: 127.0.0.1:9501
#   Models: qwen-course
```

#### Step 4: Run Generation

```bash
python main.py data/input/task.json
```

### Monitor Workers

```bash
# Real-time health
python -m workers health

# Check configuration
python -m workers config

# View logs
tail -f logs/generator.log | grep -i worker
```

---

## Part 4: Distributed Setup with Tailscale

### Why Tailscale?
- **Secure**: End-to-end encryption
- **Easy**: No port forwarding, no firewall config
- **Private**: VPN between your machines
- **Free tier**: 3 users, 100 devices

### Setup Steps

#### 1. Install Tailscale

On all machines (main PC + worker PCs):
```bash
# Linux
curl -fsSL https://tailscale.com/install.sh | sh

# macOS
brew install tailscale

# Windows
Download from https://tailscale.com/download
```

#### 2. Connect to Tailscale

On each machine:
```bash
sudo tailscale up

# Follow browser login
# Get your Tailscale IP
ip=$(sudo tailscale ip -4)
echo "Your IP: $ip"
```

#### 3. Configure Course Generator

Get Tailscale IPs of all machines:
```bash
# On each machine
sudo tailscale ip -4
```

Edit `config.py`:
```python
# Example: Main PC = 100.64.0.1, Worker PC 1 = 100.64.0.2, Worker PC 2 = 100.64.0.3

WORKER_ENABLED = True

WORKERS = [
    # Local worker
    {"name": "writer_local", "host": "127.0.0.1", "port": 9501, "models": ["qwen-course"]},

    # Remote workers via Tailscale
    {"name": "writer_remote_1", "host": "100.64.0.2", "port": 9501, "models": ["qwen-course"]},
    {"name": "critic_remote", "host": "100.64.0.3", "port": 9502, "models": ["deepseek-course"]},
]
```

#### 4. Start Remote Workers

On worker PC 1 (100.64.0.2):
```bash
python -m workers start --name writer_remote_1 --host 0.0.0.0 --port 9501
```

On worker PC 2 (100.64.0.3):
```bash
python -m workers start --name critic_remote --host 0.0.0.0 --port 9502
```

On main PC (100.64.0.1):
```bash
# Verify connection
python -m workers health

# Should show all workers as HEALTHY
# Then run generation
python main.py data/input/task.json
```

### Troubleshooting Tailscale

```bash
# Check Tailscale status
sudo tailscale status

# Check connectivity
ping 100.64.0.2  # Should work

# Check ports
nc -zv 100.64.0.2 9501  # Should connect

# View Tailscale logs
sudo journalctl -u tailscaled -f
```

---

## Part 5: Complete Deployment Example

### Scenario: 3-Machine Setup

**Main PC (Linux, GPU)**: Generate courses, run Ollama/llama.cpp
**Worker PC 1 (Linux, GPU)**: Run writer worker
**Worker PC 2 (MacBook, CPU)**: Run critic worker

### Installation on All Machines

```bash
# Clone project
git clone <project-repo>
cd kursovae

# Install dependencies
pip install -r requirements.txt

# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
```

### Configure & Start

**Main PC:**
```python
# config.py
LLM_BACKEND_TYPE = "llamacpp"
LLAMACPP_INSTANCES = [("127.0.0.1", 8000)]

WORKER_ENABLED = True
WORKERS = [
    {"name": "writer_1", "host": "100.64.0.2", "port": 9501, "models": ["qwen-course"]},
    {"name": "critic_1", "host": "100.64.0.3", "port": 9502, "models": ["deepseek-course"]},
]
```

```bash
# Start Tailscale
sudo tailscale up

# Start local llama.cpp
./llama.cpp/server -m models/qwen-course.gguf -ngl 999 --port 8000

# Run generation
python main.py data/input/task.json
```

**Worker PC 1 (100.64.0.2):**
```bash
# Start Tailscale
sudo tailscale up

# Start worker
python -m workers start --name writer_1 --host 0.0.0.0 --port 9501
```

**Worker PC 2 (100.64.0.3):**
```bash
# Start Tailscale
sudo tailscale up

# Start worker
python -m workers start --name critic_1 --host 0.0.0.0 --port 9502
```

### Monitor from Main PC

```bash
# Check all workers
python -m workers list

# Should output:
# === Registered Workers ===
#
# writer_1 ✓ HEALTHY
#   Address: 100.64.0.2:9501
#   Models: qwen-course
#
# critic_1 ✓ HEALTHY
#   Address: 100.64.0.3:9502
#   Models: deepseek-course
```

---

## Part 6: Troubleshooting & Performance

### Common Issues

#### Backend not responding
```bash
# Check Ollama
curl -v http://localhost:11434/api/tags

# Check llama.cpp
curl -v http://localhost:8000/health

# Check Tailscale connection
sudo tailscale status
```

#### Worker timeout
- **Cause**: Network latency, slow LLM generation
- **Fix**: Increase timeout in `workers/client.py` or add more workers

#### Out of memory (OOM)
- **Cause**: Model too large or context too big
- **Fix**:
  ```bash
  # Reduce context
  ./server -c 1024 -m models/...

  # Use smaller model
  # Decrease concurrent chapters: MAX_CONCURRENT_CHAPTERS = 1
  ```

#### Uneven load distribution
- **Cause**: Worker selection is round-robin
- **Fix**: Manually balance by adding dedicated workers per model

### Performance Targets

| Component | Typical Time |
|-----------|--------------|
| 1 chapter generation | 5-15 min |
| 1 chapter validation | <1 min |
| 14 chapters sequential | 3+ hours |
| 14 chapters parallel (2 concurrent) | 1.5-2 hours |
| With llama.cpp | -20-30% |
| With 3 workers distributed | 2-3× faster |

### Optimization Checklist

- [ ] Use llama.cpp for 20-30% speedup
- [ ] Enable chapter parallelism (MAX_CONCURRENT_CHAPTERS = 2)
- [ ] Set up Tailscale for distributed workers
- [ ] Start 2-3 worker processes
- [ ] Monitor with `python -m workers health`
- [ ] Tune GPU offloading (-ngl 999)
- [ ] Adjust context window (-c 2048 or lower)
- [ ] Scale to 3+ machines if needed

---

## Quick Reference Commands

```bash
# Worker management
python -m workers start --name w1 --port 9501
python -m workers list
python -m workers health
python -m workers config

# Tailscale
sudo tailscale up
sudo tailscale status
sudo tailscale ip -4

# Course generation
python main.py task.json                    # Basic
python main.py task.json --resume ID        # Resume
python main.py --list-sessions              # List sessions
python main.py task.json --validate-only    # Validate only

# llama.cpp server
./server -m models/qwen.gguf -ngl 999 -c 2048 --port 8000

# Monitoring
tail -f logs/generator.log
python -m workers health
```

---

## Next: See Docs

- `ARCHITECTURE.md` — System design details
- `LLAMACPP_SETUP.md` — llama.cpp tuning guide
- `TAILSCALE_WORKERS.md` — Detailed Tailscale setup (next file)
