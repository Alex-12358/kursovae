"""
Курсовой Генератор v5 - Конфигурация
Все константы, пути, параметры моделей и ГОСТ
"""
from pathlib import Path

# === ПУТИ ===
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SOURCES_DIR = DATA_DIR / "sources"
OUTPUT_DIR = BASE_DIR / "output"
STORAGE_DIR = BASE_DIR / "storage"
LOG_DIR = BASE_DIR / "logs"
GOST_TABLES_DIR = BASE_DIR / "calc" / "gost_tables"

# === EMBEDDINGS & RETRIEVAL ===
USE_OLLAMA_EMBEDDINGS = True  # True = Ollama (nomic-embed-text), False = sentence-transformers
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # Для sentence-transformers (если USE_OLLAMA_EMBEDDINGS=False)
EMBEDDING_DIM = 768  # nomic-embed-text: 768, bge-m3: 1024, MiniLM: 384
EMBEDDING_BATCH_SIZE = 64  # Размер батча для Ollama embeddings
EMBEDDING_MAX_WORKERS = 8  # Параллельные потоки для embeddings (увеличь до 16 если CPU мощный)
CHUNK_SIZE = 512  # символов на chunk
CHUNK_OVERLAP = 128  # overlap между chunks
FAISS_INDEX_PATH = STORAGE_DIR / "embeddings" / "index.faiss"
CHUNKS_DB_PATH = STORAGE_DIR / "embeddings" / "chunks.json"
EMBEDDINGS_CACHE_PATH = STORAGE_DIR / "embeddings" / "vectors.npy"

# === OCR ===
USE_OCR_FALLBACK = False  # ОТКЛЮЧЕНО - чертежи не содержат полезного текста для RAG
OCR_DPI = 200  # DPI для конвертации PDF в изображения
OCR_LANGUAGES = ['ru', 'en']  # Языки для EasyOCR
POPPLER_PATH = r"D:\Model\Release-25.12.0-0\poppler-25.12.0\Library\bin"  # Путь к Poppler для pdf2image

# Эталонный документ
ETALON_DOCX = "2603-1716.docx"

# === ЛОГИРОВАНИЕ ===
LOG_LEVEL = "INFO"

# === ГОСТ ПАРАМЕТРЫ ===
GOST_MARGIN_TOP = 20  # мм
GOST_MARGIN_BOTTOM = 20
GOST_MARGIN_LEFT = 30
GOST_MARGIN_RIGHT = 20  # ГОСТ 2.105
GOST_LINE_SPACING = 1.5
GOST_FONT_SIZE = 14
GOST_FONT_NAME = "Times New Roman"

# === LLM BACKEND SELECTION ===
LLM_BACKEND_TYPE = "ollama"  # "ollama" или "llamacpp"

# === OLLAMA НАСТРОЙКИ ===
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
OLLAMA_TIMEOUT = 300  # секунды
OLLAMA_RETRY_COUNT = 3
OLLAMA_RETRY_DELAY = 2  # секунды между попытками

# === LLAMA.CPP НАСТРОЙКИ ===
LLAMACPP_INSTANCES = [
    ("127.0.0.1", 8000),  # Primary instance
    # ("127.0.0.1", 8001),  # Additional instances for load balancing
]
LLAMACPP_TIMEOUT = 600  # секунды
LLAMACPP_RETRY_COUNT = 3
LLAMACPP_RETRY_DELAY = 2

# === MODEL ROUTING V1 (Writer/Compressor) ===
MODEL_ROUTING_V1 = {
    "model": "qwen-course",
    "temperature": 0.7,
    "top_p": 0.9,
    "max_tokens": 4096,
    "role": "writer"
}

# === MODEL ROUTING V2 (Planner/Critic) ===
MODEL_ROUTING_V2 = {
    "model": "deepseek-course",
    "temperature": 0.3,
    "top_p": 0.95,
    "max_tokens": 8192,
    "role": "planner_critic"
}

# === EMBEDDINGS ===
EMBEDDING_MODEL = "BAAI/bge-m3"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
EMBEDDING_BATCH_SIZE = 32
FAISS_INDEX_TYPE = "IVF100,Flat"

# === VECTOR DB ===
VECTOR_DB_PATH = DATA_DIR / "vector_db"
SQLITE_DB_PATH = DATA_DIR / "metadata.db"
BM25_INDEX_PATH = DATA_DIR / "bm25_index.pkl"

# === CALC ENGINE ===
CALC_PRECISION = 4  # знаков после запятой
MIN_SAFETY_FACTOR = 1.3  # минимальный запас прочности
MAX_ITERATIONS = 100  # для итеративных расчётов

# === TEXT ENGINE ===
MAX_CHAPTER_RETRIES = 3
CRITIC_THRESHOLD = 0.8  # порог для пропуска Smart Critic
MIN_CHAPTER_LENGTH = 500  # символов
MAX_CHAPTER_LENGTH = 8000

# === QUALITY GATE ===
GOST_LINTER_RULES = [
    "no_first_person",  # запрет "я", "мы"
    "passive_voice",  # требование страдательного залога
    "no_colloquial",  # запрет разговорных слов
    "formula_refs",  # проверка ссылок на формулы
    "figure_refs",  # проверка ссылок на рисунки
    "table_refs"  # проверка ссылок на таблицы
]

AUTOFIX_ENABLED = True
AUTOFIX_MAX_ATTEMPTS = 3

# === МАРКЕРЫ LLM ===
FORMULA_MARKER_OPEN = "[FORMULA]"
FORMULA_MARKER_CLOSE = "[/FORMULA]"
FIGURE_MARKER = "[FIGURE:"
FIGURE_MARKER_CLOSE = "]"
TABLE_MARKER = "[TABLE:"
TABLE_MARKER_CLOSE = "]"

# === WORKER ARCHITECTURE ===
WORKER_ENABLED = False  # Включить distributed worker system
WORKER_COORDINATOR_PORT = 9500
WORKERS = [
    # {"name": "writer_1", "host": "127.0.0.1", "port": 9501, "models": ["qwen-course"]},
    # {"name": "critic_1", "host": "127.0.0.1", "port": 9502, "models": ["deepseek-course"]},
    # {"name": "remote_worker", "host": "192.168.1.100", "port": 9503, "models": ["qwen-course", "deepseek-course"]},
]
WORKER_FALLBACK_TO_LOCAL = True  # Fallback to local backend if workers unavailable

# === CHAPTER PARALLELISM ===
MAX_CONCURRENT_CHAPTERS = 2  # Максимум параллельных глав одновременно
CHAPTER_VALIDATION_ENABLED = True  # Проверка глав сразу после генерации

# === LOGGING ===
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = BASE_DIR / "logs" / "generator.log"
