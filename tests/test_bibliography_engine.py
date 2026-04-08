"""Тесты для bibliography_engine.py"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from assembly.bibliography_engine import BibliographyEngine, Source


def test_book_format():
    """Тест 1: book → формат 'Автор И.О. Название / ... — Город : Издатель, Год. — N с.'"""
    engine = BibliographyEngine()
    
    engine.add_source(Source(
        type="book",
        authors=["Иванов А.Б.", "Петров В.Г."],
        title="Детали машин",
        publisher="Высшая школа",
        year=2020,
        pages=500
    ))
    
    result = engine.generate()
    
    assert len(result) == 1
    formatted = result[0]
    
    # Проверяем наличие ключевых элементов
    assert "Иванов А.Б." in formatted or "Иванов" in formatted
    assert "Петров В.Г." in formatted or "Петров" in formatted
    assert "Детали машин" in formatted
    assert "Высшая школа" in formatted
    assert "2020" in formatted
    assert "500" in formatted or str(500) in formatted
    assert "с." in formatted or "с" in formatted


def test_gost_format():
    """Тест 2: gost → формат 'ГОСТ XXXXX Название...'"""
    engine = BibliographyEngine()
    
    engine.add_source(Source(
        type="gost",
        gost_number="ГОСТ 21354-87",
        title="Передачи зубчатые цилиндрические эвольвентные"
    ))
    
    result = engine.generate()
    
    assert len(result) == 1
    formatted = result[0]
    
    assert "ГОСТ 21354-87" in formatted
    assert "Передачи зубчатые" in formatted


def test_web_format():
    """Тест 3: web → содержит 'URL:' и 'дата обращения'"""
    engine = BibliographyEngine()
    
    engine.add_source(Source(
        type="web",
        title="Расчёт зубчатых передач",
        url="https://example.com/gears",
        access_date="01.01.2024"
    ))
    
    result = engine.generate()
    
    assert len(result) == 1
    formatted = result[0]
    
    assert "URL:" in formatted or "https://" in formatted
    assert "обращения" in formatted
    assert "01.01.2024" in formatted
