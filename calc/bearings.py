"""
Подбор подшипников качения по каталогу ГОСТ 8338-75.
Расчёт динамической грузоподъёмности и ресурса.
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

from config import GOST_TABLES_DIR

logger = logging.getLogger(__name__)

# Путь к каталогу подшипников
BEARINGS_CATALOG_PATH = GOST_TABLES_DIR / "bearings_catalog.json"


def select_bearing(
    d: float,
    radial_load: float,
    rpm: float,
    life_hours: float = 10000,
    bearing_type: str = "radial_ball"
) -> Dict[str, Any]:
    """
    Подбор подшипника по диаметру вала и нагрузке.
    
    Args:
        d: Диаметр вала, мм
        radial_load: Радиальная нагрузка, Н
        rpm: Частота вращения, об/мин
        life_hours: Требуемый ресурс, часы
        bearing_type: Тип подшипника ('radial_ball', 'radial_roller')
    
    Returns:
        Словарь с параметрами подобранного подшипника
    """
    logger.info(f"Подбор подшипника: d={d}мм, Fr={radial_load}Н, n={rpm}об/мин")
    
    # Загружаем каталог
    catalog = _load_bearings_catalog()
    
    # Расчёт требуемой динамической грузоподъёмности
    C_required = _calculate_required_capacity(radial_load, rpm, life_hours)
    
    logger.info(f"Требуемая грузоподъёмность: C={C_required:.0f} Н")
    
    # Подбор из каталога
    bearing = _find_bearing_in_catalog(catalog, d, C_required, bearing_type)
    
    if bearing:
        logger.info(f"Подобран подшипник: {bearing['designation']}, C={bearing['C']} Н")
        
        # Расчёт фактического ресурса
        actual_life_hours = _calculate_bearing_life(bearing["C"], radial_load, rpm)
        
        return {
            "designation": bearing["designation"],
            "d": bearing["d"],  # внутренний диаметр
            "D": bearing["D"],  # наружный диаметр
            "B": bearing["B"],  # ширина
            "C": bearing["C"],  # динамическая грузоподъёмность
            "C0": bearing["C0"],  # статическая грузоподъёмность
            "type": bearing_type,
            "C_required": round(C_required, 0),
            "actual_life_hours": round(actual_life_hours, 0),
            "safety_factor": round(bearing["C"] / C_required, 2) if C_required else None,
            "trace": {
                "radial_load": radial_load,
                "rpm": rpm,
                "life_hours_required": life_hours,
                "life_hours_actual": round(actual_life_hours, 0),
                "status": "selected"
            }
        }
    else:
        logger.warning(f"Подшипник не найден в каталоге для d={d}мм, C={C_required}Н")
        
        # Возвращаем приблизительные данные
        return _generate_approximate_bearing(d, C_required, bearing_type, radial_load, rpm, life_hours)


def _calculate_required_capacity(Fr: float, n: float, Lh: float) -> float:
    """
    Расчёт требуемой динамической грузоподъёмности.
    
    C = Fr * (60 * n * Lh / 10^6)^(1/p)
    
    где p = 3 для шариковых подшипников, p = 10/3 для роликовых
    
    Args:
        Fr: Радиальная нагрузка, Н
        n: Частота вращения, об/мин
        Lh: Требуемый ресурс, часы
    
    Returns:
        Требуемая динамическая грузоподъёмность, Н
    """
    p = 3  # показатель степени для шариковых подшипников
    
    # Количество оборотов за срок службы
    L = 60 * n * Lh / 1e6  # млн оборотов
    
    # C = Fr * L^(1/p)
    C = Fr * (L ** (1/p))
    
    return C


def _calculate_bearing_life(C: float, Fr: float, n: float) -> float:
    """
    Расчёт фактического ресурса подшипника.
    
    Lh = (C / Fr)^p * 10^6 / (60 * n)
    
    Args:
        C: Динамическая грузоподъёмность, Н
        Fr: Радиальная нагрузка, Н
        n: Частота вращения, об/мин
    
    Returns:
        Ресурс, часы
    """
    p = 3
    
    if Fr <= 0 or n <= 0:
        return 999999
    
    L = (C / Fr) ** p  # млн оборотов
    Lh = L * 1e6 / (60 * n)  # часы
    
    return Lh


def _load_bearings_catalog() -> List[Dict[str, Any]]:
    """Загрузить каталог подшипников из JSON."""
    if not BEARINGS_CATALOG_PATH.exists():
        logger.warning(f"Каталог подшипников не найден: {BEARINGS_CATALOG_PATH}")
        return _get_default_catalog()
    
    try:
        with open(BEARINGS_CATALOG_PATH, "r", encoding="utf-8") as f:
            catalog = json.load(f)
        logger.debug(f"Загружено подшипников из каталога: {len(catalog)}")
        return catalog
    except Exception as e:
        logger.error(f"Ошибка загрузки каталога подшипников: {e}")
        return _get_default_catalog()


def _get_default_catalog() -> List[Dict[str, Any]]:
    """Встроенный каталог наиболее распространённых подшипников."""
    return [
        # Лёгкая серия (ГОСТ 8338-75)
        {"designation": "204", "d": 20, "D": 47, "B": 14, "C": 12800, "C0": 6200},
        {"designation": "205", "d": 25, "D": 52, "B": 15, "C": 14000, "C0": 6900},
        {"designation": "206", "d": 30, "D": 62, "B": 16, "C": 19500, "C0": 10000},
        {"designation": "207", "d": 35, "D": 72, "B": 17, "C": 25500, "C0": 13700},
        {"designation": "208", "d": 40, "D": 80, "B": 18, "C": 32000, "C0": 17800},
        {"designation": "209", "d": 45, "D": 85, "B": 19, "C": 33200, "C0": 18600},
        {"designation": "210", "d": 50, "D": 90, "B": 20, "C": 35100, "C0": 19600},
        {"designation": "211", "d": 55, "D": 100, "B": 21, "C": 43600, "C0": 25000},
        {"designation": "212", "d": 60, "D": 110, "B": 22, "C": 52700, "C0": 31000},
        
        # Средняя серия
        {"designation": "305", "d": 25, "D": 62, "B": 17, "C": 22500, "C0": 11200},
        {"designation": "306", "d": 30, "D": 72, "B": 19, "C": 28100, "C0": 15300},
        {"designation": "307", "d": 35, "D": 80, "B": 21, "C": 33200, "C0": 18000},
        {"designation": "308", "d": 40, "D": 90, "B": 23, "C": 41000, "C0": 22400},
        {"designation": "309", "d": 45, "D": 100, "B": 25, "C": 52700, "C0": 28000},
        {"designation": "310", "d": 50, "D": 110, "B": 27, "C": 61800, "C0": 34000},
    ]


def _find_bearing_in_catalog(
    catalog: List[Dict[str, Any]],
    d: float,
    C_required: float,
    bearing_type: str
) -> Optional[Dict[str, Any]]:
    """
    Найти подшипник в каталоге.
    
    Args:
        catalog: Список подшипников
        d: Требуемый внутренний диаметр, мм
        C_required: Требуемая грузоподъёмность, Н
        bearing_type: Тип подшипника
    
    Returns:
        Подшипник или None
    """
    # Фильтруем по диаметру (точное совпадение или ближайший больший)
    suitable = [b for b in catalog if b["d"] >= d - 2]
    
    if not suitable:
        return None
    
    # Фильтруем по грузоподъёмности
    suitable = [b for b in suitable if b["C"] >= C_required]
    
    if not suitable:
        return None
    
    # Выбираем подшипник с минимальным d и минимальным C (экономичный)
    suitable.sort(key=lambda b: (b["d"], b["C"]))
    
    return suitable[0]


def _generate_approximate_bearing(
    d: float,
    C: float,
    bearing_type: str,
    Fr: float,
    rpm: float,
    life_hours: float
) -> Dict[str, Any]:
    """Сгенерировать приблизительные параметры подшипника."""
    # Приблизительные соотношения для лёгкой серии
    D = d * 2.5
    B = d * 0.5
    
    return {
        "designation": f"~{int(d)}",
        "d": int(d),
        "D": int(D),
        "B": int(B),
        "C": int(C * 1.2),  # с запасом
        "C0": int(C * 0.6),
        "type": bearing_type,
        "C_required": round(C, 0),
        "actual_life_hours": int(life_hours * 1.1),
        "safety_factor": 1.2,
        "trace": {
            "radial_load": Fr,
            "rpm": rpm,
            "life_hours_required": life_hours,
            "status": "approximate"
        }
    }
