"""
Тест индексации и поиска для Smart Critic v6
Проверяет парсинг, embeddings, FAISS индекс и поиск
"""
import asyncio
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


async def test_indexing():
    """Тест полного pipeline индексации"""
    
    from retrieval.document_parser import parse_all_sources
    from retrieval.chunker import SmartChunker
    from retrieval.ollama_embeddings import create_embeddings_engine
    from retrieval.reference_retriever import ReferenceRetriever
    from config import (
        SOURCES_DIR, CHUNK_SIZE, CHUNK_OVERLAP, USE_OLLAMA_EMBEDDINGS, 
        FAISS_INDEX_PATH, CHUNKS_DB_PATH, EMBEDDING_BATCH_SIZE, EMBEDDING_MAX_WORKERS
    )
    
    logger.info("=== ТЕСТ ИНДЕКСАЦИИ ===")
    
    # 1. Парсинг
    logger.info("\n1. Парсинг документов...")
    documents = parse_all_sources(SOURCES_DIR)
    logger.info(f"Найдено фрагментов: {len(documents)}")
    
    if not documents:
        logger.error("Нет документов для индексации!")
        return
    
    # 2. Chunking
    logger.info("\n2. Разбиение на чанки...")
    chunker = SmartChunker(chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    chunks = chunker.chunk_documents(documents)
    logger.info(f"Создано чанков: {len(chunks)}")
    
    etalon_chunks = [c for c in chunks if c["metadata"].get("is_etalon")]
    logger.info(f"  Из эталона (2603-1716.docx): {len(etalon_chunks)}")
    
    # 3. Embeddings
    logger.info("\n3. Создание embeddings...")
    engine = create_embeddings_engine(use_ollama=USE_OLLAMA_EMBEDDINGS)
    texts = [c["text"] for c in chunks]
    embeddings = engine.encode(
        texts, 
        batch_size=EMBEDDING_BATCH_SIZE,
        show_progress_bar=True,
        max_workers=EMBEDDING_MAX_WORKERS
    )
    logger.info(f"Embeddings: shape={embeddings.shape}")
    
    # 4. FAISS индекс
    logger.info("\n4. Построение FAISS индекса...")
    retriever = ReferenceRetriever()
    retriever.build_index(chunks, embeddings)
    logger.info("✓ Индекс построен")
    
    # 5. Тестовые поиски
    logger.info("\n5. Тестовые поиски...\n")
    
    test_queries = [
        ("Введение", True),  # Из эталона
        ("Расчёт валов", True),
        ("Подшипники качения", False),  # Из любых источников
        ("ГОСТ 21354", False)
    ]
    
    for query, filter_etalon in test_queries:
        logger.info(f"\nПоиск: '{query}' (filter_etalon={filter_etalon})")
        results = retriever.search(query, top_k=3, filter_etalon=filter_etalon)
        
        for i, res in enumerate(results, 1):
            source = res["metadata"]["source"]
            score = res["score"]
            text_preview = res["text"][:100].replace("\n", " ")
            logger.info(f"  {i}. [{source}] score={score:.3f}")
            logger.info(f"     {text_preview}...")
    
    logger.info("\n=== ТЕСТ ЗАВЕРШЁН ===")


if __name__ == "__main__":
    asyncio.run(test_indexing())
