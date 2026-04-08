"""
Embeddings Engine - создание векторных представлений текста
Использует sentence-transformers (bge-m3 или MiniLM)
"""
import logging
import numpy as np
from typing import List, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class EmbeddingsEngine:
    """Движок для создания embeddings через sentence-transformers"""
    
    def __init__(self, model_name: str = "BAAI/bge-m3", batch_size: int = 32):
        """
        Args:
            model_name: Название модели из HuggingFace
            batch_size: Размер батча для encode
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.model = None
        
        logger.info(f"EmbeddingsEngine инициализирован: model={model_name}")
    
    def _load_model(self):
        """Ленивая загрузка модели (при первом вызове encode)"""
        if self.model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            
            logger.info(f"Загрузка модели {self.model_name}...")
            logger.info("(При первом запуске модель скачается из HuggingFace, ~2GB)")
            
            self.model = SentenceTransformer(self.model_name)
            
            logger.info(f"✓ Модель {self.model_name} загружена")
            logger.info(f"  Размерность: {self.model.get_sentence_embedding_dimension()}")
        
        except ImportError:
            logger.error("sentence-transformers не установлен!")
            logger.error("Установите: pip install sentence-transformers")
            raise
        
        except Exception as e:
            logger.error(f"Ошибка загрузки модели {self.model_name}: {e}")
            logger.info("Пробуем упрощённую модель: all-MiniLM-L6-v2")
            
            try:
                from sentence_transformers import SentenceTransformer
                self.model_name = "all-MiniLM-L6-v2"
                self.model = SentenceTransformer(self.model_name)
                logger.info(f"✓ Загружена упрощённая модель: {self.model_name}")
            except:
                raise RuntimeError("Не удалось загрузить ни одну модель embeddings")
    
    def encode(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """
        Создаёт embeddings для списка текстов
        
        Args:
            texts: Список текстов
            show_progress: Показывать прогресс-бар
        
        Returns:
            Матрица embeddings [N x dim]
        """
        self._load_model()
        
        if not texts:
            return np.array([])
        
        logger.info(f"Создание embeddings для {len(texts)} текстов...")
        
        # Encode батчами для экономии памяти
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True  # Для cosine similarity
        )
        
        logger.info(f"✓ Создано embeddings: shape={embeddings.shape}")
        
        return embeddings
    
    def encode_query(self, query: str) -> np.ndarray:
        """
        Создаёт embedding для поискового запроса
        
        Args:
            query: Текст запроса
        
        Returns:
            Вектор [dim]
        """
        self._load_model()
        
        embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True
        )[0]
        
        return embedding
    
    def save_embeddings(self, embeddings: np.ndarray, path: Path):
        """
        Сохраняет embeddings на диск
        
        Args:
            embeddings: Матрица embeddings
            path: Путь для сохранения (.npy)
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(path), embeddings)
        logger.info(f"Embeddings сохранены: {path} ({embeddings.shape})")
    
    def load_embeddings(self, path: Path) -> np.ndarray:
        """
        Загружает embeddings с диска
        
        Args:
            path: Путь к файлу .npy
        
        Returns:
            Матрица embeddings
        """
        if not path.exists():
            raise FileNotFoundError(f"Embeddings не найдены: {path}")
        
        embeddings = np.load(str(path))
        logger.info(f"Embeddings загружены: {path} ({embeddings.shape})")
        
        return embeddings
    
    def get_dimension(self) -> int:
        """Возвращает размерность векторов"""
        self._load_model()
        return self.model.get_sentence_embedding_dimension()
