# 🖥️ HOST SETUP GUIDE

Руководство по настройке главного компьютера (Хоста/Оркестратора) для Course Generator v5.5.

---

## Содержание

1. [Системные требования](#системные-требования)
2. [Шаг 1: Установка Tailscale](#шаг-1-установка-tailscale)
3. [Шаг 2: Установка зависимостей](#шаг-2-установка-зависимостей)
4. [Шаг 3: Выбор LLM Backend](#шаг-3-выбор-llm-backend)
5. [Шаг 4: Конфигурация воркеров](#шаг-4-конфигурация-воркеров)
6. [Шаг 5: Запуск генерации](#шаг-5-запуск-генерации)
7. [Шаг 6: Мониторинг](#шаг-6-мониторинг)
8. [Команды для быстрого старта](#команды-для-быстрого-старта)

---

## Системные требования

### Железо:
- **CPU:** Intel/AMD с 4+ ядрами
- **RAM:** 16GB+ (8GB минимум)
- **GPU:** Рекомендуется (опционально для CUDA/ROCm)
- **Диск:** 30GB+ свободного места (для моделей)
- **Сеть:** Ethernet или Wi-Fi для подключения к Tailscale

### ПО:
- **OS:** Linux (Ubuntu 20.04+), macOS 11+, Windows 10/11
- **Python:** 3.9+
- **Git:** для клонирования репозитория
- **Tailscale:** для VPN подключения к воркерам

---

## Шаг 1: Установка Tailscale

Tailscale нужен для безопасного подключения к удаленным воркерам.

### Linux (Ubuntu/Debian)

```bash
# Установка
curl -fsSL https://tailscale.com/install.sh | sh

# Запуск демона
sudo systemctl enable tailscaled
sudo systemctl start tailscaled

# Подключение к вашему Tailscale аккаунту
sudo tailscale up

# Проверка подключения (откроется браузер для логина)
sudo tailscale status
```

### macOS

```bash
# Установка через Homebrew
brew install tailscale

# Запуск в фоне
brew services start tailscale

# Подключение
sudo tailscale up

# Проверка
sudo tailscale status
```

### Windows

```powershell
# Скачайте установщик:
# https://tailscale.com/download/windows

# Или через Chocolatey:
choco install tailscale

# Подключение
tailscale up

# Проверка
tailscale status
```

### Получение Tailscale IP

```bash
# Linux/macOS
TAILSCALE_IP=$(sudo tailscale ip -4)
echo "Ваш Tailscale IP: $TAILSCALE_IP"

# Windows
tailscale ip -4
```

**Запомните этот IP!** Его нужно будет сообщить воркерам.

Пример:
```
Ваш Tailscale IP: 100.64.0.1
```

---

## Шаг 2: Установка зависимостей

### Клонирование проекта

```bash
# Выберите директорию
cd ~/projects  # или другая

# Клонируйте репозиторий
git clone <project-repo> kursovae
cd kursovae

# Проверьте структуру
ls -la
# Должны быть файлы: config.py, main.py, llm/, workers/, и т.д.
```

### Создание виртуального окружения

```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### Установка зависимостей

```bash
# Обновите pip
pip install --upgrade pip

# Установите зависимости
pip install -r requirements.txt

# Проверка
python -c "import llm, workers; print('✓ OK')"
```

---

## Шаг 3: Выбор LLM Backend

### Вариант A: Ollama (Простенький, для тестирования)

#### Установка Ollama

```bash
# Скачайте с https://ollama.ai

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# macOS & Windows - графический установщик с сайта
```

#### Загрузка моделей

```bash
# Загрузите модели
ollama pull qwen-course
ollama pull deepseek-course

# Проверка загруженных моделей
curl http://localhost:11434/api/tags | jq '.models[].name'

# Должно вывести:
# "qwen-course"
# "deepseek-course"
```

#### Конфигурация (config.py)

```python
# config.py

LLM_BACKEND_TYPE = "ollama"

OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
OLLAMA_TIMEOUT = 300
```

#### Проверка

```bash
curl http://localhost:11434/api/tags

# Ответ должен содержать ваши модели
```

---

### Вариант B: llama.cpp (Быстрее, рекомендуется)

#### Установка llama.cpp

```bash
# Клонируйте репозиторий
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# Компиляция
make

# На Windows используйте CMake:
mkdir build
cd build
cmake ..
cmake --build . --config Release
cd ..
```

#### Загрузка моделей

```bash
# Создайте директорию для моделей
mkdir -p ~/models  # или D:\models на Windows

# Скачайте GGUF модели
# qwen-course.gguf
# deepseek-course.gguf

# Поместите их в ~/models/
ls ~/models/
# qwen-course.gguf
# deepseek-course.gguf
```

#### Запуск сервера

```bash
# Из директории llama.cpp
./server \
  -m ~/models/qwen-course.gguf \
  -ngl 999 \
  -c 2048 \
  --port 8000 \
  --host 127.0.0.1

# На Windows:
# .\server.exe -m D:\models\qwen-course.gguf -ngl 999 --port 8000
```

**Флаги:**
- `-ngl 999` — загрузить все слои на GPU
- `-c 2048` — размер контекста
- `--port 8000` — порт сервера
- `-t 8` — количество потоков CPU (если нет GPU)

#### Конфигурация (config.py)

```python
# config.py

LLM_BACKEND_TYPE = "llamacpp"

LLAMACPP_INSTANCES = [("127.0.0.1", 8000)]

LLAMACPP_TIMEOUT = 600
```

#### Проверка

```bash
curl http://localhost:8000/health

# Ответ: {"status":"ok"}
```

---

## Шаг 4: Конфигурация воркеров

Отредактируйте `config.py`:

### Вариант 1: Только локальные воркеры (на одном ПК)

```python
# config.py

# Включите систему воркеров
WORKER_ENABLED = True

# Порт координатора (обычно 9500)
WORKER_COORDINATOR_PORT = 9500

# Локальные воркеры (на этом же ПК)
WORKERS = [
    {
        "name": "writer_local",
        "host": "127.0.0.1",
        "port": 9501,
        "models": ["qwen-course"]
    },
    {
        "name": "critic_local",
        "host": "127.0.0.1",
        "port": 9502,
        "models": ["deepseek-course"]
    },
]

# Максимум параллельных глав
MAX_CONCURRENT_CHAPTERS = 2

# Валидация после генерации
CHAPTER_VALIDATION_ENABLED = True
```

**Чтобы запустить локальных воркеров:** см. ниже (Шаг 5)

### Вариант 2: Удаленные воркеры (через Tailscale)

```python
# config.py

WORKER_ENABLED = True

# Удаленные воркеры через Tailscale
WORKERS = [
    {
        "name": "writer_remote_1",
        "host": "100.64.0.2",  # Tailscale IP воркера 1
        "port": 9501,
        "models": ["qwen-course"]
    },
    {
        "name": "critic_remote",
        "host": "100.64.0.3",   # Tailscale IP воркера 2
        "port": 9502,
        "models": ["deepseek-course"]
    },
]

MAX_CONCURRENT_CHAPTERS = 2
CHAPTER_VALIDATION_ENABLED = True
```

### Вариант 3: Смешанная конфигурация (локальные + удаленные)

```python
# config.py

WORKER_ENABLED = True

WORKERS = [
    # Локальные
    {
        "name": "writer_local",
        "host": "127.0.0.1",
        "port": 9501,
        "models": ["qwen-course"]
    },

    # Удаленные через Tailscale
    {
        "name": "critic_remote",
        "host": "100.64.0.3",
        "port": 9502,
        "models": ["deepseek-course"]
    },
]

MAX_CONCURRENT_CHAPTERS = 2
CHAPTER_VALIDATION_ENABLED = True
```

---

## Шаг 5: Запуск генерации

### Подготовка к запуску

```bash
# Активируйте виртуальное окружение
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate      # Windows

# Проверьте, что все работает
python -m workers config
# Должна вывести список воркеров из config.py
```

### Проверка настроек

```bash
# Убедитесь что backend запущен
# Ollama:
curl http://localhost:11434/api/tags

# llama.cpp:
curl http://localhost:8000/health

# Проверьте воркеры (если они локальные, запустите их сначала)
python -m workers list
```

### Запуск генерации

```bash
# Простая проверка (только валидация без генерации)
python main.py data/input/task.json --validate-only

# Полная генерация
python main.py data/input/task.json

# Возобновление из checkpoint
python main.py data/input/task.json --resume session_XXXXXXXX

# Список сессий
python main.py --list-sessions
```

---

## Шаг 6: Мониторинг

### Проверка статуса воркеров

```bash
# Просмотр здоровья всех воркеров
python -m workers health

# Пример вывода:
# === Worker Health Check ===
#
# writer_local: ✓ HEALTHY (127.0.0.1:9501)
# critic_remote: ✓ HEALTHY (100.64.0.3:9502)
```

### Просмотр логов

```bash
# Real-time логи генерации
tail -f logs/generator.log

# Только логи воркеров
tail -f logs/generator.log | grep -i worker

# Только логи ошибок
tail -f logs/generator.log | grep -i error

# На Windows используйте PowerShell:
# Get-Content logs/generator.log -Wait
```

### Проверка процесса

```bash
# Просмотр прогресса (каждые 5 секунд)
watch -n 5 'python -m workers health'

# На Windows:
# while(1) { python -m workers health; Start-Sleep 5; Clear-Host }
```

### Проверка Tailscale

```bash
# Статус Tailscale
sudo tailscale status

# Проверка подключения к воркерам
ping 100.64.0.2
ping 100.64.0.3

# Проверка портов
nc -zv 100.64.0.2 9501  # Linux/macOS
# или
Test-NetConnection -ComputerName 100.64.0.2 -Port 9501  # Windows
```

---

## Команды для быстрого старта

### Вариант 1: Локально (на одном ПК)

```bash
# Терминал 1: Backend LLM
# Ollama:
ollama serve

# или llama.cpp:
cd llama.cpp
./server -m ~/models/qwen-course.gguf -ngl 999 --port 8000

# Терминал 2: Воркер 1
source venv/bin/activate
python -m workers start --name writer_local --host 127.0.0.1 --port 9501

# Терминал 3: Воркер 2
source venv/bin/activate
python -m workers start --name critic_local --host 127.0.0.1 --port 9502

# Терминал 4: Проверка и генерация
source venv/bin/activate
python -m workers health
python main.py data/input/task.json
```

### Вариант 2: Удаленно (Tailscale)

```bash
# На хосте:

# Шаг 1: Убедитесь что Tailscale запущен
sudo tailscale status

# Шаг 2: Запустите backend
ollama serve  # или llama.cpp server

# Шаг 3: Проверьте конфиг (должны быть IP воркеров)
python -m workers config

# Шаг 4: Проверьте куда подключаются воркеры
python -m workers discover

# Шаг 5: Проверьте здоровье воркеров
python -m workers health

# Шаг 6: Запустите генерацию
python main.py data/input/task.json
```

---

## Troubleshooting

### Backend недоступен

```bash
# Проверьте Ollama
curl -v http://localhost:11434/api/tags

# Проверьте llama.cpp
curl -v http://localhost:8000/health

# Если ошибка, перезапустите:
# Ollama: sudo systemctl restart ollama
# llama.cpp: Ctrl+C и заново ./server ...
```

### Воркеры не видны

```bash
# Если локальные - убедитесь что они запущены
ps aux | grep "workers start"

# Если удаленные - проверьте Tailscale
sudo tailscale status

# Проверьте ping
ping 100.64.0.2

# Проверьте портов
nc -zv 100.64.0.2 9501
```

### Timeout при подключении

```bash
# Увеличьте timeout в config.py:
OLLAMA_TIMEOUT = 600  # 10 минут
LLAMACPP_TIMEOUT = 1200  # 20 минут

# Или уменьшите нагрузку:
MAX_CONCURRENT_CHAPTERS = 1
```

### Out of Memory (OOM)

```bash
# Уменьшите контекст:
# В llama.cpp: -c 1024 (вместо -c 2048)

# Или в config.py:
MAX_CONCURRENT_CHAPTERS = 1

# Используйте меньшую модель (3B-5B вместо 7B-8B)
```

---

## Оптимизация производительности

### CPU Optimization

```bash
# Увеличьте количество потоков в llama.cpp:
./server -t 16 -m models/qwen-course.gguf

# t = количество ядер вашего CPU (обычно 8-32)
```

### GPU Optimization

```bash
# Запустите все на GPU:
./server -ngl 999 -m models/qwen-course.gguf

# Multi-GPU:
./server -ngl 999 -mg 0,1 -m models/qwen-course.gguf
# (для GPU 0 и GPU 1)
```

### Параллелизм

```python
# config.py

# Увеличьте количество параллельных глав:
MAX_CONCURRENT_CHAPTERS = 3  # если достаточно памяти

# Но не более:
# - CPU: 2-3 (по количеству ядер / 4)
# - GPU 8GB: 2
# - GPU 16GB: 3
# - GPU 24GB+: 4+
```

---

## Финальная проверка

```bash
# 1. Проверьте backend
python -c "from llm import create_backend; b = create_backend(); print('✓ Backend OK')"

# 2. Проверьте воркеры
python -m workers config

# 3. Проверьте здоровье
python -m workers health

# 4. Запустите тестовый прогон
python main.py data/input/task.json --validate-only

# Если все вывело без ошибок - готово к запуску!
```

---

## Безопасность

### Tailscale

```bash
# Просмотрите кто подключен
sudo tailscale list

# Если нужно отозвать доступ:
sudo tailscale logout

# Или через веб: https://login.tailscale.com/admin/machines
```

### Firewall

```bash
# Разрешите только необходимые порты
sudo ufw default deny incoming
sudo ufw allow 9500/tcp  # Coordinator
sudo ufw allow 9501/tcp  # Workers
sudo ufw allow 9502/tcp  # Workers
sudo ufw enable
```

---

## Получение помощи

```bash
# Посмотрите документацию
cat WORKER_DEPLOYMENT.md
cat TAILSCALE_WORKERS.md
cat COMPLETE_DEPLOYMENT.md

# Проверьте логи
tail -f logs/generator.log

# Запустите диагностику
python -m workers health
python -m workers discover
python -c "import llm; print(create_backend())"
```

---

## Краткая схема HoST + WORKERS

```
┌─────────────────────────────────────────┐
│  YOUR HOST MACHINE                      │
│  (100.64.0.1 на Tailscale)             │
├─────────────────────────────────────────┤
│                                         │
│  ✓ Ollama/llama.cpp (port 8000/11434) │
│  ✓ Python venv                          │
│  ✓ config.py с IP воркеров             │
│  ✓ main.py для генерации               │
│                                         │
└─────────────────────────────────────────┘
                    ↓ Tailscale VPN
        ┌───────────┴──────────┐
        ↓                      ↓
┌──────────────────┐  ┌──────────────────┐
│ WORKER 1         │  │ WORKER 2         │
│ (100.64.0.2)     │  │ (100.64.0.3)     │
├──────────────────┤  ├──────────────────┤
│ LLM Backend      │  │ LLM Backend      │
│ Port: 9501       │  │ Port: 9502       │
│ Model: qwen      │  │ Model: deepseek  │
└──────────────────┘  └──────────────────┘
```

---

**Готово! Переходите к [WORKER_SETUP.md](WORKER_SETUP.md) для настройки воркеров.**
