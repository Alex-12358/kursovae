"""
Smart Chunker - разбиение документов на смысловые чанки
С учётом размера, overlap и границ предложений
"""
import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class SmartChunker:
    """Умная разбивка текста на чанки для embeddings"""
    
    def __init__(self, chunk_size: int = 512, overlap: int = 128):
        """
        Args:
            chunk_size: Размер чанка в символах
            overlap: Перекрытие между чанками
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        logger.info(f"SmartChunker: chunk_size={chunk_size}, overlap={overlap}")
    
    def chunk_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Разбивает список документов на чанки
        
        Args:
            documents: [{"text": "...", "metadata": {...}}]
        
        Returns:
            [{"chunk_id": "...", "text": "...", "metadata": {...}}]
        """
        logger.info(f"Разбиение {len(documents)} фрагментов на чанки...")
        
        all_chunks = []
        chunk_counter = 0
        
        for doc in documents:
            text = doc["text"]
            metadata = doc["metadata"]
            
            # Если текст короткий — берём как есть
            if len(text) <= self.chunk_size:
                chunk_counter += 1
                all_chunks.append({
                    "chunk_id": f"chunk_{chunk_counter:06d}",
                    "text": text,
                    "metadata": metadata
                })
                continue
            
            # Разбиваем длинный текст на чанки
            chunks = self._split_text(text)
            
            for chunk_text in chunks:
                chunk_counter += 1
                all_chunks.append({
                    "chunk_id": f"chunk_{chunk_counter:06d}",
                    "text": chunk_text,
                    "metadata": metadata
                })
        
        logger.info(f"Создано чанков: {len(all_chunks)}")
        
        # Статистика
        etalon_chunks = sum(1 for c in all_chunks if c["metadata"].get("is_etalon"))
        logger.info(f"  Из эталона: {etalon_chunks} чанков")
        
        return all_chunks
    
    def _split_text(self, text: str) -> List[str]:
        """
        Разбивает длинный текст на чанки с учётом границ предложений
        
        Args:
            text: Исходный текст
        
        Returns:
            Список чанков
        """
        # Разбиваем на предложения
        sentences = self._split_into_sentences(text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # Если добавление предложения не превышает лимит
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += sentence + " "
            else:
                # Сохраняем текущий chunk
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # Начинаем новый chunk
                # С overlap: берём последние N символов из предыдущего
                if chunks and self.overlap > 0:
                    overlap_text = chunks[-1][-self.overlap:]
                    current_chunk = overlap_text + " " + sentence + " "
                else:
                    current_chunk = sentence + " "
        
        # Добавляем последний chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Разбивает текст на предложения
        
        Учитывает:
        - Точки в конце предложения
        - Сокращения (т.е., т.д., и т.п.)
        - Числа с точками
        
        Returns:
            Список предложений
        """
        # Простая регулярка для разбивки на предложения
        # Точка, восклицательный или вопросительный знак + пробел + заглавная буква
        sentences = re.split(r'(?<=[.!?])\s+(?=[А-ЯA-Z])', text)
        
        return [s.strip() for s in sentences if s.strip()]
