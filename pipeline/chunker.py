"""
Chunker модуль для разбиения текста на семантические куски.
Нарезает документы на фрагменты для эмбеддинга и поиска.
"""

import logging
from typing import List, Dict, Any
import uuid

logger = logging.getLogger(__name__)

# Параметры чанкинга
CHUNK_SIZE = 512  # токенов
CHUNK_OVERLAP = 64  # токенов перекрытия


def chunk_documents(documents: List[Dict[str, Any]], 
                    chunk_size: int = CHUNK_SIZE,
                    overlap: int = CHUNK_OVERLAP) -> List[Dict[str, Any]]:
    """
    Нарезка списка документов на чанки.
    
    Args:
        documents: Список документов из parser.py
        chunk_size: Размер чанка в токенах
        overlap: Размер перекрытия в токенах
    
    Returns:
        Список чанков: [{"chunk_id": ..., "source": ..., "text": ..., "metadata": ...}]
    """
    all_chunks = []
    
    for doc in documents:
        logger.info(f"Чанкинг документа: {doc['filename']}")
        chunks = chunk_text(
            text=doc["text"],
            source_filename=doc["filename"],
            chunk_size=chunk_size,
            overlap=overlap
        )
        
        # Добавляем метаданные из исходного документа
        for chunk in chunks:
            chunk["metadata"] = {
                "source_format": doc.get("format", "unknown"),
                "source_pages": doc.get("pages", 0),
                "source_path": doc.get("path", "")
            }
        
        all_chunks.extend(chunks)
    
    logger.info(f"Всего чанков создано: {len(all_chunks)}")
    return all_chunks


def chunk_text(text: str, 
               source_filename: str,
               chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[Dict[str, Any]]:
    """
    Разбиение одного текста на чанки с перекрытием.
    
    Args:
        text: Исходный текст
        source_filename: Имя файла-источника
        chunk_size: Размер чанка в токенах
        overlap: Размер перекрытия в токенах
    
    Returns:
        Список чанков
    """
    # Простая токенизация: слова как токены (для точности нужен tiktoken или transformers tokenizer)
    # Но для базовой реализации используем split по пробелам
    tokens = text.split()
    
    chunks = []
    chunk_index = 0
    start = 0
    
    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunk_text = " ".join(chunk_tokens)
        
        # Создаём чанк
        chunk_id = f"{source_filename}_{chunk_index}_{uuid.uuid4().hex[:8]}"
        chunks.append({
            "chunk_id": chunk_id,
            "source": source_filename,
            "text": chunk_text,
            "chunk_index": chunk_index,
            "token_count": len(chunk_tokens),
            "char_count": len(chunk_text)
        })
        
        chunk_index += 1
        
        # Следующий чанк начинается с перекрытием
        start += (chunk_size - overlap)
    
    logger.info(f"  Создано {len(chunks)} чанков из {len(tokens)} токенов")
    return chunks


def chunk_by_sentences(text: str,
                       source_filename: str,
                       max_chunk_tokens: int = CHUNK_SIZE) -> List[Dict[str, Any]]:
    """
    Разбиение текста по предложениям с соблюдением лимита токенов.
    Более семантически корректный способ чанкинга.
    
    Args:
        text: Исходный текст
        source_filename: Имя файла-источника
        max_chunk_tokens: Максимальный размер чанка в токенах
    
    Returns:
        Список чанков
    """
    # Простое разбиение на предложения (по точкам, восклицательным и вопросительным знакам)
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = []
    current_tokens = 0
    chunk_index = 0
    
    for sentence in sentences:
        sentence_tokens = len(sentence.split())
        
        if current_tokens + sentence_tokens > max_chunk_tokens and current_chunk:
            # Сохраняем текущий чанк
            chunk_text = " ".join(current_chunk)
            chunk_id = f"{source_filename}_{chunk_index}_{uuid.uuid4().hex[:8]}"
            
            chunks.append({
                "chunk_id": chunk_id,
                "source": source_filename,
                "text": chunk_text,
                "chunk_index": chunk_index,
                "token_count": current_tokens,
                "char_count": len(chunk_text)
            })
            
            chunk_index += 1
            current_chunk = []
            current_tokens = 0
        
        current_chunk.append(sentence)
        current_tokens += sentence_tokens
    
    # Последний чанк
    if current_chunk:
        chunk_text = " ".join(current_chunk)
        chunk_id = f"{source_filename}_{chunk_index}_{uuid.uuid4().hex[:8]}"
        
        chunks.append({
            "chunk_id": chunk_id,
            "source": source_filename,
            "text": chunk_text,
            "chunk_index": chunk_index,
            "token_count": current_tokens,
            "char_count": len(chunk_text)
        })
    
    logger.info(f"  Создано {len(chunks)} чанков (по предложениям)")
    return chunks
