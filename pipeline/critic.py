"""
Critic - проверка качества глав курсовой работы
Использует DeepSeek-R1 для адверсариальной критики
"""
import json
import logging
from typing import Dict, Any

from llm.gateway import OllamaGateway
from llm.router import get_model_config

logger = logging.getLogger(__name__)

CRITIC_SYSTEM = """Ты — Critic. Проверяешь главу курсовой работы по деталям машин.

ПРОВЕРЯЕШЬ:
1. ЧИСЛА: все числа в тексте совпадают с calc_trace? (допуск ±1 в последнем знаке)
2. ФОРМУЛЫ: правильные размерности? правильные обозначения?
3. ФИЗИЧЕСКИЙ СМЫСЛ: нет абсурдных утверждений?
4. МАРКЕРЫ: правильно расставлены [FORMULA][FIGURE][TABLE]?

НЕ ПРОВЕРЯЕШЬ: стиль, нумерацию, орфографию, оформление ГОСТ.

Верни ТОЛЬКО валидный JSON:
{
  "chapter_idx": N,
  "score": 0.85,
  "verdict": "PASS",
  "issues": [
    {
      "type": "WRONG_NUMBER",
      "severity": "CRITICAL",
      "location": "раздел 3.2",
      "found": "что в тексте",
      "expected": "что в calc_trace",
      "fix": "инструкция для Writer"
    }
  ],
  "skip_rewrite": true,
  "rewrite_sections": []
}

Вердикт: PASS если score≥0.8 и нет CRITICAL/MAJOR. FAIL если есть CRITICAL."""

CRITIC_USER_TEMPLATE = """<CALC_TRACE>
{calc_trace}
</CALC_TRACE>

Проверь главу {chapter_idx}:
<CHAPTER_TEXT>
{chapter_text}
</CHAPTER_TEXT>"""


class Critic:
    """
    Критик качества текста
    Использует DeepSeek-R1 для адверсариальной проверки
    """
    
    def __init__(self, gateway: OllamaGateway):
        """
        Args:
            gateway: OllamaGateway для обращения к модели
        """
        self.gateway = gateway
        self.model_config = get_model_config("planner_critic")
        logger.info(f"Инициализирован Critic с моделью {self.model_config['model']}")
    
    async def critique(
        self,
        chapter_idx: int,
        chapter_text: str,
        calc_trace: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Проверить главу
        
        Args:
            chapter_idx: Номер главы
            chapter_text: Текст главы
            calc_trace: Трассировка расчётов
            
        Returns:
            {
                "chapter_idx": 3,
                "score": 0.85,
                "verdict": "PASS",
                "issues": [...],
                "skip_rewrite": True,
                "rewrite_sections": []
            }
        """
        logger.info(f"=== СТАРТ CRITIC: глава {chapter_idx} ===")
        
        # Подготовить промпт
        calc_trace_str = json.dumps(calc_trace, ensure_ascii=False, indent=2)
        
        user_message = CRITIC_USER_TEMPLATE.format(
            chapter_idx=chapter_idx,
            calc_trace=calc_trace_str,
            chapter_text=chapter_text
        )
        
        messages = [
            {"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": user_message}
        ]
        
        logger.info(f"Critic запрос: chapter={chapter_idx}, text_len={len(chapter_text)}")
        
        try:
            # Вызвать модель через chat API
            response = await self.gateway.chat(
                model=self.model_config["model"],
                messages=messages,
                temperature=self.model_config["temperature"],
                top_p=self.model_config["top_p"],
                max_tokens=self.model_config["max_tokens"]
            )
            
            # Парсинг JSON
            critique = self._parse_json_response(response, chapter_idx)
            
            if critique:
                score = critique.get("score", 0.0)
                verdict = critique.get("verdict", "FAIL")
                issues_count = len(critique.get("issues", []))
                
                logger.info(
                    f"Critic завершён: chapter={chapter_idx}, "
                    f"score={score}, verdict={verdict}, issues={issues_count}"
                )
                
                # Автоматический skip_rewrite если score > 0.8
                if score > 0.8 and verdict == "PASS":
                    critique["skip_rewrite"] = True
                    logger.info(f"Глава {chapter_idx} прошла проверку (score > 0.8), переписывание не требуется")
                
                logger.info(f"=== CRITIC ЗАВЕРШЁН: глава {chapter_idx} ===")
                return critique
            else:
                logger.error("Не удалось распарсить JSON от Critic")
                # Возвращаем дефолтный FAIL
                return {
                    "chapter_idx": chapter_idx,
                    "score": 0.0,
                    "verdict": "FAIL",
                    "issues": [{"type": "PARSE_ERROR", "severity": "CRITICAL", "location": "N/A", "found": "JSON parse error", "expected": "valid JSON", "fix": "Retry"}],
                    "skip_rewrite": False,
                    "rewrite_sections": []
                }
        
        except Exception as e:
            logger.error(f"Ошибка Critic для главы {chapter_idx}: {e}")
            raise
    
    def _parse_json_response(self, response: str, chapter_idx: int) -> Dict[str, Any]:
        """
        Извлечь и распарсить JSON из ответа модели
        
        Args:
            response: Ответ модели
            chapter_idx: Номер главы для логирования
            
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
                logger.debug(f"Убраны thinking теги из ответа Critic для главы {chapter_idx}")
        
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
            logger.error(f"Не найдены JSON скобки в ответе Critic для главы {chapter_idx}")
            logger.debug(f"Ответ: {response[:500]}...")
            return None
        
        json_str = response[start:end + 1]
        
        try:
            critique = json.loads(json_str)
            
            # Валидация структуры
            if "score" not in critique or "verdict" not in critique:
                logger.error(f"Отсутствуют обязательные поля в ответе Critic для главы {chapter_idx}")
                return None
            
            logger.debug(f"JSON успешно распарсен: score={critique.get('score')}, verdict={critique.get('verdict')}")
            return critique
        
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON Critic для главы {chapter_idx}: {e}")
            logger.debug(f"JSON строка: {json_str[:500]}...")
            return None
