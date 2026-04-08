# Course Generator v5 — Architecture & Migration Guide

## Overview

Course Generator v5 is a distributed LLM-based system for generating technical coursework documents automaticallyдлядетальлеймашин.

**Key Components:**
- **LLM Backend Abstraction**: Supports Ollama and llama.cpp
- **Worker Distribution System**: Parallel chapter generation with multiple workers
- **Intelligent Validation**: Real-time chapter validation with error detection
- **Load Balancing**: Distribute requests across multiple backend instances

## Architecture Layers

### Layer 1: LLM Backend Abstraction (`llm/backends/`)

**Purpose**: Abstract away specific LLM backend implementation details.

**Components:**
- `base.py` — Abstract `LLMBackend` interface
- `ollama_backend.py` — Ollama HTTP API implementation
- `llamacpp_backend.py` — llama.cpp HTTP API implementation
- `load_balancer.py` — Instance selection and load tracking

**Usage:**
```python
from llm import create_backend

backend = create_backend()  # Uses config.LLM_BACKEND_TYPE
response = await backend.chat("qwen-course", messages, temperature=0.7)
```

**Configuration** (`config.py`):
```python
LLM_BACKEND_TYPE = "ollama"  # or "llamacpp"

# Ollama config
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434

# llama.cpp config
LLAMACPP_INSTANCES = [("127.0.0.1", 8000)]
```

### Layer 2: Worker Distribution (`workers/`)

**Purpose**: Run multiple worker processes for parallel task execution.

**Components:**
- `worker.py` — Worker server accepting TCP RPC requests
- `client.py` — RPC client for communicating with workers
- `coordinator.py` — Manages worker registry and health
- `cli.py` — Command-line interface for worker management

**Architecture:**
```
Main Process (Orchestrator)
    ↓
Worker Coordinator
    ├── Writer Worker (port 9501)
    ├── Critic Worker (port 9502)
    └── Writer Worker 2 (port 9503)
```

**Usage:**
```bash
# Start a worker
python -m workers start --name writer_1 --port 9501

# List workers
python -m workers list

# Health check
python -m workers health
```

**Configuration** (`config.py`):
```python
WORKER_ENABLED = True
WORKERS = [
    {"name": "writer_1", "host": "127.0.0.1", "port": 9501, "models": ["qwen-course"]},
    {"name": "critic_1", "host": "127.0.0.1", "port": 9502, "models": ["deepseek-course"]},
]
```

### Layer 3: Task Distribution (DAG + Parallelism)

**Purpose**: Execute text generation in parallel with proper dependencies.

**Modifications to `core/dag.py`:**
- `node_text_engine()` now uses `asyncio.Semaphore` for chapter-level parallelism
- Chapters process concurrently (limited by `MAX_CONCURRENT_CHAPTERS`)
- Each chapter passes through validation immediately after generation

**Configuration** (`config.py`):
```python
MAX_CONCURRENT_CHAPTERS = 2  # Parallel chapter limit
CHAPTER_VALIDATION_ENABLED = True  # Validate after generation
```

### Layer 4: Quality Control (`validation/chapter_validator.py`)

**Purpose**: Validate chapters immediately after generation.

**Checks:**
- Formula marker pairing: `[FORMULA]...[/FORMULA]`
- Figure references: `[FIGURE:...]` markers exist
- Table references: `[TABLE:...]` markers complete
- Cross-references: Links are valid
- Chapter length: Within MIN/MAX bounds

**Result:**
```json
{
    "chapter_idx": 1,
    "verdict": "PASS|REVIEW|FAIL",
    "score": 0.95,
    "issues": [...],
    "issues_summary": {"critical": 0, "major": 0, "minor": 1},
    "suggested_rewrites": []
}
```

## Migration Path: Ollama → llama.cpp

### Step 1: Install llama.cpp
```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp && make
```

### Step 2: Download Models
Place GGUF format models in `./models/`:
- `qwen-course.gguf`
- `deepseek-course.gguf`

