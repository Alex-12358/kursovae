# llama.cpp Setup Guide

## Installation

### 1. Download llama.cpp

```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
```

### 2. Build llama.cpp

#### On Linux/macOS:
```bash
make
```

#### On Windows (with Visual Studio):
```bash
mkdir build
cd build
cmake ..
cmake --build . --config Release
```

### 3. Download Models

Download GGUF format models:
- `qwen-course.gguf` — Writer model (7B-8B)
- `deepseek-course.gguf` — Planner/Critic model (7B-8B)

Place them in: `./models/` directory

### 4. Run llama.cpp Server

```bash
# Single instance on port 8000
./server -m models/qwen-course.gguf -ngl 999 -c 2048 --port 8000

# Or with llama.cpp server wrapper (recommended)
python -m llama_cpp.server \
    --model models/qwen-course.gguf \
    --n_gpu_layers 999 \
    --port 8000
```

### 5. Configure Course Generator

Edit `config.py`:
```python
LLM_BACKEND_TYPE = "llamacpp"

LLAMACPP_INSTANCES = [
    ("127.0.0.1", 8000),  # Primary instance
    # ("127.0.0.1", 8001),  # Additional instances for load balancing
]
```

### 6. Test Connection

```bash
python -c "from llm import create_backend; backend = create_backend('llamacpp'); print(backend.health_check())"
```

## Performance Tuning

### GPU Acceleration
- Use `-ngl 999` flag to offload all layers to GPU
- Adjust `-c 2048` for context window size

### CPU Optimization
- Use `-t 8` for number of threads (adjust to your CPU cores)
- Use `-b 512` for batch size

### Multiple Instances (Load Balancing)

Start multiple instances on different ports:
```bash
# Terminal 1
./server -m models/qwen-course.gguf -ngl 999 --port 8000

# Terminal 2
./server -m models/deepseek-course.gguf -ngl 999 --port 8001

# Terminal 3
./server -m models/qwen-course.gguf -ngl 999 --port 8002 --devices GPU:0,GPU:1
```

Configure in `config.py`:
```python
LLAMACPP_INSTANCES = [
    ("127.0.0.1", 8000),  # qwen-course
    ("127.0.0.1", 8001),  # deepseek-course
    ("127.0.0.1", 8002),  # qwen-course (backup)
]
```

## Troubleshooting

### OOM (Out of Memory) Errors
- Reduce context size: `-c 1024` instead of `-c 2048`
- Use smaller models (3B-5B instead of 7B-8B)
- Don't use `-ngl 999`, use `-ngl 30` for partial GPU offloading

### Slow Generation
- Check GPU usage: `nvidia-smi` (NVIDIA) or `rocm-smi` (AMD)
- Increase number of threads: `-t 16` or `-t 32`
- Use multiple instances for parallel processing

### Connection Issues
- Verify llama.cpp server is running: `curl http://localhost:8000/health`
- Check firewall settings
- Ensure ports 8000-8002 are available
