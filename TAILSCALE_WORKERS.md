# Tailscale Integration for Course Generator Workers

## Overview

Tailscale enables secure, easy connection of worker processes across multiple machines without:
- Port forwarding
- Firewall configuration
- VPN setup complexity
- Public IP exposure

## What is Tailscale?

**Tailscale** is a WireGuard-based VPN that creates a private mesh network. Each machine gets a private IP in the `100.64.0.0/10` range.

**Key Benefits:**
- ✅ End-to-end encrypted
- ✅ No configuration needed (uses WireGuard under the hood)
- ✅ Free tier: 3 users, 100 devices
- ✅ Works across NAT, firewalls, cloud providers
- ✅ Instant connectivity (no setup hassles)

---

## Installation Guide

### Step 1: Install Tailscale on All Machines

#### Linux (Ubuntu/Debian)
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo systemctl enable tailscaled
sudo systemctl start tailscaled
```

#### Linux (Fedora/RHEL)
```bash
sudo dnf install tailscale
sudo systemctl enable tailscaled
sudo systemctl start tailscaled
```

#### macOS
```bash
# Using Homebrew
brew install tailscale
brew services start tailscale

# Or download from https://tailscale.com/download
```

#### Windows
Download installer: https://tailscale.com/download/windows

#### Docker
```dockerfile
FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y curl && \
    curl -fsSL https://tailscale.com/install.sh | sh

COPY . /app
WORKDIR /app

CMD ["tailscaled", "--tun=userspace"]
```

### Step 2: Authenticate

On each machine:

```bash
# Connect to Tailscale
sudo tailscale up

# Browser will open, complete authentication
# You'll see: Connected

# Get your Tailscale IP
sudo tailscale ip -4
# Output example: 100.64.0.1

# Get full status
sudo tailscale status
```

### Step 3: Verify Connectivity

```bash
# From main PC, ping worker PC
ping 100.64.0.2

# Should respond successfully
```

---

## Course Generator Configuration

### Architecture Diagram

```
┌─────────────────────────────────────────┐
│  Tailscale VPN (100.64.0.0/10)          │
├─────────────────────────────────────────┤
│                                         │
│  Main PC          Worker PC 1  Worker PC 2
│  100.64.0.1       100.64.0.2   100.64.0.3
│  ┌─────────────┐  ┌────────┐   ┌────────┐
│  │ Orchestrator├──→ Writer │   │ Critic │
│  │    DAG      │  │ Worker │   │ Worker │
│  │ (Master)    │  │ (port  │   │ (port  │
│  │             │  │  9501) │   │  9502) │
│  └─────────────┘  └────────┘   └────────┘
│
└─────────────────────────────────────────┘
```

### Configuration Example

**On Main PC (100.64.0.1):**

```python
# config.py

# LLM Backend on main PC
LLM_BACKEND_TYPE = "llamacpp"
LLAMACPP_INSTANCES = [("127.0.0.1", 8000)]

# Enable worker system
WORKER_ENABLED = True
WORKER_COORDINATOR_PORT = 9500

# Configure remote workers via Tailscale
WORKERS = [
    # Local writer (for fast processing)
    {
        "name": "writer_local",
        "host": "127.0.0.1",
        "port": 9501,
        "models": ["qwen-course"]
    },

    # Remote writer via Tailscale (100.64.0.2 = Worker PC 1)
    {
        "name": "writer_remote",
        "host": "100.64.0.2",
        "port": 9501,
        "models": ["qwen-course"]
    },

    # Remote critic via Tailscale (100.64.0.3 = Worker PC 2)
    {
        "name": "critic_remote",
        "host": "100.64.0.3",
        "port": 9502,
        "models": ["deepseek-course"]
    },
]

# Chapter parallelism
MAX_CONCURRENT_CHAPTERS = 2
CHAPTER_VALIDATION_ENABLED = True
```

---

## Step-by-Step Deployment

### Phase 1: Main PC Setup

```bash
# 1. Start Tailscale
sudo tailscale up

