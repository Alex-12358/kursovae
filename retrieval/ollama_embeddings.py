"""
Ollama Embeddings Engine - использует nomic-embed-text через Ollama
С кэшированием, параллельной обработкой и прогресс-баром
"""
import logging
import hashlib
import json
import numpy as np
import requests
from pathlib import Path
from typing import List, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Глобальный кэш для embeddings (в памяти)
_embeddings_cache: Dict[str, List[float]] = {}


class OllamaEmbeddings:
    """Embeddings через Ollama API (nomic-embed-text) с кэшированием"""
    
    def __init__(self, model_name: str = "nomic-embed-text", base_url: str = "http://localhost:11434",
                 cache_dir: Optional[Path] = None):
        """
        Args:
            model_name: Название модели в Ollama (nomic-embed-text)
            base_url: URL Ollama API
            cache_dir: Директория для кэша (опционально)
        """
        self.model_name = model_name
        self.base_url = base_url
        self.api_url = f"{base_url}/api/embeddings"
        self.cache_dir = cache_dir
        self._cache_loaded = False
        
        # Загружаем кэш с диска если указана директория
        if cache_dir:
            self._load_cache()
        
        logger.info(f"OllamaEmbeddings инициализирован: model={model_name}")
    
    def _get_text_hash(self, text: str) -> str:
        """Возвращает хэш текста для кэширования"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()[:16]
    
    def _load_cache(self):
        """Загружает кэш embeddings с диска"""
        global _embeddings_cache
        if self.cache_dir and not self._cache_loaded:
            cache_file = self.cache_dir / "embeddings_cache.json"
            if cache_file.exists():
                try:
                    with open(cache_file, 'r') as f:
                        _embeddings_cache = json.load(f)
                    logger.info(f"Загружен кэш: {len(_embeddings_cache)} embeddings")
                except Exception as e:
                    logger.warning(f"Ошибка загрузки кэша: {e}")
            self._cache_loaded = True
    
    def _save_cache(self):
        """Сохраняет кэш embeddings на диск"""
        global _embeddings_cache
        if self.cache_dir and _embeddings_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = self.cache_dir / "embeddings_cache.json"
            try:
                with open(cache_file, 'w') as f:
                    json.dump(_embeddings_cache, f)
                logger.info(f"Кэш сохранён: {len(_embeddings_cache)} embeddings")
            except Exception as e:
                logger.warning(f"Ошибка сохранения кэша: {e}")
    
    def encode(self, texts: List[str], batch_size: int = 64, show_progress_bar: bool = True, 
               max_workers: int = 8) -> np.ndarray:
        """
        Создаёт embeddings для списка текстов с параллельным батчингом и кэшированием
        
        Args:
            texts: Список текстов
            batch_size: Размер батча (по умолчанию 64)
            show_progress_bar: Показывать прогресс
            max_workers: Количество параллельных потоков (по умолчанию 8)
        
        Returns:
            numpy array с embeddings
        """
        global _embeddings_cache
        
        if not texts:
            return np.array([])
        
        # Проверяем кэш
        embeddings = [None] * len(texts)
        texts_to_compute = []  # (index, text)
        cache_hits = 0
        
        for i, text in enumerate(texts):
            text_hash = self._get_text_hash(text)
            if text_hash in _embeddings_cache:
                embeddings[i] = _embeddings_cache[text_hash]
                cache_hits += 1
            else:
                texts_to_compute.append((i, text))
        
        if cache_hits > 0:
            logger.info(f"Кэш: {cache_hits}/{len(texts)} embeddings уже вычислены")
        
        if not texts_to_compute:
            logger.info("✅ Все embeddings взяты из кэша")
            return np.array(embeddings, dtype=np.float32)
        
        logger.info(f"Вычисление {len(texts_to_compute)} embeddings через Ollama")
        logger.info(f"  Батчи: {batch_size} текстов, параллельность: {max_workers} потоков")
        
        total_batches = (len(texts_to_compute) + batch_size - 1) // batch_size
        
        # Обрабатываем батчами
        for batch_start in range(0, len(texts_to_compute), batch_size):
            batch = texts_to_compute[batch_start:batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            
            if show_progress_bar:
                progress = batch_start + len(batch)
                logger.info(f"  Батч {batch_num}/{total_batches} ({progress}/{len(texts_to_compute)})")
            
            # Параллельная обработка текстов в батче
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_info = {}
                for idx, text in batch:
                    future = executor.submit(self._get_embedding, text)
                    future_to_info[future] = (idx, text)
                
                for future in as_completed(future_to_info):
                    idx, text = future_to_info[future]
                    try:
                        embedding = future.result()
                        embeddings[idx] = embedding
                        # Сохраняем в кэш
                        text_hash = self._get_text_hash(text)
                        _embeddings_cache[text_hash] = embedding
                    except Exception as e:
                        logger.error(f"Ошибка embedding для текста {idx}: {e}")
                        embeddings[idx] = [0.0] * 768
        
        # Сохраняем кэш на диск
        self._save_cache()
        
        logger.info(f"✅ Создано {len(texts_to_compute)} новых + {cache_hits} из кэша = {len(embeddings)} embeddings")
        
        return np.array(embeddings, dtype=np.float32)
    
    def _get_embedding(self, text: str) -> List[float]:
        """Получает embedding для одного текста (для параллельного выполнения)"""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model_name,
                    "prompt": text
                },
                timeout=60  # Увеличен таймаут для стабильности
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("embedding", [0.0] * 768)
            else:
                logger.error(f"Ошибка Ollama API: {response.status_code}")
                return [0.0] * 768
        
        except Exception as e:
            logger.error(f"Ошибка запроса к Ollama: {e}")
            return [0.0] * 768
    
    def get_sentence_embedding_dimension(self) -> int:
        """Возвращает размерность embeddings"""
        return 768  # nomic-embed-text


def create_embeddings_engine(use_ollama: bool = True, cache_dir: Optional[Path] = None):
    """
    Фабрика для создания embeddings engine
    
    Args:
        use_ollama: Использовать Ollama (True) или sentence-transformers (False)
        cache_dir: Директория для кэша embeddings
    
    Returns:
        EmbeddingsEngine или OllamaEmbeddings
    """
    if use_ollama:
        logger.info("Используется Ollama embeddings (nomic-embed-text)")
        # Используем стандартную директорию для кэша
        if cache_dir is None:
            from config import STORAGE_DIR
            cache_dir = STORAGE_DIR / "embeddings"
        return OllamaEmbeddings(cache_dir=cache_dir)
    else:
        from retrieval.embeddings_engine import EmbeddingsEngine
        from config import EMBEDDING_MODEL
        logger.info(f"Используется sentence-transformers ({EMBEDDING_MODEL})")
        return EmbeddingsEngine(model_name=EMBEDDING_MODEL)
