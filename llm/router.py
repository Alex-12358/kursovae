"""
LLM Router - маршрутизация запросов к моделям с fallback
Проверяет доступность Ollama, выбирает модель по роли
"""
import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# MODEL ROUTING (из config.py, но дублируем)
MODEL_ROUTING_V1 = {
    "model": "qwen-course",
    "temperature": 0.7,
    "top_p": 0.9,
    "max_tokens": 4096,
    "role": "writer"
}

MODEL_ROUTING_V2 = {
    "model": "deepseek-course",
    "temperature": 0.3,
    "top_p": 0.95,
    "max_tokens": 8192,
    "role": "planner_critic"
}

OLLAMA_TIMEOUT = 2  # секунды для проверки доступности


async def get_client_with_fallback(
    host: str = "127.0.0.1",
    port: int = 11434,
    fallback_host: str = "localhost"
) -> tuple[str, int]:
    """
    Проверить доступность Ollama и вернуть рабочий хост
    
    Args:
        host: Основной хост
        port: Порт Ollama
        fallback_host: Резервный хост
        
    Returns:
        (рабочий_хост, порт)
    """
    logger.info(f"Проверка доступности Ollama: {host}:{port}")
    
    # Попытка подключиться к основному хосту
    if await _check_ollama_available(host, port):
        logger.info(f"Ollama доступен на {host}:{port}")
        return (host, port)
    
    # Fallback на localhost
    logger.warning(f"Ollama недоступен на {host}:{port}, пробуем {fallback_host}:{port}")
    if await _check_ollama_available(fallback_host, port):
        logger.info(f"Ollama доступен на {fallback_host}:{port}")
        return (fallback_host, port)
    
    # Если оба недоступны
    logger.error("Ollama недоступен ни на основном хосте, ни на fallback")
    raise ConnectionError(f"Не удалось подключиться к Ollama на {host}:{port} или {fallback_host}:{port}")


async def _check_ollama_available(host: str, port: int) -> bool:
    """
    Проверить доступность Ollama через /api/tags
    
    Args:
        host: Хост
        port: Порт
        
    Returns:
        True если доступен, False иначе
    """
    url = f"http://{host}:{port}/api/tags"
    
    try:
        timeout = aiohttp.ClientTimeout(total=OLLAMA_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    models = data.get("models", [])
                    logger.debug(f"Ollama на {host}:{port} доступен, моделей: {len(models)}")
                    return True
                else:
                    logger.debug(f"Ollama на {host}:{port} вернул статус {response.status}")
                    return False
    except asyncio.TimeoutError:
        logger.debug(f"Таймаут при подключении к {host}:{port}")
        return False
    except Exception as e:
        logger.debug(f"Ошибка подключения к {host}:{port}: {e}")
        return False


def get_model_config(role: str) -> Dict[str, Any]:
    """
    Получить конфигурацию модели по роли
    
    Args:
        role: Роль ('writer', 'planner_critic')
        
    Returns:
        Словарь с параметрами модели
    """
    if role == "writer":
        logger.debug(f"Выбрана модель для Writer: {MODEL_ROUTING_V1['model']}")
        return MODEL_ROUTING_V1.copy()
    elif role == "planner_critic":
        logger.debug(f"Выбрана модель для Planner/Critic: {MODEL_ROUTING_V2['model']}")
        return MODEL_ROUTING_V2.copy()
    else:
        logger.warning(f"Неизвестная роль '{role}', используем V1 по умолчанию")
        return MODEL_ROUTING_V1.copy()


def get_model_name(role: str) -> str:
    """
    Получить имя модели по роли
    
    Args:
        role: Роль
        
    Returns:
        Имя модели
    """
    config = get_model_config(role)
    return config["model"]
