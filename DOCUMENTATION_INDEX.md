# 📖 DOCUMENTATION INDEX

Полный индекс документации Course Generator v5.5.

---

## 🚀 Быстрый Старт

### Для нетерпеливых:
- **[QUICKSTART.md](QUICKSTART.md)** — 5-минутная установка (выбери один вариант ниже)

---

## 📚 Основные Руководства

### ДЛЯ ГЛАВНОЙ МАШИНЫ (HOST):
| Документ | Содержание | Время |
|----------|-----------|-------|
| **[HOST_SETUP.md](HOST_SETUP.md)** | Полное руководство для HOST: Tailscale, LLM Backend, конфигурация воркеров | 30-45 мин |
| [LLAMACPP_SETUP.md](LLAMACPP_SETUP.md) | Установка и настройка llama.cpp для быстрого inference | 15-20 мин |
| [TAILSCALE_WORKERS.md](TAILSCALE_WORKERS.md) | Детальное руководство по Tailscale VPN интеграции | 20-30 мин |

### ДЛЯ РАБОЧИХ МАШИН (WORKERS):
| Документ | Содержание | Время |
|----------|-----------|-------|
| **[WORKER_SETUP.md](WORKER_SETUP.md)** | Полное руководство для Worker: Tailscale, Backend, запуск worker'а | 30-45 мин |

### КОМПЛЕКСНЫЕ РУКОВОДСТВА:
| Документ | Содержание | Время |
|----------|-----------|-------|
| [COMPLETE_DEPLOYMENT.md](COMPLETE_DEPLOYMENT.md) | Полный цикл развёртывания с примерами | 45-60 мин |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Архитектура системы и миграция Ollama→llama.cpp | 30-40 мин |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | Итоговое резюме всей реализации (6 фаз) | 10-15 мин |

---

## 🎯 Сценарии Использования

### Сценарий 1: Один компьютер (тестирование)

**Шаги:**
1. Прочтите: [QUICKSTART.md](QUICKSTART.md)
2. Прочтите: [HOST_SETUP.md](HOST_SETUP.md) (пропустите Tailscale шаг 1)
3. Запустите локальные worker'ы (раздел "Локально" в [WORKER_SETUP.md](WORKER_SETUP.md))

**Время:** 20-30 минут

---

### Сценарий 2: Несколько машин (распределённая система)

**HOST машина:**
1. [HOST_SETUP.md](HOST_SETUP.md) — полное чтение
2. [TAILSCALE_WORKERS.md](TAILSCALE_WORKERS.md) — шаг 1-2 (Tailscale для HOST)

**WORKER машины (каждая):**
1. [WORKER_SETUP.md](WORKER_SETUP.md) — полное чтение
2. [TAILSCALE_WORKERS.md](TAILSCALE_WORKERS.md) — шаг 1-2 (Tailscale для WORKER)

**Интеграция:**
1. Каждый worker сообщает свой IP и порты HOST'у
2. HOST обновляет config.py с IP worker'ов
3. Запустить генерацию на HOST

**Время:** 1.5-2 часа для 3-х машин

---

### Сценарий 3: Миграция Ollama → llama.cpp

**На HOST:**
1. [LLAMACPP_SETUP.md](LLAMACPP_SETUP.md) — установка и запуск
2. Обновить config.py: `LLM_BACKEND_TYPE = "llamacpp"`
3. Перезапустить генерацию

**Ожидаемо:** 20-30% ускорение без других изменений!

---

## 🔧 Справочник Команд

### На HOST машине

```bash
# Проверка воркеров
python -m workers list
python -m workers health
python -m workers config
python -m workers discover  # Tailscale auto-discovery

# Запуск генерации
python main.py task.json
python main.py task.json --resume session_ID
python main.py --list-sessions

# Мониторинг
tail -f logs/generator.log
```

### На WORKER машине

```bash
# Запуск worker'а
python -m workers start --name writer_1 --host 0.0.0.0 --port 9501

# Проверка
sudo tailscale status
curl http://0.0.0.0:11434/api/tags  # Хоска backend
```

### Tailscale команды

