"""
Расчёт шпоночных соединений по ГОСТ 23360-78.
Проверка прочности шпонки на смятие и срез.
"""

import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


def calculate_key(
    d: float,
    T: float,
    L: float = None,
    material: str = "Сталь45"
) -> Dict[str, Any]:
    """
    Расчёт призматической шпонки по ГОСТ 23360-78.
    
    Проверка на смятие:
        σ_см = 2*T / (d * h * L_p) ≤ [σ_см]
    
    Проверка на срез:
        τ_ср = 2*T / (d * b * L_p) ≤ [τ_ср]
    
    Args:
        d: Диаметр вала, мм
        T: Передаваемый крутящий момент, Н·м
        L: Длина шпонки, мм (если None - принимается 0.8*L_ступицы)
        material: Материал шпонки
    
    Returns:
        Словарь с параметрами шпонки и результатами проверки
    """
    logger.info(f"Расчёт шпонки для d={d}мм, T={T}Н·м")
    
    # Подбор сечения шпонки b×h по диаметру вала (ГОСТ 23360-78)
    b, h, t1, t2 = _select_key_dimensions(d)
    
    logger.info(f"Выбрано сечение шпонки: b={b}мм, h={h}мм")
    
    # Длина шпонки
    if L is None:
        # Принимаем длину шпонки равной 80% от ширины ступицы
        # (ступица обычно на 10-15мм больше ширины зубчатого венца)
        L = max(b * 4, 20)  # минимум 20мм или 4*b
    
    L_work = L - b  # рабочая длина шпонки (минус фаски)
    
    # Допускаемые напряжения
    MATERIAL_PROPS = {
        "Сталь45": {"sigma_cm": 100, "tau_sr": 60},  # МПа
        "Сталь40Х": {"sigma_cm": 120, "tau_sr": 70},
    }
    
    props = MATERIAL_PROPS.get(material, MATERIAL_PROPS["Сталь45"])
    sigma_cm_allow = props["sigma_cm"]
    tau_sr_allow = props["tau_sr"]
    
    # === ПРОВЕРКА НА СМЯТИЕ ===
    
    # Глубина врезания в вал
    h_work = t1  # рабочая высота (глубина в ступице)
    
    # σ_см = 2*T*1000 / (d * h_work * L_work)
    sigma_cm = (2 * T * 1000) / (d * h_work * L_work) if L_work > 0 else 999
    
    safety_cm = sigma_cm_allow / sigma_cm if sigma_cm > 0 else 999
    
    logger.info(f"Проверка на смятие: σ_см={sigma_cm:.1f} МПа, [σ_см]={sigma_cm_allow} МПа, S={safety_cm:.2f}")
    
    # === ПРОВЕРКА НА СРЕЗ ===
    
    # τ_ср = 2*T*1000 / (d * b * L_work)
    tau_sr = (2 * T * 1000) / (d * b * L_work) if L_work > 0 else 999
    
    safety_sr = tau_sr_allow / tau_sr if tau_sr > 0 else 999
    
    logger.info(f"Проверка на срез: τ_ср={tau_sr:.1f} МПа, [τ_ср]={tau_sr_allow} МПа, S={safety_sr:.2f}")
    
    # Проверка условий прочности
    is_valid_cm = sigma_cm <= sigma_cm_allow
    is_valid_sr = tau_sr <= tau_sr_allow
    is_valid = is_valid_cm and is_valid_sr
    
    status = "passed" if is_valid else "failed"
    
    if not is_valid:
        logger.warning(f"Шпонка НЕ проходит проверку прочности! Увеличьте L или b×h")
    
    return {
        "b": b,  # ширина шпонки
        "h": h,  # высота шпонки
        "L": L,  # полная длина шпонки
        "L_work": L_work,  # рабочая длина
        "t1": t1,  # глубина паза в валу
        "t2": t2,  # глубина паза в ступице
        "material": material,
        "sigma_cm": round(sigma_cm, 1),
        "sigma_cm_allow": sigma_cm_allow,
        "tau_sr": round(tau_sr, 1),
        "tau_sr_allow": tau_sr_allow,
        "safety_factor_cm": round(safety_cm, 2),
        "safety_factor_sr": round(safety_sr, 2),
        "is_valid": is_valid,
        "trace": {
            "d": d,
            "T": T,
            "b_x_h": f"{b}x{h}",
            "sigma_cm": round(sigma_cm, 1),
            "tau_sr": round(tau_sr, 1),
            "status": status
        }
    }


def _select_key_dimensions(d: float) -> Tuple[int, int, int, int]:
    """
    Выбор размеров призматической шпонки по диаметру вала.
    
    ГОСТ 23360-78, таблица 1 (упрощённо).
    
    Args:
        d: Диаметр вала, мм
    
    Returns:
        (b, h, t1, t2) - ширина, высота, глубина паза в валу, глубина в ступице
    """
    # Таблица размеров шпонок (диапазон d, b, h, t1, t2)
    KEY_TABLE = [
        (6, 10, 2, 2, 1.2, 1.0),
        (10, 12, 3, 3, 1.8, 1.4),
        (12, 17, 4, 4, 2.5, 1.8),
        (17, 22, 5, 5, 3.0, 2.3),
        (22, 30, 6, 6, 3.5, 2.8),
        (30, 38, 8, 7, 4.0, 3.3),
        (38, 44, 10, 8, 5.0, 3.3),
        (44, 50, 12, 8, 5.0, 3.3),
        (50, 58, 14, 9, 5.5, 3.8),
        (58, 65, 16, 10, 6.0, 4.3),
        (65, 75, 18, 11, 7.0, 4.4),
        (75, 85, 20, 12, 7.5, 4.9),
        (85, 95, 22, 14, 9.0, 5.4),
        (95, 110, 25, 14, 9.0, 5.4),
        (110, 130, 28, 16, 10.0, 6.4),
    ]
    
    for d_min, d_max, b, h, t1, t2 in KEY_TABLE:
        if d_min <= d <= d_max:
            return (b, h, t1, t2)
    
    # Если диаметр больше максимального
    if d > 130:
        b = int(d * 0.2)
        h = int(b * 0.6)
        t1 = int(h * 0.6)
        t2 = int(h * 0.4)
        return (b, h, t1, t2)
    
    # Если диаметр меньше минимального
    return (2, 2, 1.2, 1.0)
