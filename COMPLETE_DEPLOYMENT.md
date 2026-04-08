# Deploy Guide: Course Generator v5.5 with Tailscale Workers

## 🚀 Complete Deployment Workflow

This guide covers deploying the entire system across multiple machines using Tailscale for secure networking.

---

## Phase 1: Pre-Deployment Checklist

### On All Machines

```bash
# Check Python version
python3 --version  # Must be 3.9+

# Clone project
git clone <project-repo> kursovae
cd kursovae

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import llm; import workers; print('✓ All imports OK')"
```

### Check Tailscale Installation

```bash
which tailscale  # or where tailscale on Windows

tailscale --version  # Should show version
```

If not installed:
```bash
# Linux
curl -fsSL https://tailscale.com/install.sh | sh

# macOS
brew install tailscale

# Windows
Download from https://tailscale.com/download
```

---

## Phase 2: Tailscale Network Setup

### Step 1: Authenticate All Machines

**On Main PC:**
```bash
sudo tailscale up

# Follow browser prompt
# Note your Tailscale IP
sudo tailscale ip -4
# Example: 100.64.0.1
```

**On Worker PC 1:**
```bash
sudo tailscale up
sudo tailscale ip -4
# Example: 100.64.0.2
```

**On Worker PC 2:**
```bash
sudo tailscale up
sudo tailscale ip -4
# Example: 100.64.0.3
```

### Step 2: Verify Connectivity

**From Main PC:**
```bash
# Test connectivity to all workers
ping 100.64.0.2
ping 100.64.0.3

# Both should respond
# PING 100.64.0.2 (100.64.0.2) ...
# bytes=32 time=2ms TTL=64
```

### Step 3: View Tailscale Network

```bash
# On any machine
sudo tailscale status

# Output example:
# IP                  Hostname              Status
# 100.64.0.1          main-pc              active; running
# 100.64.0.2          worker-pc-1          active; running
# 100.64.0.3          worker-pc-2          active; running
```

---

## Phase 3: LLM Backend Setup

### Option A: Ollama (Recommended for Testing)

**On Main PC:**
```bash
# Install Ollama (if not installed)
# https://ollama.ai

# Download models
ollama pull qwen-course
ollama pull deepseek-course

# Verify models
curl http://localhost:11434/api/tags

# Update config.py
LLM_BACKEND_TYPE = "ollama"
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
```

### Option B: llama.cpp (Recommended for Production)

**On Main PC:**
```bash
# Build llama.cpp
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
make

# Download GGUF models
# Place in models/ directory:
# models/qwen-course.gguf
# models/deepseek-course.gguf

# Start server
cd ..
./llama.cpp/server \
  -m models/qwen-course.gguf \
  -ngl 999 \
  -c 2048 \
  --port 8000 \
  --host 127.0.0.1

# Test
curl http://localhost:8000/health

# Update config.py
LLM_BACKEND_TYPE = "llamacpp"
LLAMACPP_INSTANCES = [("127.0.0.1", 8000)]
```

---

## Phase 4: Configure Course Generator

**On Main PC, edit `config.py`:**

```python
# Backend selection
LLM_BACKEND_TYPE = "ollama"  # or "llamacpp"

# Chapter parallelism
MAX_CONCURRENT_CHAPTERS = 2
CHAPTER_VALIDATION_ENABLED = True

# Worker system
WORKER_ENABLED = True
WORKER_COORDINATOR_PORT = 9500

# Configure workers via Tailscale IPs
WORKERS = [
    {
        "name": "writer_remote_1",
        "host": "100.64.0.2",  # Worker PC 1 Tailscale IP
        "port": 9501,
        "models": ["qwen-course"]
    },
    {
        "name": "critic_remote",
        "host": "100.64.0.3",  # Worker PC 2 Tailscale IP
        "port": 9502,
        "models": ["deepseek-course"]
    },
]

# Optional: Worker fallback
WORKER_FALLBACK_TO_LOCAL = True
```

---

## Phase 5: Start Worker Services

### Worker PC 1 (100.64.0.2) - Writer

```bash
cd kursovae
source venv/bin/activate

# Start writer worker (listen on all interfaces)
python -m workers start \
  --name writer_remote_1 \
  --host 0.0.0.0 \
  --port 9501

# Output should show:
# INFO: Initialized LLMWorkerServer: writer_remote_1 at 0.0.0.0:9501
# INFO: Worker server listening on 0.0.0.0:9501
```

