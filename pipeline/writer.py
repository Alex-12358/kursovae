"""
Writer - генерация текста разделов курсовой работы
Использует Qwen2.5 для написания академического текста
"""
import logging
import re
from typing import Dict, Any, List

from llm.gateway import OllamaGateway
from llm.router import get_model_config

logger = logging.getLogger(__name__)

WRITER_SYSTEM = """Ты — Writer. Пишешь текст раздела курсовой работы по деталям машин.
Академический технический язык. Русский язык. Без воды.

АБСОЛЮТНЫЕ ЗАПРЕТЫ:
❌ НЕ придумывай числа. Только из <CALC_TRACE>.
❌ НЕ пересчитывай значения из calc_trace.
❌ НЕ нумеруй формулы и рисунки — это делает Assembly Engine.
❌ НЕ пиши заголовок раздела.

РАЗМЕТКА:
Формулы:   [FORMULA]выражение = значение единица[/FORMULA]
Рисунки:   [FIGURE:Описание]
Таблицы:   [TABLE:Название]"""

WRITER_USER_TEMPLATE = """ТИП РАЗДЕЛА: {content_type}
LLM_THEORY   → физический смысл, конструктив, область применения
LLM_ANALYSIS → обоснование выбора на основе calc_trace
CALC_TEMPLATE → формула → подстановка из calc_trace → результат → вывод

<CALC_TRACE>
{calc_trace}
</CALC_TRACE>

Раздел {section_idx}: {section_title}
Тип: {content_type}
Переменные: {calc_vars}
Инструкция: {notes}

Напиши текст раздела. Объём: {target_words} слов."""


class Writer:
    """
    Генератор текста разделов
    Использует Qwen2.5 для написания академического текста
    """
    
    def __init__(self, gateway: OllamaGateway):
        """
        Args:
            gateway: OllamaGateway для обращения к модели
        """
        self.gateway = gateway
        self.model_config = get_model_config("writer")
        logger.info(f"Инициализирован Writer с моделью {self.model_config['model']}")
    
    async def write_section(
        self,
        section: Dict[str, Any],
        calc_trace: Dict[str, Any],
        target_words: int = 400
    ) -> str:
        """
        Написать текст раздела
        
        Args:
            section: Секция из плана:
                {
                    "idx": "1.1",
                    "title": "Название",
                    "content_type": "LLM_THEORY",
                    "calc_vars": ["T2", "n1"],
                    "notes": "Инструкция"
                }
            calc_trace: Трассировка расчётов
            target_words: Целевое количество слов
            
        Returns:
            Текст раздела с маркерами [FORMULA], [FIGURE], [TABLE]
        """
        logger.info(f"=== СТАРТ WRITER: раздел {section['idx']} '{section['title']}' ===")
        
        # Подготовить промпт
        import json
        calc_trace_str = json.dumps(calc_trace, ensure_ascii=False, indent=2)
        
        # ОТЛАДКА: проверяем calc_trace
        if not calc_trace or len(calc_trace) == 0:
            logger.warning(f"⚠️ calc_trace ПУСТОЙ для секции {section['idx']}! LLM не получит числа из расчётов")
        else:
            logger.info(f"✓ calc_trace содержит {len(calc_trace)} ключей: {list(calc_trace.keys())}")
        
        calc_vars_str = ", ".join(section.get("calc_vars", []))
        
        user_message = WRITER_USER_TEMPLATE.format(
            content_type=section.get("content_type", "LLM_THEORY"),
            calc_trace=calc_trace_str,
            section_idx=section["idx"],
            section_title=section["title"],
            calc_vars=calc_vars_str,
            notes=section.get("notes", "Напиши стандартный раздел"),
            target_words=target_words
        )
        
        messages = [
            {"role": "system", "content": WRITER_SYSTEM},
            {"role": "user", "content": user_message}
        ]
        
        logger.info(f"Writer запрос: section={section['idx']}, target_words={target_words}")
        
        try:
            # Вызвать модель через chat API
            text = await self.gateway.chat(
                model=self.model_config["model"],
                messages=messages,
                temperature=self.model_config["temperature"],
                top_p=self.model_config["top_p"],
                max_tokens=self.model_config["max_tokens"]
            )
            
            # Очистить от возможных артефактов
            text = text.strip()
            
            # АГРЕССИВНАЯ ОЧИСТКА thinking тегов (всегда, независимо от наличия)
            # Удаляем всё между <think> и </think> (case-insensitive)
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<THINK>.*?</THINK>', '', text, flags=re.DOTALL)
            # Удаляем одиночные теги если остались
            text = text.replace("<think>", "").replace("</think>", "")
            text = text.replace("<THINK>", "").replace("</THINK>", "")
            # Убираем множественные пробелы/переводы строк после удаления тегов
            text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Макс 2 переноса подряд
            text = text.strip()
            
            if 'think' in text.lower():
                logger.warning(f"⚠️ Слово 'think' всё ещё в тексте раздела {section['idx']}")
            
            # Подсчёт слов
            word_count = len(text.split())
            logger.info(
                f"Writer завершён: section={section['idx']}, "
                f"words={word_count}, chars={len(text)}"
            )
            logger.info(f"=== WRITER ЗАВЕРШЁН: {section['idx']} ===")
            
            return text
        
        except Exception as e:
            logger.error(f"Ошибка Writer для раздела {section['idx']}: {e}")
            raise
