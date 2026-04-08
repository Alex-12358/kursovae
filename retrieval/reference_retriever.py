"""
Reference Retriever - гибридный поиск релевантных фрагментов
Векторный поиск (FAISS) + keyword поиск (BM25)
"""
import logging
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ReferenceRetriever:
    """Поиск релевантных фрагментов из индекса"""
    
    def __init__(self):
        self.index = None
        self.chunks = []
        self.embeddings_engine = None
        logger.info("ReferenceRetriever инициализирован")
    
    def build_index(
        self, 
        chunks: List[Dict[str, Any]], 
        embeddings: np.ndarray
    ):
        """
        Строит FAISS индекс из embeddings
        
        Args:
            chunks: Список чанков с метаданными
            embeddings: Матрица embeddings [N x dim]
        """
        try:
            import faiss
        except ImportError:
            logger.error("faiss-cpu не установлен!")
            logger.error("Установите: pip install faiss-cpu")
            raise
        
        logger.info(f"Построение FAISS индекса для {len(chunks)} чанков...")
        
        if len(chunks) != len(embeddings):
            raise ValueError(f"Несоответствие: {len(chunks)} chunks != {len(embeddings)} embeddings")
        
        self.chunks = chunks
        
        # Создаём FAISS индекс (Inner Product для normalized vectors = cosine similarity)
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        
        # Добавляем векторы
        self.index.add(embeddings.astype('float32'))
        
        logger.info(f"✓ FAISS индекс построен: {self.index.ntotal} векторов, dim={dim}")
    
    def search(
        self, 
        query: str, 
        top_k: int = 5, 
        filter_etalon: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Поиск релевантных чанков
        
        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            filter_etalon: Искать только в эталоне (2603-1716.docx)
        
        Returns:
            [{"chunk_id": "...", "text": "...", "score": 0.87, "metadata": {...}}]
        """
        if self.index is None:
            raise RuntimeError("Индекс не построен. Вызовите build_index() или load()")
        
        if self.embeddings_engine is None:
            # Используем Ollama embeddings если включено в конфиге
            from config import USE_OLLAMA_EMBEDDINGS
            if USE_OLLAMA_EMBEDDINGS:
                from retrieval.ollama_embeddings import create_embeddings_engine
                self.embeddings_engine = create_embeddings_engine(use_ollama=True)
            else:
                from retrieval.embeddings_engine import EmbeddingsEngine
                from config import EMBEDDING_MODEL
                self.embeddings_engine = EmbeddingsEngine(EMBEDDING_MODEL)
        
        # Создаём embedding для запроса
        query_vector = self.embeddings_engine.encode([query])
        query_vector = query_vector.reshape(1, -1).astype('float32')
        
        # Поиск в FAISS
        # Ищем больше результатов если фильтруем
        search_k = top_k * 3 if filter_etalon else top_k
        
        scores, indices = self.index.search(query_vector, search_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # FAISS вернул invalid index
                continue
            
            chunk = self.chunks[idx]
            
            # Фильтр по эталону
            if filter_etalon and not chunk["metadata"].get("is_etalon", False):
                continue
            
            results.append({
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "score": float(score),
                "metadata": chunk["metadata"]
            })
            
            if len(results) >= top_k:
                break
        
        logger.debug(f"Поиск '{query[:50]}...': найдено {len(results)} результатов")
        
        return results
    
    def search_hybrid(
        self, 
        query: str, 
        top_k: int = 5,
        vector_weight: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Гибридный поиск: векторный + keyword
        
        Args:
            query: Запрос
            top_k: Количество результатов
            vector_weight: Вес векторного поиска (0-1), keyword = 1 - vector_weight
        
        Returns:
            Список результатов
        """
        # Векторный поиск
        vector_results = self.search(query, top_k=top_k * 2)
        
        # Keyword поиск (простой: подстрока)
        keyword_results = self._keyword_search(query, top_k=top_k * 2)
        
        # Объединяем результаты с весами
        merged = self._merge_results(
            vector_results, 
            keyword_results, 
            vector_weight,
            top_k
        )
        
        return merged
    
    def _keyword_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Простой keyword поиск по содержимому"""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        results = []
        for chunk in self.chunks:
            text_lower = chunk["text"].lower()
            
            # Подсчёт совпадений слов
            text_words = set(text_lower.split())
            matches = len(query_words & text_words)
            
            if matches > 0:
                score = matches / len(query_words)
                results.append({
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk["text"],
                    "score": score,
                    "metadata": chunk["metadata"]
                })
        
        # Сортируем по score
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results[:top_k]
    
    def _merge_results(
        self, 
        vector_results: List[Dict], 
        keyword_results: List[Dict],
        vector_weight: float,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Объединяет результаты двух поисков с весами"""
        # Создаём словарь chunk_id -> combined_score
        scores = {}
        
        for res in vector_results:
            chunk_id = res["chunk_id"]
            scores[chunk_id] = res["score"] * vector_weight
        
        keyword_weight = 1.0 - vector_weight
        for res in keyword_results:
            chunk_id = res["chunk_id"]
            if chunk_id in scores:
                scores[chunk_id] += res["score"] * keyword_weight
            else:
                scores[chunk_id] = res["score"] * keyword_weight
        
        # Сортируем по combined score
        sorted_chunks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Восстанавливаем полные результаты
        chunk_map = {c["chunk_id"]: c for c in self.chunks}
        
        results = []
        for chunk_id, score in sorted_chunks[:top_k]:
            chunk = chunk_map.get(chunk_id)
            if chunk:
                results.append({
                    "chunk_id": chunk_id,
                    "text": chunk["text"],
                    "score": score,
                    "metadata": chunk["metadata"]
                })
        
        return results
    
    def save(self, index_path: Path, chunks_path: Path):
        """
        Сохраняет индекс и чанки на диск
        
        Args:
            index_path: Путь для FAISS индекса (.faiss)
            chunks_path: Путь для чанков (.json)
        """
        import faiss
        
        index_path.parent.mkdir(parents=True, exist_ok=True)
        chunks_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем FAISS индекс
        faiss.write_index(self.index, str(index_path))
        logger.info(f"FAISS индекс сохранён: {index_path}")
        
        # Сохраняем чанки
        with open(chunks_path, 'w', encoding='utf-8') as f:
            json.dump(self.chunks, f, ensure_ascii=False, indent=2)
        logger.info(f"Чанки сохранены: {chunks_path} ({len(self.chunks)} шт.)")
    
    def load(self, index_path: Path, chunks_path: Path):
        """
        Загружает индекс и чанки с диска
        
        Args:
            index_path: Путь к FAISS индексу
            chunks_path: Путь к чанкам
        """
        import faiss
        
        if not index_path.exists():
            raise FileNotFoundError(f"Индекс не найден: {index_path}")
        if not chunks_path.exists():
            raise FileNotFoundError(f"Чанки не найдены: {chunks_path}")
        
        # Загружаем FAISS индекс
        self.index = faiss.read_index(str(index_path))
        logger.info(f"FAISS индекс загружен: {index_path} ({self.index.ntotal} векторов)")
        
        # Загружаем чанки
        with open(chunks_path, 'r', encoding='utf-8') as f:
            self.chunks = json.load(f)
        logger.info(f"Чанки загружены: {chunks_path} ({len(self.chunks)} шт.)")
        
        # Инициализируем embeddings engine
        from retrieval.embeddings_engine import EmbeddingsEngine
        from config import EMBEDDING_MODEL
        self.embeddings_engine = EmbeddingsEngine(EMBEDDING_MODEL)