# Get your IP (note it down)
MAIN_IP=$(sudo tailscale ip -4)
echo "Main PC Tailscale IP: $MAIN_IP"

# 2. Start local LLM backend
cd llama.cpp
./server -m ../models/qwen-course.gguf \
  -ngl 999 \
  -c 2048 \
  --port 8000 \
  --host 127.0.0.1 &

# 3. Update config.py with remote worker IPs
# (You'll get these after setting up worker PCs)

# 4. Test local setup first
python main.py data/input/task.json --validate-only
```

### Phase 2: Worker PC 1 Setup

```bash
# 1. Start Tailscale
sudo tailscale up

# Get your IP
WORKER1_IP=$(sudo tailscale ip -4)
echo "Worker PC 1 IP: $WORKER1_IP"

# 2. Clone project
cd /path/to/kursovae
pip install -r requirements.txt

# 3. Start Writer worker
# Listen on 0.0.0.0 so main PC can connect via Tailscale IP
python -m workers start \
  --name writer_remote \
  --host 0.0.0.0 \
  --port 9501

# Worker will output:
# INFO: Worker server listening on 0.0.0.0:9501
```

### Phase 3: Worker PC 2 Setup

```bash
# 1. Start Tailscale
sudo tailscale up

# Get your IP
WORKER2_IP=$(sudo tailscale ip -4)
echo "Worker PC 2 IP: $WORKER2_IP"

# 2. Clone project
cd /path/to/kursovae
pip install -r requirements.txt

# 3. Start Critic worker
python -m workers start \
  --name critic_remote \
  --host 0.0.0.0 \
  --port 9502
```

### Phase 4: Main PC Configuration & Execution

```bash
# 1. Update config.py with actual Tailscale IPs
# Example:
# WORKERS = [
#     {"name": "writer_remote", "host": "100.64.0.2", "port": 9501, ...},
#     {"name": "critic_remote", "host": "100.64.0.3", "port": 9502, ...},
# ]

# 2. Verify all workers are healthy
python -m workers health

# Expected output:
# === Worker Health Check ===
#
# writer_remote: ✓ HEALTHY (100.64.0.2:9501)
# critic_remote: ✓ HEALTHY (100.64.0.3:9502)

# 3. Run course generation
python main.py data/input/task.json

# Watch progress
tail -f logs/generator.log
```

---

## Systemd Services (Optional)

### Auto-start Workers on Boot

**On Worker PC 1:**

Create `/etc/systemd/system/course-writer.service`:
```ini
[Unit]
Description=Course Generator Writer Worker
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/kursovae
ExecStart=/usr/bin/python3 -m workers start --name writer_remote --host 0.0.0.0 --port 9501
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable course-writer.service
sudo systemctl start course-writer.service

# Check status
sudo systemctl status course-writer.service
```

**On Worker PC 2:**

Similar, but with critic configuration.

### Auto-start Tailscale

Already enabled by default:
```bash
sudo systemctl status tailscaled
```

---

## Monitoring & Debugging

### Check Tailscale Status

```bash
# On any machine
sudo tailscale status

# Output example:
# IP              Node                  Status
# 100.64.0.1      main-pc              active; running
# 100.64.0.2      worker-pc-1          active; running
# 100.64.0.3      worker-pc-2          active; running
```

### Test Connectivity

```bash
# From main PC
nc -zv 100.64.0.2 9501
# Output: Connection to 100.64.0.2 9501 port [tcp/*] succeeded!

# From main PC
curl -v http://100.64.0.2:9501/health
# Should return worker health JSON
```

### Monitor Worker Logs

```bash
# On each worker PC
tail -f logs/generator.log | grep -i worker

# On main PC
python -m workers health  # Continuous monitor
```

### Troubleshooting Connection Issues

**Problem:** Cannot connect to remote worker

```bash
# 1. Check Tailscale is running
sudo systemctl status tailscaled

