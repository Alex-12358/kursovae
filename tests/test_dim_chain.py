"""Тесты для dim_chain.py"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from calc.dim_chain import DimChain, ShaftSection


def test_add_total_length():
    """Тест 1: add() → total_length считается правильно"""
    chain = DimChain()
    
    chain.add(ShaftSection("coupling", length=50, diameter=30))
    chain.add(ShaftSection("bearing1", length=20, diameter=35))
    chain.add(ShaftSection("gear", length=60, diameter=40))
    
    assert chain.total_length() == 130
    assert len(chain.sections) == 3


def test_zero_length_validation():
    """Тест 2: секция с L=0 → validate() возвращает ошибку"""
    chain = DimChain()
    
    chain.add(ShaftSection("coupling", length=50, diameter=30))
    
    # ShaftSection с length=0 выбросит ValueError в __post_init__
    try:
        chain.add(ShaftSection("invalid", length=0, diameter=35))
        assert False, "Должно было выброситься исключение"
    except ValueError as e:
        assert "длина" in str(e).lower() or "должна" in str(e).lower()


def test_to_drawing_params():
    """Тест 3: to_drawing_params() → возвращает список секций"""
    chain = DimChain()
    
    chain.add(ShaftSection("coupling", length=50, diameter=30))
    chain.add(ShaftSection("bearing1", length=20, diameter=35))
    chain.add(ShaftSection("gear", length=60, diameter=40))
    
    params = chain.to_drawing_params()
    
    # Возвращается список
    assert isinstance(params, list)
    assert len(params) == 3
    
    # Проверяем что каждая секция имеет нужные поля
    for section in params:
        assert "name" in section
        assert "length" in section
        assert "diameter" in section
        assert "position" in section
        assert "position_end" in section
    
    # Проверяем первую секцию
    first = params[0]
    assert first["name"] == "coupling"
    assert first["length"] == 50
    assert first["diameter"] == 30
    assert first["position"] == 0
    assert first["position_end"] == 50
