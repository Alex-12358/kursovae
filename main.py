#!/usr/bin/env python3
"""
Course Generator v5 — Главная точка входа.

Использование:
    python main.py task.json
    python main.py task.json --resume session_20240401_120000
    python main.py --list-sessions
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import BASE_DIR, OUTPUT_DIR, LOG_DIR, LOG_LEVEL
from core.input_validator import validate_input
from core.orchestrator import Orchestrator, run_orchestrator


def setup_logging() -> None:
    """Настроить логирование."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Формат логов
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Файловый handler
    file_handler = logging.FileHandler(
        LOG_DIR / "course_generator.log",
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    # Консольный handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def parse_args() -> argparse.Namespace:
    """Парсинг аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="Course Generator v5 — Генератор курсовых работ по деталям машин",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python main.py task.json                    # Запуск генерации
  python main.py task.json --resume ID        # Восстановление сессии
  python main.py --list-sessions              # Список сессий
  python main.py task.json --validate-only    # Только валидация
        """
    )
    
    parser.add_argument(
        "task",
        nargs="?",
        type=Path,
        help="Путь к файлу задания (task.json)"
    )
    
    parser.add_argument(
        "--resume",
        type=str,
        metavar="SESSION_ID",
        help="Восстановить выполнение с указанной сессии"
    )
    
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="Показать список доступных сессий"
    )
    
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Только проверить task.json без генерации"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Подробный вывод"
    )
    
    return parser.parse_args()


def list_sessions() -> None:
    """Показать список доступных сессий."""
    orchestrator = Orchestrator()
    sessions = orchestrator.list_sessions()
    
    if not sessions:
        print("Нет сохранённых сессий.")
        return
    
    print("\nДоступные сессии:")
    print("-" * 60)
    
    for session in sessions:
        session_id = session["session_id"]
        last_update = session["last_update"]
        statuses = session.get("node_statuses", {})
        
        done_count = sum(1 for s in statuses.values() if s == "done")
        total_count = len(statuses)
        
        print(f"  {session_id}")
        print(f"    Обновлено: {last_update}")
        print(f"    Прогресс: {done_count}/{total_count} узлов")
        print()


def validate_task(task_path: Path) -> bool:
    """Валидировать task.json."""
    import json
    
    print(f"\nВалидация: {task_path}")
    print("-" * 40)
    
    if not task_path.exists():
        print(f"✗ Файл не найден: {task_path}")
        return False
    
    try:
        with open(task_path, "r", encoding="utf-8") as f:
            task_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"✗ Ошибка JSON: {e}")
        return False
    
    result = validate_input(task_data)
    
    if result.valid:
        print("✓ Валидация пройдена")
        if result.warnings:
            print("\nПредупреждения:")
            for warning in result.warnings:
                print(f"  ⚠ {warning}")
        return True
    else:
        print("✗ Валидация не пройдена")
        print("\nОшибки:")
        for error in result.errors:
            print(f"  ✗ {error}")
        return False


async def main() -> int:
    """Главная функция."""
    args = parse_args()
    
    # Настройка логирования
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Список сессий
    if args.list_sessions:
        list_sessions()
        return 0
    
    # Проверка наличия task файла
    if not args.task and not args.resume:
        print("Ошибка: укажите путь к task.json или --resume SESSION_ID")
        print("Используйте --help для справки")
        return 1
    
    # Если только resume — путь к task может отсутствовать
    task_path = args.task or Path("task.json")
    
    # Только валидация
    if args.validate_only:
        return 0 if validate_task(task_path) else 1
    
    # Валидация перед запуском (если не resume)
    if not args.resume:
        if not validate_task(task_path):
            return 1
    
    # Запуск генерации
    try:
        result_path = await run_orchestrator(task_path, resume=args.resume)
        
        if result_path.exists():
            print(f"\n✓ Генерация завершена: {result_path}")
            return 0
        else:
            print(f"\n⚠ Файл не создан: {result_path}")
            return 1
            
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем (Ctrl+C)")
        print("Используйте --resume для продолжения")
        return 130
        
    except Exception as e:
        logger.exception("Критическая ошибка")
        print(f"\n✗ Ошибка: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
