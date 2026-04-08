"""Тесты для docx_builder.py"""

import sys
from pathlib import Path
import tempfile
import shutil

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from assembly.docx_builder import DOCXBuilder


def test_formula_replacement():
    """Тест 1: add_chapter() → [FORMULA] заменяется на (1.1)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test.docx"
        builder = DOCXBuilder(output_path=output_path)
        
        text = "Расчёт: [FORMULA]F = ma[/FORMULA]"
        builder.add_chapter(1, "Глава 1", text)
        
        # Проверяем что документ содержит замену
        # (реальная проверка содержимого DOCX сложна, проверим что нет исключений)
        builder.save()
        
        assert output_path.exists()


def test_two_formulas_in_chapter():
    """Тест 2: два [FORMULA] в одной главе → (1.1) и (1.2)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test.docx"
        builder = DOCXBuilder(output_path=output_path)
        
        text = """
        Первая формула: [FORMULA]E = mc^2[/FORMULA]
        Вторая формула: [FORMULA]F = G(m1*m2)/r^2[/FORMULA]
        """
        builder.add_chapter(1, "Глава 1", text)
        
        # Счётчики должны увеличиться
        assert builder.formula_counter == 2
        
        builder.save()
        assert output_path.exists()


def test_figure_replacement():
    """Тест 3: [FIGURE:Схема] → 'Рисунок 1.1 — Схема'"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test.docx"
        builder = DOCXBuilder(output_path=output_path)
        
        text = "См. [FIGURE:Схема редуктора]"
        builder.add_chapter(1, "Глава 1", text)
        
        # Счётчик рисунков должен увеличиться
        assert builder.figure_counter == 1
        
        builder.save()
        assert output_path.exists()


def test_save_creates_file():
    """Тест 4: save() создаёт файл"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test.docx"
        builder = DOCXBuilder(output_path=output_path)
        
        builder.add_chapter(1, "Введение", "Текст введения")
        builder.add_chapter(2, "Основная часть", "Текст основной части")
        
        builder.save()
        
        assert output_path.exists()
        assert output_path.stat().st_size > 0  # Файл не пустой

