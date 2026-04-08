# 🚀 Quick Start: 5-Minute Setup

For impatient users. Full details in [COMPLETE_DEPLOYMENT.md](COMPLETE_DEPLOYMENT.md).

## Single Machine (Testing)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start LLM backend
ollama serve  # or ./llama.cpp/server -m models/qwen-course.gguf -ngl 999 --port 8000

# 3. Start workers (separate terminals)
python -m workers start --name w1 --port 9501
python -m workers start --name c1 --port 9502

# 4. Configure config.py
WORKER_ENABLED = True
WORKERS = [
    {"name": "w1", "host": "127.0.0.1", "port": 9501, "models": ["qwen-course"]},
    {"name": "c1", "host": "127.0.0.1", "port": 9502, "models": ["deepseek-course"]},
]

# 5. Verify
python -m workers health

# 6. Run
python main.py data/input/task.json
```

## Multiple Machines (Production)

```bash
# 1. All machines: Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# 2. Get IPs
sudo tailscale ip -4  # Note these

# 3. Main PC: Update config.py
WORKER_ENABLED = True
WORKERS = [
    {"name": "w_remote", "host": "100.64.0.2", "port": 9501, "models": ["qwen-course"]},
    {"name": "c_remote", "host": "100.64.0.3", "port": 9502, "models": ["deepseek-course"]},
]

# 4. Worker PC 1 & 2: Start workers
python -m workers start --name w_remote --host 0.0.0.0 --port 9501
python -m workers start --name c_remote --host 0.0.0.0 --port 9502

# 5. Main PC: Verify
python -m workers health

# 6. Main PC: Run
python main.py data/input/task.json
```

## Troubleshooting

```bash
# Worker not found?
python -m workers discover

# Can't connect?
sudo tailscale status
ping 100.64.0.2

# Out of memory?
MAX_CONCURRENT_CHAPTERS = 1

# Slow generation?
# Check: python -m workers health
# Then: tail -f logs/generator.log
```

---

See [COMPLETE_DEPLOYMENT.md](COMPLETE_DEPLOYMENT.md) for detailed setup.
