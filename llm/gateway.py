"""
LLM Gateway - обёртка над Ollama HTTP API
Retry логика, логирование, обработка ошибок
"""
import json
import logging
import time
import asyncio
import aiohttp
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Retry параметры
RETRY_COUNT = 3
RETRY_DELAYS = [1, 2, 4]  # экспоненциальная задержка
REQUEST_TIMEOUT = 600  # 10 минут для генерации


class OllamaGateway:
    """
    Gateway для взаимодействия с Ollama HTTP API
    Поддержка generate и chat, retry логика
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 11434):
        """
        Args:
            host: Хост Ollama
            port: Порт Ollama
        """
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        logger.info(f"Инициализирован OllamaGateway: {self.base_url}")
    
    async def generate(
        self,
        model: str,
        prompt: str,
        **kwargs
    ) -> str:
        """
        Генерация текста через /api/generate
        
        Args:
            model: Имя модели
            prompt: Промпт
            **kwargs: Дополнительные параметры (temperature, top_p, max_tokens)
            
        Returns:
            Сгенерированный текст
        """
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,  # не используем стриминг
            "options": {}
        }
        
        # Добавить параметры
        if "temperature" in kwargs:
            payload["options"]["temperature"] = kwargs["temperature"]
        if "top_p" in kwargs:
            payload["options"]["top_p"] = kwargs["top_p"]
        if "max_tokens" in kwargs:
            payload["options"]["num_predict"] = kwargs["max_tokens"]
        
        logger.info(f"Generate запрос: model={model}, prompt_len={len(prompt)}")
        start_time = time.time()
        
        # Retry логика
        for attempt in range(RETRY_COUNT):
            try:
                timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            text = data.get("response", "")
                            
                            # Логируем сырой ответ
                            logger.debug(f"Generate RAW response: {text[:1000]}...")
                            
                            elapsed = time.time() - start_time
                            logger.info(
                                f"Generate успешно: model={model}, "
                                f"output_len={len(text)}, time={elapsed:.2f}s"
                            )
                            
                            return text
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"Generate ошибка HTTP {response.status}: {error_text}"
                            )
                            
                            if attempt < RETRY_COUNT - 1:
                                delay = RETRY_DELAYS[attempt]
                                logger.info(f"Повтор через {delay}s (попытка {attempt + 1}/{RETRY_COUNT})")
                                await asyncio.sleep(delay)
                            else:
                                raise RuntimeError(f"Generate провалился после {RETRY_COUNT} попыток")
            
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error(f"Ошибка сети/таймаут при generate: {type(e).__name__}: {e}")
                
                if attempt < RETRY_COUNT - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.info(f"Повтор через {delay}s (попытка {attempt + 1}/{RETRY_COUNT})")
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(f"Generate провалился после {RETRY_COUNT} попыток: {e}") from e
            
            except Exception as e:
                logger.error(f"Неожиданная ошибка при generate: {type(e).__name__}: {e}")
                
                if attempt < RETRY_COUNT - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.info(f"Повтор через {delay}s (попытка {attempt + 1}/{RETRY_COUNT})")
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(f"Generate провалился после {RETRY_COUNT} попыток: {e}") from e
        
        raise RuntimeError("Generate провалился")
    
    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """
        Чат через /api/chat (streaming режим)
        
        Args:
            model: Имя модели
            messages: Список сообщений [{"role": "user", "content": "..."}]
            **kwargs: Дополнительные параметры
            
        Returns:
            Ответ ассистента
        """
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,  # Включаем streaming
            "options": {}
        }
        
        # Добавить параметры
        if "temperature" in kwargs:
            payload["options"]["temperature"] = kwargs["temperature"]
        if "top_p" in kwargs:
            payload["options"]["top_p"] = kwargs["top_p"]
        if "max_tokens" in kwargs:
            payload["options"]["num_predict"] = kwargs["max_tokens"]
        
        logger.info(f"Chat запрос (streaming): model={model}, messages={len(messages)}")
        logger.debug(f"Chat payload: {json.dumps(payload, ensure_ascii=False, indent=2)[:500]}...")
        start_time = time.time()
        
        # Retry логика
        for attempt in range(RETRY_COUNT):
            try:
                # Увеличенный таймаут: нет лимита на общее время, 30s на подключение, 300s (5 мин) на чтение каждого chunk
                timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=300)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    logger.debug(f"Отправка POST запроса на {url}...")
                    async with session.post(url, json=payload) as response:
                        logger.debug(f"Получен HTTP {response.status}")
                        if response.status == 200:
                            logger.debug("Начинаем читать streaming ответ...")
                            
                            full_text = ""
                            chunk_count = 0
                            
                            # Читаем streaming ответ построчно
                            async for line in response.content:
                                if not line:
                                    continue
                                
                                try:
                                    # Каждая строка — JSON объект
                                    chunk = json.loads(line.decode('utf-8'))
                                    
                                    # Извлекаем контент из chunk
                                    if "message" in chunk:
                                        content = chunk["message"].get("content", "")
                                        if content:
                                            full_text += content
                                            chunk_count += 1
                                    
                                    # Проверяем флаг завершения
                                    if chunk.get("done", False):
                                        logger.debug(f"Streaming завершён: chunks={chunk_count}")
                                        break
                                        
                                except json.JSONDecodeError:
                                    # Пропускаем невалидные строки
                                    continue
                            
                            elapsed = time.time() - start_time
                            
                            # Логируем сырой ответ
                            logger.info(f"Chat RAW response ({model}): {full_text[:2000]}")
                            logger.info(
                                f"Chat успешно: model={model}, "
                                f"output_len={len(full_text)}, chunks={chunk_count}, time={elapsed:.2f}s"
                            )
                            
                            return full_text
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"Chat ошибка HTTP {response.status}: {error_text}"
                            )
                            
                            if attempt < RETRY_COUNT - 1:
                                delay = RETRY_DELAYS[attempt]
                                logger.info(f"Повтор через {delay}s (попытка {attempt + 1}/{RETRY_COUNT})")
                                await asyncio.sleep(delay)
                            else:
                                raise RuntimeError(f"Chat провалился после {RETRY_COUNT} попыток")
            
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error(f"Ошибка сети/таймаут при chat: {type(e).__name__}: {e}")
                
                if attempt < RETRY_COUNT - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.info(f"Повтор через {delay}s (попытка {attempt + 1}/{RETRY_COUNT})")
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(f"Chat провалился после {RETRY_COUNT} попыток: {e}") from e
            
            except Exception as e:
                logger.error(f"Неожиданная ошибка при chat: {type(e).__name__}: {e}")
                
                if attempt < RETRY_COUNT - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.info(f"Повтор через {delay}s (попытка {attempt + 1}/{RETRY_COUNT})")
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(f"Chat провалился после {RETRY_COUNT} попыток: {e}") from e
        
        raise RuntimeError("Chat провалился")
