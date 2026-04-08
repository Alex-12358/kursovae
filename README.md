# course-generator-v5

Intelligent automated coursework generation system using LLM with distributed worker architecture.

## Features

✨ **Latest in v5.5:**
- **Backend Abstraction**: Seamlessly switch between Ollama and llama.cpp backends
- **Distributed Workers**: Run parallel worker processes for 2-3× speedup
- **Chapter Parallelism**: Generate multiple chapters simultaneously with semaphore control
- **Real-time Validation**: Validate chapters immediately after generation
- **Load Balancing**: Distribute requests across multiple LLM instances
- **Worker CLI**: Easy management of worker processes (`python -m workers start/list/health`)

## Quick Start

### 1. Configuration

Edit `config.py`:

```python
# Choose backend
LLM_BACKEND_TYPE = "ollama"  # or "llamacpp"

# Enable chapter parallelism
MAX_CONCURRENT_CHAPTERS = 2
CHAPTER_VALIDATION_ENABLED = True

# Optional: Enable distributed workers
WORKER_ENABLED = False
WORKERS = [
    # {"name": "writer_1", "host": "127.0.0.1", "port": 9501, "models": ["qwen-course"]},
]
```

### 2. Run Course Generation

```bash
python main.py data/input/task.json
```

## Architecture

### Backend Abstraction Layer
- Supports **Ollama** (default) and **llama.cpp** backends
- Factory pattern for seamless switching
- Load balancing across multiple instances

### Distributed Worker System
- Worker processes accept RPC requests over TCP
- Coordinator manages health and task distribution
- Fallback to local backend if workers unavailable

### Chapter-Level Parallelism
- Chapters process concurrently (limited by `MAX_CONCURRENT_CHAPTERS`)
- Validation runs immediately after each chapter
- 2-3× speedup with 2 concurrent chapter generation

### Validation Engine
- Checks formula markers: `[FORMULA]...[/FORMULA]`
- Verifies figure/table references
- Validates cross-references and structure
- Returns detailed issue reports with fixes

## Performance

| Setup | Time | Speedup |
|-------|------|---------|
| Sequential (Ollama) | 3+ hours | 1× |
| Parallel (Ollama, 2 chapters) | 1.5-2 hours | 2× |
| Parallel (llama.cpp, 2 chapters) | 1-1.5 hours | 3× |

## Migration: Ollama → llama.cpp

### Installation

1. **Install llama.cpp**
   ```bash
   git clone https://github.com/ggerganov/llama.cpp.git
   cd llama.cpp && make
   ```

2. **Download Models**
   ```bash
   # Place GGUF models in ./models/
   models/
   ├── qwen-course.gguf
   └── deepseek-course.gguf
   ```

3. **Start Server**
   ```bash
   ./server -m models/qwen-course.gguf -ngl 999 --port 8000
   ```

4. **Update Config**
   ```python
   LLM_BACKEND_TYPE = "llamacpp"
   LLAMACPP_INSTANCES = [("127.0.0.1", 8000)]
   ```

See [LLAMACPP_SETUP.md](LLAMACPP_SETUP.md) for detailed instructions.

## Distributed Workers

### Start Workers

```bash
# Terminal 1 - Writer worker
python -m workers start --name writer_1 --port 9501

# Terminal 2 - Critic worker
python -m workers start --name critic_1 --port 9502
```

### Configure

```python
WORKER_ENABLED = True
WORKERS = [
    {"name": "writer_1", "host": "127.0.0.1", "port": 9501, "models": ["qwen-course"]},
    {"name": "critic_1", "host": "127.0.0.1", "port": 9502, "models": ["deepseek-course"]},
]
```

### Manage

```bash
python -m workers list      # List all workers
python -m workers health    # Check health
python -m workers config    # Show configuration
```

See [WORKER_DEPLOYMENT.md](WORKER_DEPLOYMENT.md) for setup guides.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — System design and components
- [LLAMACPP_SETUP.md](LLAMACPP_SETUP.md) — llama.cpp installation and tuning
- [WORKER_DEPLOYMENT.md](WORKER_DEPLOYMENT.md) — Worker system guide

## Project Structure

```
llm/
├── backends/              # LLM backend implementations
│   ├── base.py           # Abstract interface
│   ├── ollama_backend.py # Ollama implementation
│   ├── llamacpp_backend.py # llama.cpp implementation
│   └── load_balancer.py  # Load distribution
├── gateway.py            # Legacy (now routes to backends)
├── queue.py              # Task queue system
└── router.py             # Model selection

workers/                   # Distributed worker system
├── worker.py             # Worker server process
├── coordinator.py        # Worker management
├── client.py             # RPC client
└── cli.py                # Command-line interface

core/
├── dag.py                # DAG execution with chapter parallelism
└── orchestrator.py       # Pipeline orchestration

validation/
├── chapter_validator.py  # NEW: Real-time validation
├── gost_linter.py
└── gost_fixer.py

pipeline/
├── writer.py             # Text generation
├── planner.py            # Structure planning
├── critic.py             # Quality review
└── smart_critic.py       # Deep analysis

calc/                      # Calculation engines
├── engine.py
├── shaft.py
├── coupling.py
└── ...
```

## Configuration

Key settings in `config.py`:

```python
# Backend selection
LLM_BACKEND_TYPE = "ollama"  # or "llamacpp"

# Chapter parallelism
MAX_CONCURRENT_CHAPTERS = 2
CHAPTER_VALIDATION_ENABLED = True

# Worker system
WORKER_ENABLED = False
WORKERS = [...]

# Timeouts and retries
OLLAMA_TIMEOUT = 300
LLAMACPP_TIMEOUT = 600
```

## Command Line

```bash
# Generate course
python main.py task.json

# Resume session
python main.py task.json --resume session_20240401_120000

# List sessions
python main.py --list-sessions

# Validate only
python main.py task.json --validate-only

# Manage workers
python -m workers start --name w1 --port 9501
python -m workers list
python -m workers health
```

## Performance Tips

1. **Use llama.cpp** for 20-30% speedup over Ollama
2. **Enable parallelism** with `MAX_CONCURRENT_CHAPTERS = 2-3`
3. **Start workers** for 2-3× throughput improvement
4. **Monitor health** with `python -m workers health`
5. **Scale horizontally** by adding more worker processes

## Troubleshooting

### Backend unavailable
```bash
# Check Ollama
curl http://localhost:11434/api/tags

# Check llama.cpp
curl http://localhost:8000/health
```

### Worker connection failed
```bash
# Verify worker is running
python -m workers list

# Check port is available
netstat -an | grep 9501
```

### Out of memory (OOM)
- Reduce context: `-c 1024` instead of `-c 2048`
- Use smaller models (3B-5B instead of 7B-8B)
- Decrease `MAX_CONCURRENT_CHAPTERS = 1`

## Development

### Add a New Backend
1. Create `llm/backends/mybackend.py`
2. Implement `LLMBackend` interface
3. Add case in `llm/__init__.py` factory
4. Update documentation

### Extend Validation
1. Add method to `ChapterValidator`
2. Call in `validate()` method
3. Return issue dict

### Test Changes
```bash
pytest tests/
```

## Requirements

- Python 3.9+
- aiohttp (async HTTP)
- python-docx (DOCX generation)
- FAISS (vector search)
- PyYAML (config)

See `requirements.txt` for full list.

## License

Proprietary

## Support

For issues and questions:
- Check documentation files (ARCHITECTURE.md, etc.)
- Review logs in `logs/generator.log`
- Run `python -m workers health` for worker diagnostics
