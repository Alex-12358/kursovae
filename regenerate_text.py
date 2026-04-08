#!/usr/bin/env python3
"""Перегенерация TEXT_ENGINE с новым LLM_PLANNING"""
import asyncio
import json
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

async def main():
    from core.dag import node_llm_planning, node_text_engine
    
    session_id = "session_20260406_235441"
    checkpoints_dir = Path(f"storage/checkpoints/{session_id}")
    
    # Загружаем task.json
    with open("data/input/task.json", 'r', encoding='utf-8') as f:
        task_data = json.load(f)
    
    # Загружаем CALC_ENGINE checkpoint
    with open(checkpoints_dir / "CALC_ENGINE.json", 'r', encoding='utf-8') as f:
        calc_checkpoint = json.load(f)
    
    # Загружаем REF_ANALYZER checkpoint
    with open(checkpoints_dir / "REF_ANALYZER.json", 'r', encoding='utf-8') as f:
        ref_checkpoint = json.load(f)
    
    logger.info("=== ПЕРЕГЕНЕРАЦИЯ LLM_PLANNING С НОВОЙ ЛОГИКОЙ ===")
    
    ctx = {"task_data": task_data}
    deps = {
        "CALC_ENGINE": calc_checkpoint.get("result", {}),
        "REF_ANALYZER": ref_checkpoint.get("result", {})
    }
    
    # Генерируем новый план
    plan_result = await node_llm_planning(ctx, deps)
    plan = plan_result["plan"]
    
    # Показываем главы с llm_task
    logger.info(f"\nПлан содержит {len(plan['chapters'])} глав:")
    for ch in plan["chapters"]:
        idx = ch.get("idx", "?")
        title = ch.get("title", "")
        sections = ch.get("sections", [])
        llm_task = ch.get("llm_task", "")
        
        logger.info(f"  Глава {idx}: {title}")
        logger.info(f"    Секций: {len(sections)}")
        logger.info(f"    llm_task: {llm_task[:80] if llm_task else 'NONE'}")
    
    # Сохраняем новый план
    new_plan_path = checkpoints_dir / "LLM_PLANNING_NEW.json"
    with open(new_plan_path, 'w', encoding='utf-8') as f:
        json.dump({
            "node_name": "LLM_PLANNING",
            "status": "done",
            "result": plan_result
        }, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n✓ Новый план сохранён: {new_plan_path}")
    
    # ОПЦИОНАЛЬНО: можно сразу запустить TEXT_ENGINE для пустых глав
    # Но это займёт несколько часов — лучше сделать отдельной командой

if __name__ == "__main__":
    asyncio.run(main())
