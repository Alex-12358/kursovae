"""Тесты для input_validator.py"""

import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.input_validator import validate_input


def test_valid_task():
    """Тест 1: валидный task.json → ok=True"""
    task_data = {
        "power": 10.0,  # кВт
        "rpm_input": 1450,  # об/мин
        "gear_ratio": 3.15,
        "load_type": "constant",
        "service_life": 10000,  # часы
        "material_pinion": "Сталь45",
        "material_gear": "Сталь45",
        "hardness_pinion": 200,  # HB
        "hardness_gear": 200  # HB
    }
    
    result = validate_input(task_data)
    
    assert result.valid is True
    assert len(result.errors) == 0


def test_missing_power():
    """Тест 2: отсутствует power → ok=False, errors содержит 'power'"""
    task_data = {
        "rpm_input": 1450,
        "gear_ratio": 3.15,
        "load_type": "constant",
        "service_life": 10000,
        "material_pinion": "Сталь45",
        "material_gear": "Сталь45",
        "hardness_pinion": 200,
        "hardness_gear": 200
    }
    
    result = validate_input(task_data)
    
    assert result.valid is False
    assert len(result.errors) > 0
    assert any("power" in error.lower() for error in result.errors)


def test_power_out_of_range():
    """Тест 3: power=99999 (вне диапазона) → ok=False, errors содержит 'power'"""
    task_data = {
        "power": 99999,  # Вне стандартного диапазона
        "rpm_input": 1450,
        "gear_ratio": 3.15,
        "load_type": "constant",
        "service_life": 10000,
        "material_pinion": "Сталь45",
        "material_gear": "Сталь45",
        "hardness_pinion": 200,
        "hardness_gear": 200
    }
    
    result = validate_input(task_data)
    
    # Валидация НЕ проходит из-за выхода за диапазон (строгая валидация)
    assert result.valid is False
    assert len(result.errors) > 0
    assert any("power" in error.lower() or "диапазон" in error.lower() for error in result.errors)

