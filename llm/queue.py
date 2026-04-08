"""
LLM Queue - приоритетная очередь для LLM запросов
Rate limiting, управление параллелизмом
"""
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from enum import IntEnum

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """Приоритеты задач"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2


@dataclass(order=True)
class LLMTask:
    """
    Задача для LLM
    """
    priority: int = field(compare=True)
    task_type: str = field(compare=False)
    payload: dict = field(compare=False)
    callback: Optional[Callable] = field(default=None, compare=False)
    task_id: str = field(default="", compare=False)
    
    def __post_init__(self):
        if not self.task_id:
            import uuid
            self.task_id = str(uuid.uuid4())[:8]


class LLMQueue:
    """
    Приоритетная очередь для LLM запросов
    Управляет rate limiting и порядком выполнения
    """
    
    def __init__(self, rate_limit_seconds: float = 1.0):
        """
        Args:
            rate_limit_seconds: Минимальный интервал между запросами (секунды)
        """
        self.queue = asyncio.PriorityQueue()
        self.rate_limit = rate_limit_seconds
        self.last_request_time = 0.0
        self.running = False
        logger.info(f"Инициализирована LLMQueue, rate_limit={rate_limit_seconds}s")
    
    async def enqueue(
        self,
        task_type: str,
        payload: dict,
        priority: Priority = Priority.NORMAL,
        callback: Optional[Callable] = None
    ) -> str:
        """
        Добавить задачу в очередь
        
        Args:
            task_type: Тип задачи ('planner', 'writer', 'critic')
            payload: Данные задачи
            priority: Приоритет
            callback: Функция обратного вызова (опционально)
            
        Returns:
            ID задачи
        """
        task = LLMTask(
            priority=priority,
            task_type=task_type,
            payload=payload,
            callback=callback
        )
        
        await self.queue.put(task)
        logger.debug(
            f"Задача добавлена в очередь: id={task.task_id}, "
            f"type={task_type}, priority={priority.name}"
        )
        
        return task.task_id
    
    async def dequeue(self) -> Optional[LLMTask]:
        """
        Извлечь задачу из очереди с учётом rate limit
        
        Returns:
            LLMTask или None если очередь пуста
        """
        if self.queue.empty():
            return None
        
        # Rate limiting
        import time
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit:
            wait_time = self.rate_limit - time_since_last
            logger.debug(f"Rate limit: ожидание {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        task = await self.queue.get()
        self.last_request_time = time.time()
        
        logger.debug(
            f"Задача извлечена из очереди: id={task.task_id}, "
            f"type={task.task_type}, priority={task.priority}"
        )
        
        return task
    
    def size(self) -> int:
        """
        Получить размер очереди
        
        Returns:
            Количество задач в очереди
        """
        return self.queue.qsize()
    
    def is_empty(self) -> bool:
        """
        Проверить, пуста ли очередь
        
        Returns:
            True если пуста
        """
        return self.queue.empty()
    
    async def process_queue(self, worker_func: Callable):
        """
        Обработать очередь с помощью worker функции
        
        Args:
            worker_func: Async функция для обработки задачи (task) -> result
        """
        self.running = True
        logger.info("Запуск обработки очереди")
        
        while self.running:
            if self.is_empty():
                await asyncio.sleep(0.5)  # ждём новые задачи
                continue
            
            task = await self.dequeue()
            if task is None:
                continue
            
            try:
                logger.info(f"Обработка задачи {task.task_id} ({task.task_type})")
                result = await worker_func(task)
                
                # Callback
                if task.callback:
                    try:
                        if asyncio.iscoroutinefunction(task.callback):
                            await task.callback(result)
                        else:
                            task.callback(result)
                    except Exception as e:
                        logger.error(f"Ошибка в callback для задачи {task.task_id}: {e}")
                
                logger.info(f"Задача {task.task_id} завершена")
            
            except Exception as e:
                logger.error(f"Ошибка обработки задачи {task.task_id}: {e}")
    
    def stop(self):
        """
        Остановить обработку очереди
        """
        logger.info("Остановка очереди")
        self.running = False
