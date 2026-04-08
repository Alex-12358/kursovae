# Smart Critic v6 — Установка и запуск

## 🔧 Установка зависимостей

```bash
pip install -r requirements.txt
```

**Что установится:**
- `sentence-transformers` — embeddings модель (~500 MB)
- `faiss-cpu` — векторный поиск (~50 MB)
- `PyPDF2` — парсинг PDF
- При первом запуске скачается модель `BAAI/bge-m3` (~2 GB)

---

## 🧪 Тест индексации

Перед полным запуском рекомендуется протестировать индексацию:

```bash
python test_indexing.py
```

**Что проверяется:**
1. Парсинг всех файлов из `data/sources/`
2. Разбиение на чанки
3. Создание embeddings
4. Построение FAISS индекса
5. Тестовый поиск

**Ожидаемое время:** 2-5 минут (при первом запуске — скачивание модели)

---

## 🚀 Полный запуск

### Новая сессия (с индексацией):

```bash
python main.py data/input/task.json
```

**Этапы:**
1. CHUNK — парсинг sources (5-10 сек)
2. EMBED — создание embeddings (2-5 мин при первом запуске)
3. INDEX — построение FAISS (5 сек)
4. LLM_PLANNING — планирование структуры (3 мин)
5. TEXT_ENGINE — генерация текста с style examples (6-8 часов)
6. SMART_CRITIC — глубокий анализ (15-30 мин)
7. Финальная сборка DOCX

### Продолжение сессии:

```bash
python main.py data/input/task.json --resume session_YYYYMMDD_HHMMSS
```

**Checkpoint system:**
- Сохраняет результат каждого узла
- Если индекс уже построен — пропускает CHUNK/EMBED/INDEX
- Если TEXT_ENGINE завершён — переходит сразу к SMART_CRITIC

---

## 📊 Результаты

### 1. Итоговый документ:
```
output/coursework.docx
```

### 2. Отчёт Smart Critic:
```
logs/smart_critic_report.json
```

**Содержит:**
- `overall_score` — общая оценка (0-1)
- `section_scores` — оценки по разделам
- `weak_sections` — разделы требующие доработки
- `verdict` — итоговый вердикт
- `summary` — текстовое резюме
- `detailed_results` — подробные результаты по каждому разделу

---

## 🔍 Просмотр отчёта

```bash
# Windows
type logs\smart_critic_report.json

# Или в Python
python -c "import json; print(json.dumps(json.load(open('logs/smart_critic_report.json', encoding='utf-8')), indent=2, ensure_ascii=False))"
```

---

## ⚡ Переиндексация

Если добавили новые файлы в `data/sources/`:

```bash
# Удалить старые checkpoints индексации
rmdir /s /q storage\checkpoints\{session_id}\CHUNK.json
rmdir /s /q storage\checkpoints\{session_id}\EMBED.json
rmdir /s /q storage\checkpoints\{session_id}\INDEX.json

# Или просто запустить новую сессию
python main.py data/input/task.json
```

---

## 📝 Интерпретация Score

```
0.9+ → Почти как эталон 2603-1716, можно сдавать как есть
0.8-0.9 → Хорошая работа, минимальные правки
0.7-0.8 → Удовлетворительно, нужны улучшения
<0.7 → Слабо, требуется переработка
```

---

## 🐛 Возможные проблемы

### 1. `ModuleNotFoundError: No module named 'sentence_transformers'`
```bash
pip install sentence-transformers
```

### 2. `ModuleNotFoundError: No module named 'faiss'`
```bash
pip install faiss-cpu
```

### 3. `FileNotFoundError: Индекс не найден`
Запустите сначала индексацию:
```bash
python test_indexing.py
```

### 4. Долго грузится модель
При первом запуске модель `BAAI/bge-m3` (~2GB) скачивается из HuggingFace.
Это нормально, происходит один раз.

Альтернатива (быстрая модель):
В `config.py` замените:
```python
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # ~90MB, быстрее
```

---

## 📞 Поддержка

Если что-то не работает — проверьте:
1. Установлены ли все зависимости: `pip list | findstr "sentence faiss PyPDF"`
2. Есть ли файлы в `data/sources/` (особенно `2603-1716.docx`)
3. Запущен ли Ollama: `curl http://localhost:11434`
