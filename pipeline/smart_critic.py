"""
Smart Critic v6 - глубокий анализ качества текста курсовой
Сравнение с эталоном, оценка стиля, выявление проблем
"""
import logging
import json
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class SmartCritic:
    """Модуль содержательной проверки текста курсовой работы"""
    
    def __init__(self, gateway, retriever):
        """
        Args:
            gateway: OllamaGateway для вызова DeepSeek
            retriever: ReferenceRetriever для поиска примеров
        """
        self.gateway = gateway
        self.retriever = retriever
        self.model = "deepseek-course"
        logger.info("SmartCritic инициализирован")
    
    async def analyze_section(
        self, 
        section_title: str, 
        text: str,
        calc_trace: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Анализирует один раздел курсовой
        
        Args:
            section_title: Название раздела
            text: Текст раздела
            calc_trace: Результаты расчётов (опционально)
        
        Returns:
            {
              "score": 0.85,
              "issues": ["проблема 1", ...],
              "suggestions": ["улучшение 1", ...],
              "style_match": 0.82
            }
        """
        logger.info(f"=== АНАЛИЗ РАЗДЕЛА: {section_title} ===")
        
        # Получить примеры стиля из эталона
        style_chunks = self.retriever.search(
            section_title, 
            top_k=3, 
            filter_etalon=True
        )
        
        style_text = "\n\n---\n\n".join([
            f"ПРИМЕР {i+1}:\n{chunk['text']}"
            for i, chunk in enumerate(style_chunks)
        ])
        
        # Построить промпт
        prompt = self._build_analysis_prompt(
            section_title, 
            text, 
            style_text,
            calc_trace
        )
        
        # Вызвать DeepSeek
        try:
            response = await self.gateway.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4096
            )
            
            # Парсить JSON ответ
            result = self._parse_json_response(response)
            
            # Добавить style_match на основе similarity с эталоном
            result["style_match"] = self._calculate_style_match(text)
            
            logger.info(f"Раздел '{section_title}': score={result['score']:.2f}")
            
            return result
        
        except Exception as e:
            logger.error(f"Ошибка анализа раздела '{section_title}': {e}")
            return {
                "score": 0.5,
                "issues": [f"Ошибка анализа: {str(e)}"],
                "suggestions": [],
                "style_match": 0.5
            }
    
    async def analyze_full_document(
        self, 
        sections: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Глобальный анализ всего документа
        
        Args:
            sections: [{"title": "...", "text": "..."}, ...]
        
        Returns:
            {
              "overall_score": 0.82,
              "section_scores": {"Введение": 0.85, ...},
              "weak_sections": ["Расчёт валов"],
              "summary": "...",
              "verdict": "хорошо, можно сдавать"
            }
        """
        logger.info(f"=== ПОЛНЫЙ АНАЛИЗ ДОКУМЕНТА: {len(sections)} разделов ===")
        
        section_results = {}
        
        # Анализируем каждый раздел
        for section in sections:
            title = section["title"]
            text = section["text"]
            
            result = await self.analyze_section(title, text)
            section_results[title] = result
        
        # Вычисляем общий score (weighted average)
        scores = [r["score"] for r in section_results.values()]
        overall_score = sum(scores) / len(scores) if scores else 0.0
        
        # Находим слабые разделы (score < 0.75)
        weak_sections = [
            title for title, result in section_results.items()
            if result["score"] < 0.75
        ]
        
        # Определяем verdict
        verdict = self._determine_verdict(overall_score)
        
        # Формируем summary
        summary = self._build_summary(overall_score, weak_sections, section_results)
        
        result = {
            "overall_score": round(overall_score, 2),
            "section_scores": {
                title: round(r["score"], 2) 
                for title, r in section_results.items()
            },
            "weak_sections": weak_sections,
            "summary": summary,
            "verdict": verdict,
            "detailed_results": section_results
        }
        
        logger.info(f"=== ИТОГОВЫЙ SCORE: {overall_score:.2f} ===")
        logger.info(f"Verdict: {verdict}")
        
        return result
    
    def compare_with_reference(self, text: str) -> Dict[str, Any]:
        """
        Сравнивает текст с эталоном через embeddings
        
        Args:
            text: Текст для сравнения
        
        Returns:
            {
              "similarity_score": 0.82,
              "style_match": 0.79,
              "structure_match": 0.85,
              "verdict": "хорошо, можно сдавать"
            }
        """
        logger.info("Сравнение с эталоном через embeddings...")
        
        # Ищем топ-10 похожих чанков из эталона
        similar = self.retriever.search(
            text[:500],  # Берём начало текста
            top_k=10, 
            filter_etalon=True
        )
        
        # Вычисляем среднюю similarity
        if similar:
            avg_similarity = sum(c["score"] for c in similar) / len(similar)
        else:
            avg_similarity = 0.0
        
        # Анализ структуры (эвристика)
        structure_score = self._analyze_structure(text)
        
        # Комбинированный score
        combined = (avg_similarity * 0.6 + structure_score * 0.4)
        
        # Verdict
        if combined > 0.85:
            verdict = "отлично, как эталон"
        elif combined > 0.75:
            verdict = "хорошо, можно сдавать"
        elif combined > 0.65:
            verdict = "средне, нужны правки"
        else:
            verdict = "слабо, нужна переработка"
        
        return {
            "similarity_score": round(avg_similarity, 2),
            "style_match": round(avg_similarity, 2),
            "structure_match": round(structure_score, 2),
            "verdict": verdict
        }
    
    def _get_system_prompt(self) -> str:
        """Системный промпт для DeepSeek"""
        return """Ты — опытный преподаватель, проверяющий курсовые работы по деталям машин.

Твоя задача: оценить качество текста как эксперт, сравнить со стилем эталонной работы.

Будь объективен и строг, но конструктивен."""
    
    def _build_analysis_prompt(
        self, 
        section_title: str, 
        text: str, 
        style_examples: str,
        calc_trace: Optional[Dict]
    ) -> str:
        """Строит промпт для анализа раздела"""
        
        prompt = f"""Проанализируй раздел курсовой работы.

РАЗДЕЛ: {section_title}

ТЕКСТ:
{text}

---

ЭТАЛОННЫЕ ПРИМЕРЫ (как должно быть написано):
<STYLE_REFERENCE>
{style_examples}
</STYLE_REFERENCE>

---

КРИТЕРИИ ОЦЕНКИ:
1. Стиль (соответствие эталону) — вес 30%
   - Академичность формулировок
   - Технический язык
   - Структура предложений

2. Структура (логика, последовательность) — вес 25%
   - Логичность изложения
   - Последовательность мыслей
   - Связность абзацев

3. Формулировки (инженерный стиль) — вес 20%
   - Точность терминов
   - Отсутствие разговорных оборотов
   - Профессиональный язык

4. Полнота (раскрытие темы) — вес 15%
   - Достаточность информации
   - Охват всех аспектов темы

5. Грамотность — вес 10%
   - Орфография, пунктуация
   - Правильность оформления

ВАЖНО:
❌ НЕ критикуй расчёты и числа
❌ НЕ предлагай менять формулы
✅ Фокус на СТИЛЬ, СТРУКТУРУ, ФОРМУЛИРОВКИ

ФОРМАТ ОТВЕТА (только JSON, без комментариев):
{{
  "score": 0.0-1.0,
  "issues": [
    "конкретная проблема 1",
    "конкретная проблема 2"
  ],
  "suggestions": [
    "как улучшить 1",
    "как улучшить 2"
  ]
}}"""
        
        return prompt
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Извлекает JSON из ответа DeepSeek (может содержать thinking теги)"""
        
        # Убираем thinking теги
        if "</think>" in response:
            parts = response.split("</think>")
            response = parts[-1].strip()
        
        # Убираем markdown обёртку
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        # Извлекаем JSON между первой { и последней }
        start = response.find("{")
        end = response.rfind("}")
        
        if start == -1 or end == -1:
            logger.warning("JSON не найден в ответе")
            return {
                "score": 0.5,
                "issues": ["Не удалось распарсить ответ Critic"],
                "suggestions": []
            }
        
        json_str = response[start:end+1]
        
        try:
            data = json.loads(json_str)
            
            # Валидация
            if "score" not in data:
                data["score"] = 0.5
            if "issues" not in data:
                data["issues"] = []
            if "suggestions" not in data:
                data["suggestions"] = []
            
            return data
        
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            logger.debug(f"JSON string: {json_str[:200]}...")
            return {
                "score": 0.5,
                "issues": ["Ошибка парсинга JSON ответа"],
                "suggestions": []
            }
    
    def _calculate_style_match(self, text: str) -> float:
        """Вычисляет style_match через similarity с эталоном"""
        similar = self.retriever.search(
            text[:300],  # Первые 300 символов
            top_k=5, 
            filter_etalon=True
        )
        
        if not similar:
            return 0.5
        
        avg_score = sum(c["score"] for c in similar) / len(similar)
        return round(avg_score, 2)
    
    def _analyze_structure(self, text: str) -> float:
        """Эвристический анализ структуры текста"""
        score = 1.0
        
        # Проверяем длину абзацев
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        if not paragraphs:
            return 0.3
        
        # Средняя длина абзаца
        avg_para_len = sum(len(p) for p in paragraphs) / len(paragraphs)
        
        # Оптимальная длина абзаца: 300-600 символов
        if avg_para_len < 100:
            score -= 0.2  # Слишком короткие
        elif avg_para_len > 1000:
            score -= 0.15  # Слишком длинные
        
        # Количество абзацев
        if len(paragraphs) < 2:
            score -= 0.3
        
        # Проверяем наличие формул (маркеры)
        if '[FORMULA]' in text or '[FIGURE]' in text or '[TABLE]' in text:
            score += 0.1  # Бонус за использование маркеров
        
        return max(0.0, min(1.0, score))
    
    def _determine_verdict(self, overall_score: float) -> str:
        """Определяет итоговый verdict на основе score"""
        if overall_score >= 0.9:
            return "отлично, почти как эталон"
        elif overall_score >= 0.8:
            return "хорошо, можно сдавать"
        elif overall_score >= 0.7:
            return "удовлетворительно, нужны правки"
        else:
            return "слабая работа, требуется доработка"
    
    def _build_summary(
        self, 
        overall_score: float, 
        weak_sections: List[str],
        section_results: Dict[str, Dict]
    ) -> str:
        """Формирует текстовое резюме анализа"""
        
        parts = []
        
        # Общая оценка
        if overall_score >= 0.85:
            parts.append("Работа выполнена на высоком уровне.")
        elif overall_score >= 0.75:
            parts.append("Работа выполнена хорошо.")
        elif overall_score >= 0.65:
            parts.append("Работа выполнена удовлетворительно.")
        else:
            parts.append("Работа требует существенной доработки.")
        
        # Соответствие стилю эталона
        avg_style = sum(r.get("style_match", 0.5) for r in section_results.values()) / len(section_results)
        
        if avg_style >= 0.8:
            parts.append("Стиль изложения соответствует эталону.")
        elif avg_style >= 0.7:
            parts.append("Стиль изложения близок к эталону.")
        else:
            parts.append("Стиль изложения требует улучшения.")
        
        # Слабые разделы
        if weak_sections:
            sections_str = ", ".join([f"'{s}'" for s in weak_sections])
            parts.append(f"Рекомендуется доработать разделы: {sections_str}.")
        else:
            parts.append("Все разделы выполнены на хорошем уровне.")
        
        return " ".join(parts)