```bash
# На любой машине
sudo tailscale up          # Подключение
sudo tailscale status      # Статус
sudo tailscale ip -4       # Получить свой IP
sudo tailscale logout      # Отключение
```

---

## 📋 Checklist для развёртывания

### HOST Setup
- [ ] Tailscale установлен и подключен
- [ ] LLM Backend (Ollama или llama.cpp) запущен
- [ ] Python dependencies установлены
- [ ] config.py обновлён с backend типом
- [ ] Проверено: `python -m workers config`

### WORKER Setup (для каждого worker'а)
- [ ] Tailscale установлен и подключен к ОДИНАКОВОМУ аккаунту
- [ ] Ping до HOST работает
- [ ] LLM Backend запущен
- [ ] Python dependencies установлены
- [ ] Worker successfully starts: `python -m workers start ...`

### Интеграция
- [ ] HOST может ping все worker'ы
- [ ] config.py на HOST содержит все worker IP's
- [ ] `python -m workers health` показывает все HEALTHY
- [ ] Пробный запуск: `python main.py --validate-only`
- [ ] Полная генерация: `python main.py task.json`

---

## 🆘 Troubleshooting Quick Links

| Проблема | Решение |
|----------|---------|
| Tailscale не подключается | [HOST_SETUP.md #Troubleshooting](HOST_SETUP.md#troubleshooting) |
| Backend недоступен | [WORKER_SETUP.md #Backend не запускается](WORKER_SETUP.md#backend-не-запускается) |
| Worker не видит HOST | [TAILSCALE_WORKERS.md #Troubleshooting](TAILSCALE_WORKERS.md#troubleshooting-connection-issues) |
| Out of Memory | [HOST_SETUP.md #OOM](HOST_SETUP.md#out-of-memory-oom) |
| Slow Generation | [ARCHITECTURE.md #Performance](ARCHITECTURE.md#-performance-benchmarks) |

---

## 📊 Документация по Технологиям

### LLM Backend:
- **Ollama:** [HOST_SETUP.md #Вариант A](HOST_SETUP.md#вариант-a-ollama-простенький-для-тестирования) + [QUICKSTART.md](QUICKSTART.md)
- **llama.cpp:** [HOST_SETUP.md #Вариант B](HOST_SETUP.md#вариант-b-llamacpp-быстрее-рекомендуется) + [LLAMACPP_SETUP.md](LLAMACPP_SETUP.md)

### Worker System:
- **Архитектура:** [ARCHITECTURE.md #Worker Distribution](ARCHITECTURE.md)
- **Desarrollo:** [WORKER_SETUP.md](WORKER_SETUP.md)
- **Управление:** [WORKER_DEPLOYMENT.md](WORKER_DEPLOYMENT.md)

### Networking:
- **Tailscale Setup:** [TAILSCALE_WORKERS.md](TAILSCALE_WORKERS.md)
- **Security:** [TAILSCALE_WORKERS.md #Security](TAILSCALE_WORKERS.md#security-best-practices)

---

## 📈 Производительность

### Базовые цифры

| Сценарий | Время | Ускорение |
|----------|-------|----------|
| Sequential (Ollama, 1 PC) | 3-4h | 1× |
| Parallel (Ollama, 2 chapters) | 1.5-2h | 2× |
| llama.cpp (1 PC) | 2-2.5h | 1.5× |
| llama.cpp + Parallel | 1-1.5h | 3× |
| Distributed (3 PCs) | 45-60min | 3-4× |
| **Optimal** (3 PCs + llama.cpp) | **30-45min** | **4-5×** |

### Оптимизация:
1. Используйте **llama.cpp** вместо Ollama (+20-30%)
2. Включите **章 Parallelism** (+100%)
3. Добавьте **Worker'ов** (+100-200%)

---

## 🎓 Для Разработчиков

### Архитектурные решения:
- [ARCHITECTURE.md #Architecture Overview](ARCHITECTURE.md)
- [IMPLEMENTATION_SUMMARY.md #Summary of Changes](IMPLEMENTATION_SUMMARY.md)

### Расширение функциональности:
- Добавить новый LLM backend: [ARCHITECTURE.md #Add New Backend](ARCHITECTURE.md)
- Расширить валидацию: [ARCHITECTURE.md #Extend Validation](ARCHITECTURE.md)
- Кастомизировать worker: [WORKER_DEPLOYMENT.md](WORKER_DEPLOYMENT.md)

---

## 📞 Получение Помощи

### Проверить логи:
```bash
tail -f logs/generator.log
```

### Диагностика:
```bash
python -m workers health          # Статус worker'ов
sudo tailscale status            # Статус Tailscale
python -m workers discover       # Auto-discovery
```

### Документация по компоненту:
- **LLM:** Читай [LLAMACPP_SETUP.md](LLAMACPP_SETUP.md)
- **Workers:** Читай [WORKER_SETUP.md](WORKER_SETUP.md)
- **Tailscale:** Читай [TAILSCALE_WORKERS.md](TAILSCALE_WORKERS.md)
- **Весь стек:** Читай [COMPLETE_DEPLOYMENT.md](COMPLETE_DEPLOYMENT.md)

---

## 🌐 Структура документации

```
├── QUICKSTART.md                ← НАЧНИ ОТСЮДА (5 мин)
├── HOST_SETUP.md                ← Для главной машины (30-45 мин)
├── WORKER_SETUP.md              ← Для рабочих машин (30-45 мин)
├── COMPLETE_DEPLOYMENT.md       ← Полный цикл (45-60 мин)
│
├── LLAMACPP_SETUP.md            ← Детали llama.cpp
├── TAILSCALE_WORKERS.md         ← Детали Tailscale VPN
├── WORKER_DEPLOYMENT.md         ← Детали worker'ов
│
├── ARCHITECTURE.md              ← Система & дизайн
├── IMPLEMENTATION_SUMMARY.md    ← Итоги реализации
│
└── README.md                    ← Обзор проекта
```

---

## ✅ Статус Реализации

### Фазы 1-6: ЗАВЕРШЕНЫ ✅

- ✅ Phase 1: Backend Abstraction
- ✅ Phase 2: llama.cpp Support
- ✅ Phase 3: Worker Distribution
- ✅ Phase 4: Chapter Parallelism
- ✅ Phase 5 & 6: Documentation & Tailscale Integration

**Полная реализация готова к production развёртыванию!**

---

## 🎯 Рекомендуемый путь обучения

### День 1: Базовое понимание
1. Прочтите [README.md](README.md) (5 мин)
2. Прочтите [QUICKSTART.md](QUICKSTART.md) (5 мин)
3. Прочтите [ARCHITECTURE.md](ARCHITECTURE.md) (30 мин)

### День 2: Практическое применение
1. Выполните HOST Setup ([HOST_SETUP.md](HOST_SETUP.md)) (45 мин)
2. Запустите локально одну машину (15 мин)
3. Проверьте генерацию (15 мин)

### День 3: Масштабирование
1. Подготовьте Worker машину ([WORKER_SETUP.md](WORKER_SETUP.md)) (45 мин)
2. Подключите через Tailscale ([TAILSCALE_WORKERS.md](TAILSCALE_WORKERS.md)) (30 мин)
3. Запустите распределённую генерацию (15 мин)

**Итого:** 3 дня для полного deployment

---

## 💡 Советы

| Совет | Действие |
|-------|---------|
| Первый раз? | Начните с [QUICKSTART.md](QUICKSTART.md) |
| Локальное тестирование? | Используйте один компьютер ([HOST_SETUP.md](HOST_SETUP.md)) |
| Production система? | Используйте распределённую архитектуру ([COMPLETE_DEPLOYMENT.md](COMPLETE_DEPLOYMENT.md)) |
| Нужна скорость? | Используйте llama.cpp ([LLAMACPP_SETUP.md](LLAMACPP_SETUP.md)) |
| Проблемы? | Проверьте [Troubleshooting](#-troubleshooting-quick-links) |

---

**Последнее обновление:** 2026-04-08
**Версия:** v5.5 (Final Release)
**Статус:** ✅ Production Ready
