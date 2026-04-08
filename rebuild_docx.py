#!/usr/bin/env python3
"""
Пересборка DOCX из сохранённых checkpoint'ов без перезапуска pipeline
Использует TEXT_ENGINE checkpoint для получения chapters
"""
import asyncio
import json
import logging
from pathlib import Path

from config import BASE_DIR, OUTPUT_DIR, STORAGE_DIR, LOG_LEVEL
from core.dag import node_docx_builder, node_bibliography_engine, node_toc_builder

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


async def rebuild_docx_from_checkpoints(session_id: str):
    """
    Пересобрать DOCX из checkpoint'ов сессии
    
    Args:
        session_id: ID сессии (например, session_20260406_235441)
    """
    logger.info(f"=== ПЕРЕСБОРКА DOCX ИЗ CHECKPOINT'ОВ ===")
    logger.info(f"Сессия: {session_id}")
    
    checkpoint_dir = STORAGE_DIR / "checkpoints" / session_id
    
    if not checkpoint_dir.exists():
        logger.error(f"Checkpoint директория не найдена: {checkpoint_dir}")
        return None
    
    # Загрузить checkpoint TEXT_ENGINE
    text_engine_checkpoint = checkpoint_dir / "TEXT_ENGINE_COMPLETE.json"
    if not text_engine_checkpoint.exists():
        logger.error(f"TEXT_ENGINE checkpoint не найден: {text_engine_checkpoint}")
        return None
    
    logger.info(f"Загружаем TEXT_ENGINE checkpoint...")
    with open(text_engine_checkpoint, "r", encoding="utf-8") as f:
        text_engine_checkpoint_data = json.load(f)
    
    # Checkpoint содержит метаданные + result
    text_engine_result = text_engine_checkpoint_data.get("result", {})
    
    chapters = text_engine_result.get("chapters", {})
    logger.info(f"Загружено глав: {len(chapters)}")
    
    # Вывести статистику по главам
    for idx, chapter_data in chapters.items():
        title = chapter_data.get("title", f"Глава {idx}")
        text_len = len(chapter_data.get("text", ""))
        logger.info(f"  Глава {idx}: '{title}' — {text_len} символов")
    
    # Загрузить checkpoint DRAWING_ENGINE (если есть)
    drawing_checkpoint = checkpoint_dir / "DRAWING_ENGINE.json"
    drawing_result = {}
    if drawing_checkpoint.exists():
        logger.info(f"Загружаем DRAWING_ENGINE checkpoint...")
        with open(drawing_checkpoint, "r", encoding="utf-8") as f:
            drawing_checkpoint_data = json.load(f)
            drawing_result = drawing_checkpoint_data.get("result", {})
    
    # Подготовить deps для узлов
    deps = {
        "FIGURE_NUMBERER": {"chapters": chapters},
        "DRAWING_ENGINE": drawing_result
    }
    
    # Запустить узлы сборки
    logger.info("\n=== ЗАПУСК DOCX_BUILDER ===")
    docx_result = await node_docx_builder(ctx={}, deps=deps)
    
    logger.info("\n=== ЗАПУСК BIBLIOGRAPHY_ENGINE ===")
    biblio_result = await node_bibliography_engine(
        ctx={},
        deps={"DOCX_BUILDER": docx_result}
    )
    
    logger.info("\n=== ЗАПУСК TOC_BUILDER ===")
    toc_result = await node_toc_builder(
        ctx={},
        deps={"BIBLIOGRAPHY_ENGINE": biblio_result}
    )
    
    output_path = OUTPUT_DIR / "coursework.docx"
    
    if output_path.exists():
        logger.info(f"\n✅ DOCX успешно пересобран: {output_path}")
        logger.info(f"   Размер: {output_path.stat().st_size / 1024:.1f} KB")
        return output_path
    else:
        logger.error(f"\n❌ DOCX не создан")
        return None


async def main():
    """Главная функция"""
    import sys
    
    if len(sys.argv) < 2:
        print("Использование: python rebuild_docx.py <session_id>")
        print("\nПример:")
        print("  python rebuild_docx.py session_20260406_235441")
        print("\nДоступные сессии:")
        
        sessions_dir = STORAGE_DIR / "checkpoints"
        if sessions_dir.exists():
            for session_dir in sorted(sessions_dir.iterdir()):
                if session_dir.is_dir() and session_dir.name.startswith("session_"):
                    text_engine_checkpoint = session_dir / "TEXT_ENGINE_COMPLETE.json"
                    if text_engine_checkpoint.exists():
                        print(f"  - {session_dir.name}")
        
        return 1
    
    session_id = sys.argv[1]
    result_path = await rebuild_docx_from_checkpoints(session_id)
    
    return 0 if result_path else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