# 2. Check Tailscale is connected
sudo tailscale status

# 3. Ping remote IP
ping 100.64.0.2

# 4. Check firewall (usually not needed with Tailscale)
sudo ufw allow 9501
sudo ufw allow 9502

# 5. Check worker is actually listening
netstat -tlnp | grep 9501  # On worker PC
```

**Problem:** Worker starts but marked UNHEALTHY

```bash
# 1. Check worker logs
tail -f logs/generator.log

# 2. Test direct connection
curl -v http://100.64.0.2:9501/health

# 3. Increase logging
python -m workers start --name w1 --port 9501 --verbose
```

---

## Performance Considerations

### Network Latency

Tailscale adds minimal latency (usually <5ms):

```bash
# Check latency
ping 100.64.0.2

# Typical output:
# bytes=32 time=2-5ms TTL=64
```

### Bandwidth

- Text generation requests: ~100KB-1MB per chapter
- Tailscale overhead: < 1% for typical usage

### Scalability

Tested configurations:
- ✅ 2 worker machines
- ✅ 3 worker machines
- ✅ 5 worker machines (excellent scalability)

---

## Security Best Practices

### Tailscale Authorization

By default, all devices in your Tailnet can reach each other. To restrict:

1. Go to https://login.tailscale.com
2. Settings → ACLs (Access Control Lists)
3. Example restrictive policy:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["group:workers"],
      "dst": ["group:main:9501,9502,8000"]
    }
  ],
  "groups": {
    "main": ["user@example.com"],
    "workers": ["worker1@example.com", "worker2@example.com"]
  }
}
```

### Firewall on Worker PCs

```bash
# Allow only Tailscale interface
sudo ufw default deny incoming
sudo ufw allow 9501/tcp  # Writer port
sudo ufw allow 9502/tcp  # Critic port
sudo ufw enable
```

### Credentials & Tokens

- Tailscale uses OAuth tokens (automatic, secure)
- Don't share tailnet with untrusted users
- Revoke access: https://login.tailscale.com/admin/machines

---

## Advanced: Multi-Region Deployment

If workers are in different regions (e.g., AWS, GCP, Azure):

```python
WORKERS = [
    # US-East cluster
    {"name": "writer_us_east", "host": "100.64.0.2", "port": 9501, "models": ["qwen-course"], "region": "us-east"},

    # EU cluster
    {"name": "writer_eu", "host": "100.64.0.3", "port": 9501, "models": ["qwen-course"], "region": "eu-west"},

    # AP cluster
    {"name": "critic_ap", "host": "100.64.0.4", "port": 9502, "models": ["deepseek-course"], "region": "ap-south"},
]
```

Tailscale automatically routes through the fastest path!

---

## Cleanup & Removal

### Stop Worker

```bash
# Graceful shutdown
pkill -f "python -m workers"

# Or systemd
sudo systemctl stop course-writer.service
```

### Remove from Tailscale

On the machine:
```bash
sudo tailscale logout
```

Or remotely:
1. Go to https://login.tailscale.com/admin/machines
2. Click the machine
3. "Remove machine"

---

## Quick Reference

```bash
# Install
curl -fsSL https://tailscale.com/install.sh | sh

# Connect
sudo tailscale up

# Check status
sudo tailscale status

# Get IP
sudo tailscale ip -4

# Start worker
python -m workers start --name w1 --host 0.0.0.0 --port 9501

# Monitor
python -m workers health

# Test connectivity
ping 100.64.0.2
nc -zv 100.64.0.2 9501
```

---

## Support & Resources

- **Tailscale Docs**: https://tailscale.com/kb/
- **Community Forum**: https://github.com/tailscale/tailscale/discussions
- **Status Page**: https://status.tailscale.com/
- **Security**: https://tailscale.com/security/

---

**Next:** See `SETUP_GUIDE.md` for complete deployment walkthrough.
