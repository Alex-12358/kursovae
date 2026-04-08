# 👷 WORKER SETUP GUIDE

Руководство по настройке рабочих машин (Worker'ов) для Course Generator v5.5.

---

## ✅ Model Consolidation Architecture

**ВАЖНО:** Workers НЕ имеют локальных моделей. Они используют модели из HOST машины.

```
HOST (модели + основной процесс)          ← Модели здесь (20-50GB)
  └─ Ollama/llama.cpp (с моделями на :11434 или :8000)

WORKER 1 (только воркер)                   ← БЕЗ моделей (~100MB)
  └─ Worker сервер (:9501) → обращается к HOST backend'у через HTTP

WORKER 2 (только воркер)                   ← БЕЗ моделей (~100MB)
  └─ Worker сервер (:9502) → обращается к HOST backend'у через HTTP
```

**Преимущества:**
- ✅ Модели хранятся только на HOST машине (экономия дискапространства)
- ✅ Workers легкие: только Python вериф (~100MB vs 20-50GB на HOST)
- ✅ Легко добавлять новых worker'ов без загрузки моделей
- ✅ Легко обновлять модели: одно место вместо N worker'ов

---

## Содержание

1. [Системные требования](#системные-требования)
2. [Шаг 1: Установка Tailscale](#шаг-1-установка-tailscale)
3. [Шаг 2: Установка зависимостей](#шаг-2-установка-зависимостей)
4. [Шаг 3: Настройка HOST Backend URL](#шаг-3-настройка-host-backend-url)
5. [Шаг 4: Запуск Worker'а](#шаг-4-запуск-worker)
6. [Шаг 5: Подключение к HOST](#шаг-5-подключение-к-host)
7. [Шаг 6: Мониторинг Worker'а](#шаг-6-мониторинг-worker)
8. [Команды для быстрого старта](#команды-для-быстрого-старта)

---

## Системные требования

### Железо (для Worker'а):
- **CPU:** Intel/AMD с 1+ ядром (минимум, подойдёт старый компьютер)
- **RAM:** 2GB+ (достаточно для worker сервера, НЕ для моделей)
- **GPU:** Не требуется (модели на HOST машине)
- **Диск:** 500MB свободного места (для кода и логов)
- **Сеть:** Ethernet или Wi-Fi для подключения к HOST через Tailscale

**NOTE:** Workers работают очень быстро потому что НЕ запускают LLM модели - только пересылают запросы на HOST!

### ПО:
- **OS:** Linux (Ubuntu 20.04+), macOS 11+, Windows 10/11
- **Python:** 3.9+
- **Git:** для клонирования репозитория
- **Tailscale:** для безопасного подключения к HOST

---

## Шаг 1: Установка Tailscale

Tailscale позволяет безопасно подключить Worker к HOST машине.

### Linux (Ubuntu/Debian)

```bash
# Установка
curl -fsSL https://tailscale.com/install.sh | sh

# Запуск демона
sudo systemctl enable tailscaled
sudo systemctl start tailscaled

# Подключение к вашему Tailscale аккаунту
sudo tailscale up

# Следуйте ссылке в браузере, залогиньтесь в тот же аккаунт что и на HOST!
```

### macOS

```bash
# Установка
brew install tailscale

# Запуск в фоне
brew services start tailscale

# Подключение
sudo tailscale up

# Выполните вход в той же сети что и HOST
```

### Windows

```powershell
# Метод 1: Скачайте установщик
# https://tailscale.com/download/windows

# Метод 2: Через Chocolatey
choco install tailscale

# Подключение
tailscale up

# Выполните вход в той же сети что и HOST
```

### Получение Tailscale IP Worker'а

```bash
# Linux/macOS
WORKER_IP=$(sudo tailscale ip -4)
echo "My Tailscale IP: $WORKER_IP"

# Windows
tailscale ip -4
```

**Запомните этот IP** (например: `100.64.0.2`). Его нужно сообщить администратору HOST.

### Проверка подключения к HOST

```bash
# Пингуйте HOST машину (спросите IP у администратора)
ping 100.64.0.1

# Должен откликаться
# PING 100.64.0.1 (100.64.0.1) 56(84) bytes of data.
# 64 bytes from 100.64.0.1: icmp_seq=1 ttl=64 time=2.54 ms
```

---

## Шаг 2: Установка зависимостей

### Клонирование проекта

```bash
# Выберите директорию
cd ~/projects  # или другая

# Клонируйте репозиторий (ТОТ ЖЕ что на HOST)
git clone <project-repo> kursovae
cd kursovae

# Проверьте структуру
ls -la workers/
# Должны быть файлы: worker.py, client.py, cli.py
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
python -c "from workers.worker import LLMWorkerServer; print('✓ OK')"
```

---

## Шаг 3: Настройка HOST Backend URL

**ВАЖНО:** Workers НЕ устанавливают свой LLM Backend! Они обращаются к HOST backend'у.

Вам нужно узнать у администратора HOST:
- **HOST Backend URL** (например: `http://100.64.0.1:11434` для Ollama или `http://100.64.0.1:8000` для llama.cpp)

### Обновите config.py

```bash
# Откройте config.py в редакторе
nano config.py  # или используйте ваш редактор

# Найдите строку:
# HOST_BACKEND_URL = "http://127.0.0.1:11434"

# Замените на URL HOST машины:
HOST_BACKEND_URL = "http://100.64.0.1:11434"  # Замените 100.64.0.1 на IP вашего HOST
```

**Примеры:**
- Ollama на HOST: `http://100.64.0.1:11434`
- llama.cpp на HOST: `http://100.64.0.1:8000`

Проверьте что URL доступен:

```bash
# Pingуйте HOST backend
curl http://100.64.0.1:11434/api/tags  # Ollama
curl http://100.64.0.1:8000/health     # llama.cpp
```

---

**Для systemd (автозапуск):**

```bash
sudo systemctl enable ollama
sudo systemctl start ollama
sudo systemctl status ollama

# Если нужно другой порт, отредактируйте:
sudo nano /etc/systemd/system/ollama.service
# Добавьте: Environment="OLLAMA_HOST=0.0.0.0:11434"
```

### Вариант B: llama.cpp

```bash
# Клонируйте и компилируйте
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
make

# Скачайте модель (спросите у администратора)
# Поместите в ~/models/:
# ~/models/qwen-course.gguf
# ~/models/deepseek-course.gguf

# Запустите сервер (слушайте на 0.0.0.0)
cd ..
./llama.cpp/server \
  -m ~/models/qwen-course.gguf \
  -ngl 999 \
  --port 11434 \
  --host 0.0.0.0
```

**Флаги:**
- `-ngl 999` — загрузить все на GPU (если есть)
- `-t 8` — количество потоков (8-16 для CPU)
- `--host 0.0.0.0` — слушать все интерфейсы (для Tailscale)
- `--port 11434` — порт (используйте Ollama порт или другой по согласованию)

### Проверка LLM Backend

```bash
# Проверьте что backend отвечает
curl http://0.0.0.0:11434/api/tags            # Ollama
curl http://0.0.0.0:11434/health              # llama.cpp

# Должен вывести JSON с информацией
```

---

## Шаг 4: Запуск Worker'а

### Синтаксис

```bash
# Активируйте виртуальное окружение
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate      # Windows

# Запустите worker с указанием HOST backend URL
python -m workers start \
  --name <worker_name> \
  --host 0.0.0.0 \
  --port <port> \
  --host-backend-url <HOST_BACKEND_URL>

# Пример для Ollama:
python -m workers start --name writer_1 --host 0.0.0.0 --port 9501 --host-backend-url http://100.64.0.1:11434

# Пример для llama.cpp:
python -m workers start --name critic_1 --host 0.0.0.0 --port 9502 --host-backend-url http://100.64.0.1:8000
```

**Параметры:**
- `--name` — уникальное имя worker'а (например: `writer_1`, `critic_1`)
- `--host` — **ВСЕГДА** используйте `0.0.0.0` для Tailscale подключения!
- `--port` — порт для слушания (9501-9510 рекомендуется)
- `--host-backend-url` — URL HOST backend'а (например: `http://100.64.0.1:11434`)

**Или используйте config.py:**
Если вы обновили `HOST_BACKEND_URL` в config.py, параметр `--host-backend-url` не требуется:

```bash
python -m workers start --name writer_1 --host 0.0.0.0 --port 9501
```

### Пример запуска

```bash
# Writer worker (с явным URL)
python -m workers start --name writer_1 --host 0.0.0.0 --port 9501 --host-backend-url http://100.64.0.1:11434

# Output:
# INFO: Initialized LLMWorkerServer: writer_1 at 0.0.0.0:9501
# INFO: Will route requests to HOST backend: http://100.64.0.1:11434
# INFO: Worker server listening on 0.0.0.0:9501
```

**Оставьте этот процесс работать!** Закроется по Ctrl+C в конце.

### Запуск нескольких Worker'ов на одной машине

```bash
# Терминал 1: Writer
python -m workers start --name writer_1 --host 0.0.0.0 --port 9501 --host-backend-url http://100.64.0.1:11434

# Терминал 2: Critic
python -m workers start --name critic_1 --host 0.0.0.0 --port 9502 --host-backend-url http://100.64.0.1:11434

# Оба должны запуститься независимо и обращаться к HOST backend'у
```

---

## Шаг 5: Подключение к HOST

### Сообщить HOST ваш Tailscale IP и порты

Напишите администратору HOST:
```
Worker готов к подключению:
- Tailscale IP: 100.64.0.2
- Имя: writer_1
- Порт: 9501
- Модели: qwen-course
```

### HOST обновит config.py

На стороне HOST администратор добавит:

```python
# config.py на HOST
WORKERS = [
    {
        "name": "writer_1",
        "host": "100.64.0.2",      # Ваш Tailscale IP
        "port": 9501,               # Ваш порт
        "models": ["qwen-course"]
    },
]
```

### Проверка подключения HOST к Worker'у

**На ХОСТЕ:**

```bash
# HOST пингует ваш Worker
ping 100.64.0.2

# HOST тестирует порт
nc -zv 100.64.0.2 9501
# или на Windows:
Test-NetConnection -ComputerName 100.64.0.2 -Port 9501

# HOST проверяет health
python -m workers health
# Должен показать вас как HEALTHY
```

---

## Шаг 6: Мониторинг Worker'а

### Логи Worker'а

```bash
# Смотрите логи в реальном времени
tail -f logs/generator.log

# Только ошибки
tail -f logs/generator.log | grep ERROR

# На Windows:
Get-Content logs/generator.log -Wait
```

### Проверка нагрузки

```bash
# Посмотрите загрузку CPU и RAM
top -p $(pgrep -f "workers start")  # Linux/macOS
# или
tasklist | findstr python           # Windows
```

### Проверка запросов от HOST

```bash
# Посмотрите входящие соединения
netstat -an | grep 9501      # Linux
# или
netstat -ano | findstr 9501  # Windows
# или
ss -tlnp | grep 9501         # Linux (новый)
```

### Если Worker завис

```bash
# Остановите worker
pkill -f "workers start"

# Или найдите PID и убейте вручную
ps aux | grep "workers start"
kill -9 <PID>

# Перезапустите
python -m workers start --name writer_1 --host 0.0.0.0 --port 9501
```

---

## Команды для быстрого старта

### Быстрая проверка (перед запуском)

```bash
# 1. Проверьте Tailscale
sudo tailscale status
ping 100.64.0.1  # Пингуйте HOST (спросите IP)

# 2. Проверьте доступ к HOST backend
curl http://100.64.0.1:11434/api/tags  # Ollama на HOST
curl http://100.64.0.1:8000/health     # llama.cpp на HOST

# 3. Активируйте окружение
source venv/bin/activate

# 4. Запустите Worker
python -m workers start --name writer_1 --host 0.0.0.0 --port 9501 --host-backend-url http://100.64.0.1:11434

# Output должен показать:
# INFO: Initialized LLMWorkerServer: writer_1 at 0.0.0.0:9501
# INFO: Will route requests to HOST backend: http://100.64.0.1:11434
# INFO: Worker server listening on 0.0.0.0:9501
```

### Распределённая система (несколько машин)

```bash
# На каждой WORKER машине:

# Терминал 1: Writer Worker
source venv/bin/activate
python -m workers start --name writer_remote_1 --host 0.0.0.0 --port 9501 --host-backend-url http://100.64.0.1:11434

# Терминал 2: Critic Worker (на другой машине или в другом терминале)
python -m workers start --name critic_remote_1 --host 0.0.0.0 --port 9502 --host-backend-url http://100.64.0.1:11434

# На HOST машине:
# - HOST_BACKEND_URL указывает на локальный backend (127.0.0.1:11434)
# - config.py содержит IP рабочих машин
# python main.py task.json
```

---

## Troubleshooting

### Tailscale не подключается

```bash
# Проверьте демон
sudo systemctl status tailscaled

# Перезапустите
sudo systemctl restart tailscaled

# Подключитесь заново
sudo tailscale up

# Проверьте статус
sudo tailscale status
```

### Не видно HOST машины

```bash
# Убедитесь что вы залогинены в ОДИНАКОВЫЙ Tailscale аккаунт
sudo tailscale status

# Пингуйте HOST (спросите IP)
ping 100.64.0.1

# Если не пингует - HOST может быть offline
# Свяжитесь с администратором
```

### Backend не доступен (HOST backend)

```bash
# Проверьте HOST backend URL
# Олламa на HOST:
ping 100.64.0.1
curl http://100.64.0.1:11434/api/tags

# llama.cpp на HOST:
curl http://100.64.0.1:8000/health

# Если не доступен - обновите HOST_BACKEND_URL в config.py
# Убедитесь что HOST машина включена и backend запущен
# Свяжитесь с администратором HOST
```

### Worker не подключается к HOST backend

```bash
# Проверьте Tailscale
sudo tailscale status

# Пингуйте HOST
ping 100.64.0.1

# Проверьте HOST_BACKEND_URL в config.py
cat config.py | grep HOST_BACKEND_URL

# Проверьте параметры запуска worker'а
python -m workers start --name test --host 0.0.0.0 --port 9999 --host-backend-url http://100.64.0.1:11434
```

### Out of Memory (OOM)

```bash
# Уменьшите размер контекста (llama.cpp)
./llama.cpp/server -c 1024 -m ~/models/qwen-course.gguf

# Используйте меньшую модель
ollama pull mistral  # 7B, меньше памяти
ollama pull phi      # 3B, минимум памяти

# Мониторьте память
watch -n 1 free -h  # Linux
tasklist            # Windows
```

### Потеря подключения к HOST

```bash
# Проверьте Tailscale
sudo tailscale status

# Пингуйте HOST
ping 100.64.0.1

# Если нет ответа - reconnect
sudo tailscale down
sudo tailscale up

# Worker продолжит слушать, HOST переподключится автоматически
```

---

## Автозапуск Worker'а на Boot (Systemd)

Чтобы Worker запускался автоматически при перезагрузке:

### Создайте service файл

```bash
# Отредактируйте с вашими путями
sudo nano /etc/systemd/system/course-worker.service
```

```ini
[Unit]
Description=Course Generator Worker
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
Type=simple
User=ubuntu  # ИЛИ ваше имя пользователя
WorkingDirectory=/home/ubuntu/kursovae  # ИЛИ ваша директория
ExecStart=/usr/bin/python3 -m workers start --name writer_1 --host 0.0.0.0 --port 9501
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Включите и запустите

```bash
# Перезагрузите systemd
sudo systemctl daemon-reload

# Включите автозапуск
sudo systemctl enable course-worker.service

# Запустите сейчас
sudo systemctl start course-worker.service

# Проверьте статус
sudo systemctl status course-worker.service

# Смотрите логи
sudo journalctl -u course-worker.service -f
```

---

## Оптимизация производительности

### Для CPU-only машин

```bash
# llama.cpp: Увеличьте потоки
./llama.cpp/server -t 16 -m ~/models/qwen-course.gguf
# t = количество ваших CPU ядер × 2
```

### Для GPU машин

```bash
# llama.cpp: Загрузьте все на GPU
./llama.cpp/server -ngl 999 -m ~/models/qwen-course.gguf

# Если несколько GPU
./llama.cpp/server -ngl 999 -mg 0,1 -m ~/models/qwen-course.gguf
```

### Для маломощных машин (4GB RAM)

```bash
# Используйте малые модели (3B)
ollama pull phi  # 3B model

# Или используйте меньший контекст
./llama.cpp/server -c 512 -m ~/models/phi.gguf
```

---

## Безопасность

### Firewall (если использует не Tailscale)

```bash
# Разрешьте только Tailscale интерфейс
sudo ufw default deny incoming
sudo ufw allow 9501/tcp  # Worker port
sudo ufw allow 9502/tcp  # Other workers
sudo ufw enable
```

### Tailscale Security

```bash
# Посмотрите кто подключен к вашей машине
sudo tailscale status

# Если компроментирована - отозвите доступ
sudo tailscale logout

# Или через веб: https://login.tailscale.com/admin/machines
```

---

## Контакты & Поддержка

Если что-то не работает:

1. **Проверьте логи:** `tail -f logs/generator.log`
2. **Проверьте дебаг информацию:** `sudo tailscale status`
3. **Свяжитесь с администратором HOST** и сообщите:
   - Ваша Tailscale IP
   - Имя Worker'а
   - Какая ошибка в логах
   - Какой Backend используется

---

## Схема подключения Worker → HOST

```
┌─────────────────────────────────────┐
│ WORKER MACHINE (100.64.0.2)         │
├─────────────────────────────────────┤
│                                     │
│ ✓ Python venv                       │
│                                     │
│ ✓ Worker processes                  │
│   (ports 9501, 9502...)             │
│   Слушает на 0.0.0.0                │
│                                     │
│ ✗ БЕЗ Ollama/llama.cpp (модели на  │
│   HOST!)                            │
│                                     │
└─────────────────────────────────────┘
    Tailscale VPN (HTTP запросы)
    (безопасный туннель)
           ↓
┌─────────────────────────────────────┐
│ HOST MACHINE (100.64.0.1)           │
├─────────────────────────────────────┤
│                                     │
│ ✓ Ollama/llama.cpp (порт 11434/8000)
│   (модели только здесь!)           │
│                                     │
│ ✓ Coordinator                       │
│                                     │
│ ✓ main.py генератор                │
│   Подключается к:                  │
│   100.64.0.2:9501 (writer_1)       │
│   100.64.0.2:9502 (critic_1)       │
│                                     │
│ WORKER'ы обращаются к HOST backend: │
│   http://100.64.0.1:11434           │
│   http://100.64.0.1:8000            │
│                                     │
└─────────────────────────────────────┘
```

---

## Финальная проверка

```bash
# 1. Tailscale подключен
sudo tailscale status

# 2. HOST backend доступен (с WORKER машины)
curl http://100.64.0.1:11434/api/tags   # Ollama
curl http://100.64.0.1:8000/health      # llama.cpp

# 3. Worker запущен и подключен к HOST backend
ps aux | grep "workers start"

# 4. HOST может пингнуть worker (с HOST машины)
ping 100.64.0.2

# ✅ Готово к работе!
# Workers готовы получать запросы от HOST
```

---

**Дальше:** Отправьте свои IP и порты администратору HOST. Он обновит config.py и запустит генерацию.
