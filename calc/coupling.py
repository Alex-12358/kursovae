"""
Подбор упругих муфт МУВП (муфта упругая втулочно-пальцевая).
Выбор по передаваемому крутящему моменту и диаметру вала.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def select_coupling(
    d: float,
    T: float,
    rpm: float = 1000,
    coupling_type: str = "МУВП"
) -> Dict[str, Any]:
    """
    Подбор упругой муфты по диаметру вала и крутящему моменту.
    
    Args:
        d: Диаметр вала, мм
        T: Передаваемый крутящий момент, Н·м
        rpm: Частота вращения, об/мин
        coupling_type: Тип муфты (МУВП, МЗ, др.)
    
    Returns:
        Словарь с параметрами муфты
    """
    logger.info(f"Подбор муфты {coupling_type} для d={d}мм, T={T}Н·м")
    
    # Расчётный момент с коэффициентом безопасности
    K = _get_safety_coefficient(rpm)
    T_calc = T * K
    
    logger.info(f"Расчётный момент: T_calc={T_calc:.1f}Н·м (K={K})")
    
    # Каталог муфт МУВП
    catalog = _get_muvp_catalog()
    
    # Подбор муфты
    coupling = _find_coupling_in_catalog(catalog, d, T_calc)
    
    if coupling:
        logger.info(f"Подобрана муфта: {coupling['designation']}, T_nom={coupling['T_nom']}Н·м")
        
        return {
            "designation": coupling["designation"],
            "T_nom": coupling["T_nom"],  # номинальный момент
            "d_min": coupling["d_min"],  # минимальный диаметр вала
            "d_max": coupling["d_max"],  # максимальный диаметр вала
            "D": coupling["D"],  # наружный диаметр
            "L": coupling["L"],  # длина муфты
            "mass": coupling["mass"],  # масса, кг
            "K": K,
            "T_calc": round(T_calc, 1),
            "safety_factor": round(coupling["T_nom"] / T, 2) if T else None,
            "trace": {
                "T": T,
                "T_calc": round(T_calc, 1),
                "K": K,
                "coupling_type": coupling_type,
                "status": "selected"
            }
        }
    else:
        logger.warning(f"Муфта не найдена в каталоге для d={d}мм, T={T_calc}Н·м")
        return _generate_approximate_coupling(d, T, T_calc, K, coupling_type)


def _get_safety_coefficient(rpm: float) -> float:
    """
    Определить коэффициент безопасности по режиму работы.
    
    Args:
        rpm: Частота вращения, об/мин
    
    Returns:
        Коэффициент безопасности K
    """
    # Упрощённо: для постоянной нагрузки K=1.3, для переменной K=1.5
    # Для высоких оборотов (>1500) увеличиваем
    
    if rpm > 2000:
        return 1.5
    elif rpm > 1500:
        return 1.4
    else:
        return 1.3


def _get_muvp_catalog() -> List[Dict[str, Any]]:
    """
    Каталог муфт МУВП.
    
    Данные из справочника "Детали машин" (Дунаев, Леликов).
    """
    return [
        # МУВП-1 ... МУВП-12
        {
            "designation": "МУВП-1",
            "T_nom": 6.3,  # Н·м
            "d_min": 9,
            "d_max": 16,
            "D": 50,
            "L": 66,
            "mass": 0.5
        },
        {
            "designation": "МУВП-2",
            "T_nom": 16,
            "d_min": 11,
            "d_max": 20,
            "D": 63,
            "L": 78,
            "mass": 0.8
        },
        {
            "designation": "МУВП-3",
            "T_nom": 31.5,
            "d_min": 14,
            "d_max": 25,
            "D": 80,
            "L": 92,
            "mass": 1.3
        },
        {
            "designation": "МУВП-4",
            "T_nom": 63,
            "d_min": 18,
            "d_max": 32,
            "D": 100,
            "L": 114,
            "mass": 2.2
        },
        {
            "designation": "МУВП-5",
            "T_nom": 125,
            "d_min": 22,
            "d_max": 40,
            "D": 125,
            "L": 142,
            "mass": 4.0
        },
        {
            "designation": "МУВП-6",
            "T_nom": 250,
            "d_min": 28,
            "d_max": 50,
            "D": 160,
            "L": 182,
            "mass": 7.5
        },
        {
            "designation": "МУВП-7",
            "T_nom": 500,
            "d_min": 35,
            "d_max": 63,
            "D": 200,
            "L": 222,
            "mass": 14
        },
        {
            "designation": "МУВП-8",
            "T_nom": 1000,
            "d_min": 45,
            "d_max": 80,
            "D": 250,
            "L": 282,
            "mass": 26
        },
        {
            "designation": "МУВП-9",
            "T_nom": 2000,
            "d_min": 55,
            "d_max": 100,
            "D": 315,
            "L": 350,
            "mass": 50
        },
        {
            "designation": "МУВП-10",
            "T_nom": 4000,
            "d_min": 70,
            "d_max": 125,
            "D": 400,
            "L": 430,
            "mass": 95
        },
    ]


def _find_coupling_in_catalog(
    catalog: List[Dict[str, Any]],
    d: float,
    T_calc: float
) -> Optional[Dict[str, Any]]:
    """
    Найти муфту в каталоге.
    
    Args:
        catalog: Список муфт
        d: Диаметр вала, мм
        T_calc: Расчётный момент, Н·м
    
    Returns:
        Муфта или None
    """
    # Фильтруем по диаметру
    suitable = [c for c in catalog if c["d_min"] <= d <= c["d_max"]]
    
    if not suitable:
        # Ищем ближайшую большую
        suitable = [c for c in catalog if c["d_max"] >= d]
    
    if not suitable:
        return None
    
    # Фильтруем по моменту
    suitable = [c for c in suitable if c["T_nom"] >= T_calc]
    
    if not suitable:
        return None
    
    # Выбираем муфту с минимальным моментом (экономичная)
    suitable.sort(key=lambda c: c["T_nom"])
    
    return suitable[0]


def _generate_approximate_coupling(
    d: float,
    T: float,
    T_calc: float,
    K: float,
    coupling_type: str
) -> Dict[str, Any]:
    """Сгенерировать приблизительные параметры муфты."""
    # Приблизительные оценки
    D = d * 6
    L = d * 8
    mass = (D / 100) ** 2 * 5  # грубая оценка
    
    return {
        "designation": f"{coupling_type}-приблизительно",
        "T_nom": int(T_calc * 1.2),
        "d_min": int(d * 0.8),
        "d_max": int(d * 1.2),
        "D": int(D),
        "L": int(L),
        "mass": round(mass, 1),
        "K": K,
        "T_calc": round(T_calc, 1),
        "safety_factor": 1.2,
        "trace": {
            "T": T,
            "T_calc": round(T_calc, 1),
            "K": K,
            "coupling_type": coupling_type,
            "status": "approximate"
        }
    }