### Step 3: Start llama.cpp Server
```bash
./server -m models/qwen-course.gguf -ngl 999 --port 8000
```

### Step 4: Update Configuration
```python
# config.py
LLM_BACKEND_TYPE = "llamacpp"
LLAMACPP_INSTANCES = [("127.0.0.1", 8000)]
```

### Step 5: Test
```bash
python main.py data/input/task.json
```

**That's it!** No code changes needed. The abstraction layer handles everything.

## Performance Improvements

### Before (Sequential)
```
Chapter 1: ████████████ (15 min)
Chapter 2: ████████████ (15 min)
Chapter 3: ████████████ (15 min)
...
Total: 14 chapters × 15 min = 210 minutes (3.5 hours)
```

### After (Parallel with 2 concurrent)
```
Chapter 1: ████░░ | Chapter 2: ████░░ (parallel)
Chapter 3: ████░░ | Chapter 4: ████░░ (parallel)
...
Total: 210 / 2 ≈ 105 minutes (1.75 hours) — 2× faster!
```

### With llama.cpp + Load Balancing
```
- 20-30% faster generation (llama.cpp vs Ollama)
- Better resource utilization (load balancer distributes requests)
- Estimated: 105 × 0.75 ≈ 80 minutes (1.3 hours)
```

## Development Workflow

### Adding New Backend
1. Create `llm/backends/newbackend.py`
2. Implement `LLMBackend` interface (abstract class)
3. Add case in `llm/__init__.py` factory
4. Add config parameters
5. Update documentation

### Adding Worker Types
1. Create specialized worker subclass (extend `LLMWorkerServer`)
2. Register in `WORKERS` config
3. Coordinator automatically manages it

### Extending Validation
1. Add check method to `ChapterValidator`
2. Call it in `validate()` method
3. Return issue dict with type, severity, location, fix

## Testing

### Unit Tests
```bash
pytest tests/test_llamacpp_backend.py
pytest tests/test_worker_client.py
pytest tests/test_chapter_validator.py
```

### Integration Tests
```bash
# Full generation with llama.cpp
python main.py task.json --backend llamacpp

# With distributed workers
python -m workers start --name w1 --port 9501 &
python main.py task.json --workers enabled
```

## Troubleshooting

### Issue: "Backend unavailable"
- **Cause**: llama.cpp server not running
- **Fix**: Start server: `./server -m models/qwen-course.gguf -ngl 999 --port 8000`

### Issue: "Worker timeout"
- **Cause**: Network latency or slow backend
- **Fix**: Increase timeout in `workers/client.py` or add more workers

### Issue: "Memory error (OOM)"
- **Cause**: Model too large or context window too big
- **Fix**: Reduce context size or use smaller models

### Issue: "Chapters not validating"
- **Cause**: Formula/figure markers missing
- **Fix**: Ensure Planner and Writer use correct markers in prompts

## Performance Guidelines

| Component | Typical Duration | Bottleneck |
|-----------|------------------|------------|
| Planning (Planner) | 2-3 min | LLM |
| Writing 1 chapter (Writer) | 5-15 min | LLM |
| Validating 1 chapter | <1 min | Regex matching |
| Critiquing 1 chapter (Critic) | 3-5 min | LLM |
| Full course (14 chapters) | 1.5-3 hours | Chapter parallelism |

**Optimization:**
- Use llama.cpp for 20-30% speedup
- Parallelize chapters (2× speedup)
- Combine: 3× total speedup possible

## Future Enhancements

1. **Distributed Checkpoints**: Store checkpoints across workers
2. **Advanced Load Balancing**: Least-loaded selection vs round-robin
3. **Model Fallback**: Automatic model switching if primary fails
4. **Streaming Responses**: Return text as generated (WebSocket)
5. **Multi-Language Support**: Extend validators for other languages
6. **Caching**: Cache LLM responses for deterministic generation
