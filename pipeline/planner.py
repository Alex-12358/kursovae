"""
Planner - построение структуры курсовой работы
Использует DeepSeek-R1 для планирования глав и разделов
"""
import json
import logging
from typing import Dict, Any

from llm.gateway import OllamaGateway
from llm.router import get_model_config

logger = logging.getLogger(__name__)

PLANNER_SYSTEM = """Ты — Planner. Твоя единственная задача: спроектировать структуру курсовой работы
по деталям машин (ГГТУ) на основе входных параметров и calc_trace.

ПРАВИЛА — НАРУШЕНИЕ НЕДОПУСТИМО:
1. Ты НЕ пишешь текст глав. Только структуру.
2. Ты НЕ придумываешь числа. Все числа — только из <CALC_TRACE>.
3. Верни ТОЛЬКО валидный JSON без текста до или после.

Типы контента секций:
  LLM_THEORY    — теоретическое описание, пишет Writer
  LLM_ANALYSIS  — анализ выбора, обоснование, пишет Writer
  CALC_TEMPLATE — расчётный раздел, числа из calc_trace
  GOST_TABLE    — таблица из ГОСТ, Python вставляет готовую

Формат вывода:
{{
  "plan_version": "v5",
  "scheme": "<схема>",
  "chapters": [
    {{
      "idx": 1,
      "title": "Название главы",
      "sections": [
        {{
          "idx": "1.1",
          "title": "Название раздела",
          "content_type": "LLM_THEORY",
          "calc_vars": ["T2", "n1"],
          "notes": "Инструкция для Writer"
        }}
      ]
    }}
  ],
  "total_chapters": 8
}}"""

PLANNER_USER_TEMPLATE = """<CALC_TRACE>
{calc_trace}
</CALC_TRACE>

<TASK>
{task_json}
</TASK>

Построй план курсовой работы."""


class Planner:
    """
    Планировщик структуры курсовой работы
    Использует DeepSeek-R1 для генерации плана
    """
    
    def __init__(self, gateway: OllamaGateway):
        """
        Args:
            gateway: OllamaGateway для обращения к модели
        """
        self.gateway = gateway
        self.model_config = get_model_config("planner_critic")
        logger.info(f"Инициализирован Planner с моделью {self.model_config['model']}")
    
    async def plan(self, calc_trace: Dict[str, Any], task_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Построить план курсовой работы
        
        Args:
            calc_trace: Трассировка расчётов из Calc Engine
            task_json: Входные параметры задачи
            
        Returns:
            Структура плана (dict)
        """
        logger.info("=== СТАРТ PLANNER ===")
        
        # Подготовить промпт
        calc_trace_str = json.dumps(calc_trace, ensure_ascii=False, indent=2)
        task_json_str = json.dumps(task_json, ensure_ascii=False, indent=2)
        
        user_message = PLANNER_USER_TEMPLATE.format(
            calc_trace=calc_trace_str,
            task_json=task_json_str
        )
        
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": user_message}
        ]
        
        logger.info(f"Planner: system_len={len(PLANNER_SYSTEM)}, user_len={len(user_message)}")
        
        # Retry до 3 раз для парсинга JSON
        for attempt in range(3):
            try:
                logger.info(f"Planner запрос (попытка {attempt + 1}/3)")
                
                # Вызвать модель через chat API
                response = await self.gateway.chat(
                    model=self.model_config["model"],
                    messages=messages,
                    temperature=self.model_config["temperature"],
                    top_p=self.model_config["top_p"],
                    max_tokens=self.model_config["max_tokens"]
                )
                
                # Парсинг JSON
                plan = self._parse_json_response(response)
                
                if plan:
                    logger.info(f"План построен: глав={plan.get('total_chapters', 0)}")
                    logger.info("=== PLANNER ЗАВЕРШЁН ===")
                    return plan
                else:
                    logger.warning(f"Не удалось распарсить JSON (попытка {attempt + 1})")
                    if attempt < 2:
                        logger.info("Повтор запроса...")
            
            except Exception as e:
                logger.error(f"Ошибка Planner (попытка {attempt + 1}): {e}")
                if attempt < 2:
                    logger.info("Повтор запроса...")
        
        # Если все попытки провалились
        logger.error("Planner провалился после 3 попыток")
        raise RuntimeError("Planner не смог построить валидный план")
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Извлечь и распарсить JSON из ответа модели
        
        Args:
            response: Ответ модели
            
        Returns:
            Распарсенный dict или None
        """
        # Попытка найти JSON блок
        response = response.strip()
        
        # Убрать thinking теги если есть (DeepSeek-R1)
        if "</think>" in response:
            parts = response.split("</think>")
            if len(parts) > 1:
                response = parts[-1].strip()  # Берём часть после </think>
                logger.debug("Убраны thinking теги из ответа")
        
        # Убрать markdown обёртку если есть
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        response = response.strip()
        
        # Найти первую { и последнюю }
        start = response.find('{')
        end = response.rfind('}')
        
        if start == -1 or end == -1 or start >= end:
            logger.error("Не найдены JSON скобки в ответе")
            logger.debug(f"Ответ: {response[:500]}...")
            return None
        
        json_str = response[start:end + 1]
        
        try:
            plan = json.loads(json_str)
            
            # Валидация структуры
            if "chapters" not in plan:
                logger.error("Отсутствует поле 'chapters' в плане")
                return None
            
            logger.debug(f"JSON успешно распарсен: глав={len(plan.get('chapters', []))}")
            return plan
        
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            logger.debug(f"JSON строка: {json_str[:500]}...")
            return None
