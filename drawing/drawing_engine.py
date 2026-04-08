"""
Drawing Engine для Course Generator v5.
Генерация чертежей в DXF формате через ezdxf.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

try:
    import ezdxf
    from ezdxf import units
    from ezdxf.enums import TextEntityAlignment
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False
    ezdxf = None

from config import OUTPUT_DIR

logger = logging.getLogger(__name__)


class DrawingEngine:
    """
    Генератор чертежей в DXF.
    
    - shaft_drawing: чертёж вала по размерной цепи
    - gear_drawing: чертёж зубчатого колеса
    - assembly_drawing: сборочный чертёж
    - title_block: основная надпись по ГОСТ 2.104
    """
    
    def __init__(self, output_dir: Optional[Path] = None):
        self._output_dir = output_dir or OUTPUT_DIR / "drawings"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        
        if not EZDXF_AVAILABLE:
            logger.warning("ezdxf не установлен. Чертежи будут заглушками.")
    
    def shaft_drawing(self, dim_chain_params: Dict) -> str:
        """
        Создать чертёж вала по параметрам размерной цепи.
        
        Args:
            dim_chain_params: Словарь с секциями вала
                {
                    "sections": [
                        {"name": "coupling", "length": 50, "diameter": 30},
                        {"name": "bearing1", "length": 20, "diameter": 35},
                        ...
                    ],
                    "total_length": 200
                }
        
        Returns:
            Путь к сгенерированному .dxf файлу
        """
        output_path = self._output_dir / "shaft.dxf"
        
        if not EZDXF_AVAILABLE:
            # Создаём пустой файл-заглушку
            output_path.write_text("// Shaft drawing placeholder - ezdxf not installed")
            logger.warning(f"Создана заглушка чертежа вала: {output_path}")
            return str(output_path)
        
        doc = ezdxf.new("R2010")
        doc.units = units.MM
        msp = doc.modelspace()
        
        sections = dim_chain_params.get("sections", [])
        
        # Масштаб и начальная позиция
        scale = 1.0
        x_offset = 50
        y_center = 100
        
        current_x = x_offset
        
        for section in sections:
            length = section.get("length", 50) * scale
            diameter = section.get("diameter", 30) * scale
            radius = diameter / 2
            
            # Рисуем прямоугольник (сечение вала)
            # Верхняя половина (для симметрии)
            points = [
                (current_x, y_center),
                (current_x, y_center + radius),
                (current_x + length, y_center + radius),
                (current_x + length, y_center),
            ]
            msp.add_lwpolyline(points)
            
            # Нижняя половина
            points_bottom = [
                (current_x, y_center),
                (current_x, y_center - radius),
                (current_x + length, y_center - radius),
                (current_x + length, y_center),
            ]
            msp.add_lwpolyline(points_bottom)
            
            # Размерные линии
            self._add_dimension(msp, current_x, current_x + length, y_center + radius + 10, length / scale)
            
            # Подпись секции
            name = section.get("name", "")
            if name:
                msp.add_text(
                    name,
                    dxfattribs={"height": 3, "layer": "TEXT"}
                ).set_placement((current_x + length/2, y_center - radius - 15), align=TextEntityAlignment.MIDDLE_CENTER)
            
            current_x += length
        
        # Осевая линия
        msp.add_line(
            (x_offset - 20, y_center),
            (current_x + 20, y_center),
            dxfattribs={"linetype": "CENTER", "layer": "AXIS"}
        )
        
        # Основная надпись
        self._add_title_block(msp, "Вал", "ГГТУ.КП.001")
        
        doc.saveas(str(output_path))
        logger.info(f"Чертёж вала создан: {output_path}")
        
        return str(output_path)
    
    def gear_drawing(self, gear_params: Dict) -> str:
        """
        Создать чертёж зубчатого колеса.
        
        Args:
            gear_params: Параметры зубчатого колеса из calc
                {
                    "m": 2.5,        # модуль
                    "z": 80,         # число зубьев
                    "d": 200,        # делительный диаметр
                    "da": 205,       # диаметр вершин
                    "df": 193.75,    # диаметр впадин
                    "b": 50          # ширина венца
                }
        
        Returns:
            Путь к сгенерированному .dxf файлу
        """
        output_path = self._output_dir / "gear.dxf"
        
        if not EZDXF_AVAILABLE:
            output_path.write_text("// Gear drawing placeholder - ezdxf not installed")
            logger.warning(f"Создана заглушка чертежа колеса: {output_path}")
            return str(output_path)
        
        doc = ezdxf.new("R2010")
        doc.units = units.MM
        msp = doc.modelspace()
        
        # Параметры колеса
        m = gear_params.get("m", 2.5)
        z = gear_params.get("z2", gear_params.get("z", 80))
        d = gear_params.get("d2", z * m)  # делительный диаметр
        da = d + 2 * m  # диаметр вершин
        df = d - 2.5 * m  # диаметр впадин
        b = gear_params.get("b2", gear_params.get("b", 50))
        
        # Масштаб для вписывания в формат
        scale = min(200 / da, 1.0)
        
        center_x = 150
        center_y = 150
        
        # Вид сбоку (слева)
        side_x = 50
        
        # Окружность вершин
        msp.add_circle((center_x, center_y), da/2 * scale, dxfattribs={"layer": "CONTOUR"})
        
        # Делительная окружность (штрих-пунктир)
        msp.add_circle((center_x, center_y), d/2 * scale, dxfattribs={"layer": "PITCH", "linetype": "DASHDOT"})
        
        # Окружность впадин
        msp.add_circle((center_x, center_y), df/2 * scale, dxfattribs={"layer": "CONTOUR"})
        
        # Отверстие под вал (примерно d/5)
        bore = d / 5
        msp.add_circle((center_x, center_y), bore/2 * scale, dxfattribs={"layer": "CONTOUR"})
        
        # Вид сбоку - прямоугольник
        half_da = da/2 * scale
        half_b = b/2 * scale
        
        points = [
            (side_x - half_b, center_y - half_da),
            (side_x + half_b, center_y - half_da),
            (side_x + half_b, center_y + half_da),
            (side_x - half_b, center_y + half_da),
            (side_x - half_b, center_y - half_da),
        ]
        msp.add_lwpolyline(points, close=True, dxfattribs={"layer": "CONTOUR"})
        
        # Осевые линии
        msp.add_line(
            (center_x - half_da - 10, center_y),
            (center_x + half_da + 10, center_y),
            dxfattribs={"linetype": "CENTER", "layer": "AXIS"}
        )
        msp.add_line(
            (center_x, center_y - half_da - 10),
            (center_x, center_y + half_da + 10),
            dxfattribs={"linetype": "CENTER", "layer": "AXIS"}
        )
        
        # Таблица параметров
        table_x = 250
        table_y = 200
        params_text = [
            f"m = {m}",
            f"z = {z}",
            f"d = {d:.1f}",
            f"da = {da:.1f}",
            f"df = {df:.2f}",
            f"b = {b}",
        ]
        
        for i, text in enumerate(params_text):
            msp.add_text(
                text,
                dxfattribs={"height": 3.5, "layer": "TEXT"}
            ).set_placement((table_x, table_y - i * 7), align=TextEntityAlignment.LEFT)
        
        # Основная надпись
        self._add_title_block(msp, "Колесо зубчатое", "ГГТУ.КП.002")
        
        doc.saveas(str(output_path))
        logger.info(f"Чертёж зубчатого колеса создан: {output_path}")
        
        return str(output_path)
    
    def assembly_drawing(self, calc_params: Dict) -> str:
        """
        Создать сборочный чертёж редуктора.
        
        Args:
            calc_params: Все расчётные параметры
        
        Returns:
            Путь к .dxf файлу
        """
        output_path = self._output_dir / "assembly.dxf"
        
        if not EZDXF_AVAILABLE:
            output_path.write_text("// Assembly drawing placeholder")
            return str(output_path)
        
        doc = ezdxf.new("R2010")
        doc.units = units.MM
        msp = doc.modelspace()
        
        # Заглушка — прямоугольник корпуса
        msp.add_lwpolyline([
            (50, 50),
            (250, 50),
            (250, 200),
            (50, 200),
            (50, 50)
        ], close=True)
        
        msp.add_text(
            "Сборочный чертёж (заглушка)",
            dxfattribs={"height": 5}
        ).set_placement((150, 125), align=TextEntityAlignment.MIDDLE_CENTER)
        
        self._add_title_block(msp, "Редуктор. Сборочный чертёж", "ГГТУ.КП.000 СБ")
        
        doc.saveas(str(output_path))
        logger.info(f"Сборочный чертёж создан: {output_path}")
        
        return str(output_path)
    
    def _add_dimension(
        self,
        msp,
        x1: float,
        x2: float,
        y: float,
        value: float
    ) -> None:
        """Добавить линейный размер."""
        if not EZDXF_AVAILABLE:
            return
        
        # Размерная линия
        msp.add_line((x1, y), (x2, y), dxfattribs={"layer": "DIMENSION"})
        
        # Выносные линии
        msp.add_line((x1, y - 5), (x1, y + 2), dxfattribs={"layer": "DIMENSION"})
        msp.add_line((x2, y - 5), (x2, y + 2), dxfattribs={"layer": "DIMENSION"})
        
        # Стрелки (упрощённо — линиями)
        arrow_len = 3
        msp.add_line((x1, y), (x1 + arrow_len, y + 1), dxfattribs={"layer": "DIMENSION"})
        msp.add_line((x1, y), (x1 + arrow_len, y - 1), dxfattribs={"layer": "DIMENSION"})
        msp.add_line((x2, y), (x2 - arrow_len, y + 1), dxfattribs={"layer": "DIMENSION"})
        msp.add_line((x2, y), (x2 - arrow_len, y - 1), dxfattribs={"layer": "DIMENSION"})
        
        # Текст размера
        msp.add_text(
            f"{value:.0f}",
            dxfattribs={"height": 2.5, "layer": "DIMENSION"}
        ).set_placement(((x1 + x2) / 2, y + 2), align=TextEntityAlignment.BOTTOM_CENTER)
    
    def _add_title_block(
        self,
        msp,
        title: str,
        designation: str,
        scale: str = "1:1",
        sheet: str = "1"
    ) -> None:
        """
        Добавить основную надпись по ГОСТ 2.104.
        
        Упрощённая версия — прямоугольник с текстом.
        """
        if not EZDXF_AVAILABLE:
            return
        
        # Позиция (правый нижний угол формата A3)
        x = 185
        y = 5
        width = 185
        height = 55
        
        # Рамка основной надписи
        msp.add_lwpolyline([
            (x, y),
            (x + width, y),
            (x + width, y + height),
            (x, y + height),
            (x, y)
        ], close=True, dxfattribs={"layer": "TITLE_BLOCK"})
        
        # Горизонтальные линии
        for dy in [5, 10, 15, 20, 25, 40]:
            msp.add_line((x, y + dy), (x + width, y + dy), dxfattribs={"layer": "TITLE_BLOCK"})
        
        # Вертикальные линии (упрощённо)
        for dx in [70, 90, 110, 130, 150]:
            msp.add_line((x + dx, y), (x + dx, y + 15), dxfattribs={"layer": "TITLE_BLOCK"})
        
        # Текст
        # Наименование
        msp.add_text(
            title,
            dxfattribs={"height": 5, "layer": "TITLE_TEXT"}
        ).set_placement((x + width/2, y + 32), align=TextEntityAlignment.MIDDLE_CENTER)
        
        # Обозначение
        msp.add_text(
            designation,
            dxfattribs={"height": 3.5, "layer": "TITLE_TEXT"}
        ).set_placement((x + width/2, y + 22), align=TextEntityAlignment.MIDDLE_CENTER)
        
        # Масштаб
        msp.add_text(
            f"М {scale}",
            dxfattribs={"height": 3, "layer": "TITLE_TEXT"}
        ).set_placement((x + 100, y + 7), align=TextEntityAlignment.MIDDLE_CENTER)
        
        # Лист
        msp.add_text(
            sheet,
            dxfattribs={"height": 3, "layer": "TITLE_TEXT"}
        ).set_placement((x + 140, y + 7), align=TextEntityAlignment.MIDDLE_CENTER)
        
        # Дата
        date_str = datetime.now().strftime("%d.%m.%Y")
        msp.add_text(
            date_str,
            dxfattribs={"height": 2.5, "layer": "TITLE_TEXT"}
        ).set_placement((x + 160, y + 7), align=TextEntityAlignment.MIDDLE_CENTER)
        
        # Учебное заведение
        msp.add_text(
            "ГГТУ им. П.О.Сухого",
            dxfattribs={"height": 2.5, "layer": "TITLE_TEXT"}
        ).set_placement((x + width/2, y + 47), align=TextEntityAlignment.MIDDLE_CENTER)
