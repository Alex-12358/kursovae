#!/usr/bin/env python3
"""Отладка пустых глав"""
import json

# Загружаем LLM_PLANNING
with open('storage/checkpoints/session_20260406_235441/LLM_PLANNING.json', 'r', encoding='utf-8') as f:
    plan_data = json.load(f)

plan = plan_data.get('result', {}).get('plan', {})
chapters = plan.get('chapters', [])

print(f"=== LLM_PLANNING: {len(chapters)} глав ===\n")

for ch in chapters:
    idx = ch.get('idx', '?')
    title = ch.get('title', 'NO TITLE')
    sections = ch.get('sections', [])
    llm_task = ch.get('llm_task', None)
    
    print(f"Глава {idx}: {title}")
    print(f"  Секций: {len(sections)}")
    print(f"  llm_task: {llm_task[:80] if llm_task else 'None'}")
    
    if len(sections) > 0:
        for sec in sections:
            sec_idx = sec.get('idx', '?')
            sec_title = sec.get('title', '?')
            print(f"    - {sec_idx}: {sec_title}")
    print()

# Загружаем TEXT_ENGINE
with open('storage/checkpoints/session_20260406_235441/TEXT_ENGINE.json', 'r', encoding='utf-8') as f:
    text_data = json.load(f)

text_chapters = text_data.get('result', {}).get('chapters', {})

print(f"\n=== TEXT_ENGINE: {len(text_chapters)} глав ===\n")

for idx, ch in sorted(text_chapters.items(), key=lambda x: (int(x[0]) if str(x[0]).isdigit() else 999)):
    title = ch.get('title', 'NO TITLE')
    text = ch.get('text', '')
    text_len = len(text)
    
    status = "✓ OK" if text_len > 0 else "✗ EMPTY"
    print(f"{status} Глава {idx}: {title[:60]} ({text_len} chars)")
