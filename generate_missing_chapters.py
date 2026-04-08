#!/usr/bin/env python3
"""Дописать пустые главы используя новый план"""
import asyncio
import json
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

async def main():
    from pipeline.writer import Writer
    from pipeline.critic import Critic
    from llm.gateway import OllamaGateway
    from retrieval.reference_retriever import ReferenceRetriever
    from config import FAISS_INDEX_PATH, CHUNKS_DB_PATH
    
    session_id = "session_20260406_235441"
    checkpoints_dir = Path(f"storage/checkpoints/{session_id}")
    
    # Загружаем старый TEXT_ENGINE
    with open(checkpoints_dir / "TEXT_ENGINE.json", 'r', encoding='utf-8') as f:
        old_text_data = json.load(f)
    
    old_chapters = old_text_data.get("result", {}).get("chapters", {})
    
    # Загружаем новый план
    with open(checkpoints_dir / "LLM_PLANNING_NEW.json", 'r', encoding='utf-8') as f:
        new_plan_data = json.load(f)
    
    plan = new_plan_data.get("result", {}).get("plan", {})
    
    # Загружаем CALC_ENGINE
    with open(checkpoints_dir / "CALC_ENGINE.json", 'r', encoding='utf-8') as f:
        calc_data = json.load(f)
    
    calc_trace = calc_data.get("result", {}).get("calc_trace", {})
    
    # Проверяем что calc_trace загружен
    logger.info(f"calc_trace загружен, ключей: {len(calc_trace)}")
    if calc_trace:
        logger.info(f"  Доступные ключи: {list(calc_trace.keys())}")
    else:
        logger.warning("⚠️ calc_trace ПУСТОЙ! Числа из расчётов не попадут в текст")
    
    # Инициализируем LLM
    gateway = OllamaGateway()
    
    # Загружаем retriever (если есть)
    retriever = None
    if FAISS_INDEX_PATH.exists(): #lol
        retriever = ReferenceRetriever()
       # await retriever.load_index(str(FAISS_INDEX_PATH), str(CHUNKS_DB_PATH))
    
    writer = Writer(gateway)
    critic = Critic(gateway)
    
    logger.info(f"=== ДОПИСЫВАЕМ ПУСТЫЕ ГЛАВЫ ===")
    logger.info(f"Найдено глав в старом checkpoint: {len(old_chapters)}")
    
    # Определяем пустые главы
    empty_chapters = []
    for ch in plan.get("chapters", []):
        idx = str(ch.get("idx", 0))
        if idx in old_chapters:
            text_len = len(old_chapters[idx].get("text", ""))
            if text_len == 0:
                empty_chapters.append(ch)
                logger.info(f"  Глава {idx} пустая — нужно сгенерировать")
        else:
            empty_chapters.append(ch)
            logger.info(f"  Глава {idx} не найдена — нужно сгенерировать")
    
    logger.info(f"\nВсего пустых глав: {len(empty_chapters)}")
    
    # Генерируем текст для пустых глав
    new_chapters = old_chapters.copy()
    
    for i, chapter in enumerate(empty_chapters, 1):
        chapter_idx = str(chapter.get("idx", 0))
        chapter_title = chapter.get("title", "")
        sections = chapter.get("sections", [])
        llm_task = chapter.get("llm_task", "")
        
        logger.info(f"\n[{i}/{len(empty_chapters)}] Генерируем главу {chapter_idx}: {chapter_title}")
        
        chapter_text_parts = []
        
        # Если есть секции — генерируем каждую
        if sections:
            for j, section in enumerate(sections, 1):
                section_idx = section.get("idx", "")
                section_title = section.get("title", "")
                logger.info(f"  [{j}/{len(sections)}] Секция {section_idx}: {section_title}")
                
                section_text = await writer.write_section(section, calc_trace)
                chapter_text_parts.append(section_text)
        else:
            # Создаём pseudo-section для главы без секций
            logger.info(f"  Глава без секций, llm_task: {llm_task[:80]}")
            
            pseudo_section = {
                "idx": chapter_idx,
                "title": chapter_title,
                "content_type": "LLM_THEORY",
                "llm_task": llm_task,
                "calc_vars": [],
                "notes": f"Напиши полный текст раздела '{chapter_title}'"
            }
            chapter_text = await writer.write_section(pseudo_section, calc_trace)
            chapter_text_parts.append(chapter_text)
        
        chapter_text = "\n\n".join(chapter_text_parts)
        
        # Проверяем через Critic
        logger.info(f"  Проверка через Critic (text_len={len(chapter_text)})")
        critique_result = await critic.critique(chapter_idx, chapter_text, calc_trace)
        
        new_chapters[chapter_idx] = {
            "text": chapter_text,
            "title": chapter_title,
            "critique": critique_result
        }
        
        logger.info(f"  ✓ Глава {chapter_idx} сгенерирована ({len(chapter_text)} символов)")
    
    # Сохраняем обновлённый TEXT_ENGINE
    updated_text_data = {
        "node_name": "TEXT_ENGINE",
        "status": "done",
        "result": {
            "chapters": new_chapters
        }
    }
    
    output_path = checkpoints_dir / "TEXT_ENGINE_COMPLETE.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(updated_text_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n✅ ЗАВЕРШЕНО!")
    logger.info(f"   Обновлённый TEXT_ENGINE сохранён: {output_path}")
    logger.info(f"   Всего глав: {len(new_chapters)}")
    
    # Статистика
    total_chars = sum(len(ch.get("text", "")) for ch in new_chapters.values())
    logger.info(f"   Общий объём текста: {total_chars} символов")

if __name__ == "__main__":
    asyncio.run(main())