### Worker PC 2 (100.64.0.3) - Critic

```bash
cd kursovae
source venv/bin/activate

# Start critic worker
python -m workers start \
  --name critic_remote \
  --host 0.0.0.0 \
  --port 9502

# Output should show:
# INFO: Initialized LLMWorkerServer: critic_remote at 0.0.0.0:9502
# INFO: Worker server listening on 0.0.0.0:9502
```

### Keep Workers Running (Optional: Systemd)

**On Worker PC 1, create `/etc/systemd/system/course-writer.service`:**

```ini
[Unit]
Description=Course Generator Writer Worker
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/kursovae
ExecStart=/usr/bin/python3 -m workers start --name writer_remote_1 --host 0.0.0.0 --port 9501
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable course-writer.service
sudo systemctl start course-writer.service
sudo systemctl status course-writer.service
```

Repeat for Worker PC 2 with critic configuration.

---

## Phase 6: Verify Setup on Main PC

```bash
# Activate environment
source venv/bin/activate

# Method 1: CLI Discovery
python -m workers discover

# Expected output:
# === Tailscale Network ===
# Your IP: 100.64.0.1
#
# === Available Nodes ===
#
# 🟢 ONLINE  worker-pc-1          100.64.0.2
# 🟢 ONLINE  worker-pc-2          100.64.0.3
#
# === Discovering Workers ===
#
# Found 2 workers:
#   ✓ worker_worker_pc_1_9501      100.64.0.2:9501
#   ✓ worker_worker_pc_2_9502      100.64.0.3:9502

# Method 2: Check Configuration
python -m workers config

# Method 3: Health Check
python -m workers health

# Expected output:
# === Worker Health Check ===
#
# writer_remote_1: ✓ HEALTHY (100.64.0.2:9501)
# critic_remote: ✓ HEALTHY (100.64.0.3:9502)
```

---

## Phase 7: Run Course Generation

**On Main PC:**

```bash
# Test setup (validate only)
python main.py data/input/task.json --validate-only

# Expected: No errors, validation passes

# Full generation with distribution
python main.py data/input/task.json

# Monitor progress
tail -f logs/generator.log | grep -E "Chapter|Worker|validation"

# Expected output:
# INFO: Processing chapter 1...
# INFO: Chapter 1 completed
# INFO: Chat success from 100.64.0.2:9501, time=45.23s
# INFO: Chapter 1 validation: PASS (score: 0.95)
```

---

## 📊 Monitoring & Diagnostics

### Real-time Worker Health

```bash
# Continuous health monitoring
watch -n 5 'python -m workers health'

# Check specific worker
python -c "from workers.client import WorkerRPCClient; \
import asyncio; \
c = WorkerRPCClient('100.64.0.2', 9501); \
print(asyncio.run(c.health_check()))"
```

### Network Diagnostics

```bash
# Check Tailscale connectivity
sudo tailscale status

# Test port connectivity
nc -zv 100.64.0.2 9501
# Expected: Connection to 100.64.0.2 9501 port [tcp/*] succeeded!

# Check worker API
curl -v http://100.64.0.2:9501/health

# Ping worker
ping 100.64.0.2
```

### View Logs

```bash
# Main PC logs
tail -f logs/generator.log

# Worker PC 1 logs (SSH)
ssh user@worker-1
tail -f kursovae/logs/generator.log

# If using systemd
sudo journalctl -u course-writer.service -f
```

---

## 🔧 Troubleshooting

### Problem: "Worker unavailable"

```bash
# 1. Check Tailscale is connected
sudo tailscale status

# 2. Verify worker is running (on worker machine)
ps aux | grep "workers start"

# 3. Check port is listening
nc -zv 100.64.0.2 9501

# 4. Check firewall
sudo ufw allow 9501/tcp
sudo ufw allow 9502/tcp

# 5. Restart worker
pkill -f "workers start"
# Then restart it
```

### Problem: "Timeout connecting to worker"

```bash
# 1. Increase timeout in config.py (not shown, but can modify workers/client.py)
# Modify: self.timeout = 1200  # 20 minutes

# 2. Check network latency
ping 100.64.0.2

# 3. Check LLM backend on worker machine
# Verify Ollama/llama.cpp is running and accessible

# 4. Reduce concurrent chapters
MAX_CONCURRENT_CHAPTERS = 1
```

### Problem: "Out of Memory (OOM)"

