"""
Расчёт валов по ГОСТ Р 54395-2011 и упрощённой методике.
Определяет диаметры участков вала из крутящего момента и изгиба.
"""

import logging
import math
from typing import Dict, Any

logger = logging.getLogger(__name__)


def calculate_shaft(task_data: Dict[str, Any], gear_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Расчёт диаметров вала.
    
    Упрощённый расчёт по допускаемым напряжениям:
    - Диаметр из крутящего момента: d = (16*T / (π*[τ]))^(1/3)
    - Диаметр из изгиба и кручения: d = (32*M_экв / (π*[σ_и]))^(1/3)
    
    Args:
        task_data: Исходные данные из task.json
        gear_result: Результаты расчёта зубчатой передачи
    
    Returns:
        Словарь с расчётными диаметрами вала и trace
    """
    logger.info("Расчёт вала по упрощённой методике")
    
    # Исходные данные
    T1 = gear_result.get("T1", 0)  # Крутящий момент на шестерне, Н·м
    T2 = gear_result.get("T2", 0)  # Крутящий момент на колесе, Н·м
    
    # Материал вала - принимаем Сталь45 улучшенная
    material = task_data.get("material_pinion", "Сталь45")
    
    # Допускаемые напряжения для Сталь45 улучшенной
    MATERIAL_PROPS = {
        "Сталь45": {"sigma_b": 600, "tau_allow": 30, "sigma_i_allow": 60},
        "Сталь40Х": {"sigma_b": 750, "tau_allow": 35, "sigma_i_allow": 70},
        "Сталь20ХН2М": {"sigma_b": 900, "tau_allow": 40, "sigma_i_allow": 80},
    }
    
    props = MATERIAL_PROPS.get(material, MATERIAL_PROPS["Сталь45"])
    tau_allow = props["tau_allow"]  # МПа
    sigma_i_allow = props["sigma_i_allow"]  # МПа
    
    # === РАСЧЁТ ДИАМЕТРОВ ===
    
    # 1. Диаметр под шестерню (входной вал)
    # Только крутящий момент T1
    d_gear_min = _diameter_from_torque(T1, tau_allow)
    d_gear_seat = _round_to_standard(d_gear_min)
    
    logger.info(f"Диаметр под шестерню: d_min={d_gear_min:.1f}мм → d={d_gear_seat}мм")
    
    # 2. Диаметр под подшипники (обычно на 5-10мм меньше)
    d_bearing_seat = _round_to_standard(d_gear_seat - 5)
    
    # 3. Диаметр под муфту (равен или немного больше диаметра под шестерню)
    d_coupling_seat = d_gear_seat
    
    # 4. Концевой участок (меньше диаметра подшипника)
    d_end = _round_to_standard(d_bearing_seat - 5)
    
    # 5. Диаметр под колесо (выходной вал, момент T2)
    d_wheel_min = _diameter_from_torque(T2, tau_allow)
    d_wheel_seat = _round_to_standard(d_wheel_min)
    
    logger.info(f"Диаметр под колесо: d_min={d_wheel_min:.1f}мм → d={d_wheel_seat}мм")
    
    # === ПРОВЕРКА НА ПРОЧНОСТЬ ===
    
    # Касательное напряжение в опасном сечении
    W_p = math.pi * d_gear_seat**3 / 16  # мм³
    tau_actual = T1 * 1000 / W_p  # МПа
    safety_tau = tau_allow / tau_actual if tau_actual > 0 else 999
    
    logger.info(f"Проверка прочности: τ={tau_actual:.1f} МПа, [τ]={tau_allow} МПа, S={safety_tau:.2f}")
    
    result = {
        "d_gear_seat": d_gear_seat,  # диаметр посадочного места шестерни
        "d_bearing_seat": d_bearing_seat,  # диаметр посадки подшипника
        "d_coupling_seat": d_coupling_seat,  # диаметр посадки муфты
        "d_end": d_end,  # диаметр концевого участка
        "d_wheel_seat": d_wheel_seat,  # диаметр посадочного места колеса (выходной вал)
        "material": material,
        "tau_actual": round(tau_actual, 2),
        "tau_allow": tau_allow,
        "safety_factor": round(safety_tau, 2),
        "trace": {
            "method": "simplified_torque_based",
            "T1": T1,
            "T2": T2,
            "tau_allow": tau_allow,
            "d_gear_min": round(d_gear_min, 2),
            "d_wheel_min": round(d_wheel_min, 2),
            "W_p": round(W_p, 1),
            "tau_actual": round(tau_actual, 2),
            "safety_factor": round(safety_tau, 2),
            "status": "calculated"
        }
    }
    
    return result


def _diameter_from_torque(T: float, tau_allow: float) -> float:
    """
    Расчёт минимального диаметра вала из условия прочности при кручении.
    
    d = (16 * T / (π * [τ]))^(1/3)
    
    Args:
        T: Крутящий момент, Н·м
        tau_allow: Допускаемое напряжение кручения, МПа
    
    Returns:
        Минимальный диаметр, мм
    """
    if T <= 0 or tau_allow <= 0:
        return 10.0
    
    # T в Н·м → Н·мм
    T_nmm = T * 1000
    
    # d³ = 16*T / (π*[τ])
    d_cubed = (16 * T_nmm) / (math.pi * tau_allow)
    d = d_cubed ** (1/3)
    
    return d


def _round_to_standard(d: float) -> int:
    """
    Округлить диаметр до стандартного ряда по ГОСТ 6636-69.
    
    Стандартный ряд диаметров: ..., 17, 20, 22, 25, 28, 30, 32, 35, 38, 40, 42, 45, 48, 50, ...
    
    Args:
        d: Расчётный диаметр, мм
    
    Returns:
        Стандартный диаметр, мм
    """
    standard_diameters = [
        10, 12, 14, 16, 17, 18, 19, 20, 22, 24, 25, 26, 28, 30,
        32, 35, 36, 38, 40, 42, 45, 48, 50, 52, 55, 58, 60, 63,
        65, 68, 70, 72, 75, 78, 80, 85, 90, 95, 100, 105, 110, 120
    ]
    
    # Находим ближайший больший стандартный диаметр
    for std_d in standard_diameters:
        if std_d >= d:
            return std_d
    
    # Если больше максимального, округляем до кратного 5
    return int(math.ceil(d / 5) * 5)


def calculate_shaft_lengths(gear_params: Dict[str, Any]) -> Dict[str, float]:
    """
    Определить длины участков вала.
    
    Упрощённая методика на основе ширины зубчатого венца.
    
    Args:
        gear_params: Параметры зубчатой передачи
    
    Returns:
        Словарь с длинами участков
    """
    b_w = gear_params.get("b_w", 50)  # ширина венца
    
    return {
        "L_coupling": 100,  # длина посадки под муфту
        "L_transition": 20,  # длина переходного участка
        "L_bearing": 23,  # длина посадки подшипника (зависит от типа)
        "L_gear": b_w + 10,  # длина посадки зубчатого колеса (с запасом)
        "L_end": 30  # длина концевого участка
    }