```bash
# 1. On main PC, reduce context
# In llama.cpp startup:
-c 1024  # instead of -c 2048

# 2. Reduce concurrent chapters
MAX_CONCURRENT_CHAPTERS = 1

# 3. Check memory usage
watch -n 1 free -h

# 4. Monitor GPU (if using)
nvidia-smi -l 1  # NVIDIA
rocm-smi -l 1    # AMD
```

### Problem: "Chapter validation fails"

```bash
# 1. Check validation is enabled
CHAPTER_VALIDATION_ENABLED = True

# 2. Review logs for validation issues
grep "validation" logs/generator.log | head -20

# 3. Check LLM is using correct markers
# Writer should produce: [FORMULA]...[/FORMULA]
# Ensure prompt templates include these markers

# 4. Disable validation temporarily (for debugging)
CHAPTER_VALIDATION_ENABLED = False
```

---

## ⚡ Performance Optimization

### Single PC (Sequential)
```
Time: 3-4 hours for 14 chapters
```

### Single PC (Parallel, 2 concurrent)
```
Time: 1.5-2 hours
Speedup: 2×
config:
  MAX_CONCURRENT_CHAPTERS = 2
```

### Multi-PC with Tailscale (2 workers)
```
Time: 1-1.5 hours
Speedup: 2-3×
config:
  WORKER_ENABLED = True
  WORKERS = [worker1, worker2]
```

### Multi-PC with llama.cpp + Tailscale
```
Time: 45 minutes - 1 hour
Speedup: 3-4×
config:
  LLM_BACKEND_TYPE = "llamacpp"
  WORKER_ENABLED = True
  MAX_CONCURRENT_CHAPTERS = 2
```

### Tuning Tips

1. **GPU Offloading**: `-ngl 999` (move all to GPU)
2. **Threads**: `-t 16` (adjust to CPU core count)
3. **Context**: `-c 1024` (reduce if OOM)
4. **Batch Size**: `-b 512` (increase for speed)

---

## 🔐 Security Best Practices

### Tailscale ACL (Access Control List)

Edit at https://login.tailscale.com/org/acls

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["group:main"],
      "dst": ["group:workers:9501,9502"]
    }
  ],
  "groups": {
    "main": ["user@example.com"],
    "workers": ["worker1@example.com", "worker2@example.com"]
  }
}
```

### Firewall Configuration

```bash
# Allow only Tailscale interfaces
sudo ufw default deny incoming
sudo ufw allow 9501/tcp
sudo ufw allow 9502/tcp
sudo ufw enable
```

### Network Isolation

- Use Tailscale VPN only for connections
- Don't expose ports publicly
- Keep Tailscale account secure
- Revoke device access when not needed

---

## ✅ Final Verification Checklist

- [ ] Tailscale connected on all machines (`sudo tailscale status`)
- [ ] LLM backend running (`curl http://localhost:8000/health`)
- [ ] Workers starting without errors (`python -m workers list`)
- [ ] Network connectivity verified (`ping 100.64.0.2`)
- [ ] Config file updated with correct Tailscale IPs
- [ ] Test run completed successfully
- [ ] Logs show chapter parallelism working
- [ ] Validation catching issues correctly

---

## 📚 Additional Resources

- [ARCHITECTURE.md](ARCHITECTURE.md) — System design
- [TAILSCALE_WORKERS.md](TAILSCALE_WORKERS.md) — Detailed Tailscale setup
- [SETUP_GUIDE.md](SETUP_GUIDE.md) — Complete setup walkthrough
- [LLAMACPP_SETUP.md](LLAMACPP_SETUP.md) — llama.cpp tuning guide
- [WORKER_DEPLOYMENT.md](WORKER_DEPLOYMENT.md) — Worker system details

---

## 🎯 Quick Commands Reference

```bash
# Setup
sudo tailscale up
python -m workers discover
python -m workers config
python -m workers health

# Start worker
python -m workers start --name w1 --host 0.0.0.0 --port 9501

# Health check
python -m workers health

# Generate course
python main.py task.json

# Monitor
tail -f logs/generator.log
python -m workers health  # in another terminal

# Cleanup
pkill -f "workers start"
sudo tailscale logout
```

---

**Status: Complete ✅**

All phases completed:
- ✅ Phase 1: Backend Abstraction
- ✅ Phase 2: llama.cpp Support
- ✅ Phase 3: Worker Distribution
- ✅ Phase 4: Chapter Parallelism
- ✅ Phase 5: Documentation
- ✅ Phase 6: Tailscale Integration

System ready for production deployment.
