"""
Расчёт цилиндрической косозубой передачи по ГОСТ 21354
Включает проверку контактной и изгибной прочности
"""
import json
import logging
import math
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Загрузка коэффициентов из JSON
GOST_TABLES_DIR = Path(__file__).parent / "gost_tables"
COEFFS_PATH = GOST_TABLES_DIR / "gear_coeffs.json"

with open(COEFFS_PATH, "r", encoding="utf-8") as f:
    COEFFS = json.load(f)

logger.info(f"Загружены коэффициенты ГОСТ из {COEFFS_PATH}")


def calculate_gear(task_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Расчёт геометрии и прочности косозубой передачи
    
    Args:
        task_params: Параметры из task.json:
            - power: мощность, кВт
            - rpm_input: обороты входного вала, об/мин
            - gear_ratio: передаточное отношение u
            - material_pinion, material_gear: материалы
            - hardness_pinion, hardness_gear: твёрдость HB
            - beta (опц): угол наклона зуба, град
            - psi_ba (опц): коэфф. ширины венца
            
    Returns:
        Словарь с расчётными параметрами:
        {
            "m": модуль,
            "z1": число зубьев шестерни,
            "z2": число зубьев колеса,
            "a_w": межосевое расстояние,
            "b_w": ширина венца,
            "d1": делительный диаметр шестерни,
            "d2": делительный диаметр колеса,
            "beta": угол наклона,
            "sigma_h": контактное напряжение,
            "sigma_f1": изгибное напряжение шестерни,
            "sigma_f2": изгибное напряжение колеса,
            "safety_h": запас прочности по контакту,
            "safety_f": запас прочности по изгибу,
            "trace": отладочная информация
        }
    """
    logger.info("=== НАЧАЛО РАСЧЁТА ЗУБЧАТОЙ ПЕРЕДАЧИ ===")
    
    # === Извлечение параметров ===
    P = task_params["power"]  # кВт
    n1 = task_params["rpm_input"]  # об/мин
    u = task_params["gear_ratio"]
    mat1 = task_params["material_pinion"]
    mat2 = task_params["material_gear"]
    hb1 = task_params["hardness_pinion"]
    hb2 = task_params["hardness_gear"]
    
    # Опциональные параметры
    beta = task_params.get("beta", COEFFS["beta_default"])  # град
    psi_ba = task_params.get("psi_ba", COEFFS["psi_ba_default"])
    
    logger.info(f"Входные: P={P}кВт, n1={n1}об/мин, u={u}, β={beta}°, ψ_ba={psi_ba}")
    
    # === Крутящий момент ===
    T1 = 9550 * P / n1  # Н·м
    n2 = n1 / u
    T2 = T1 * u
    
    logger.info(f"Моменты: T1={T1:.2f}Н·м, T2={T2:.2f}Н·м, n2={n2:.1f}об/мин")
    
    # === Допускаемые напряжения ===
    sigma_h_lim1, sigma_f_lim1 = _durability_factor(mat1, hb1)
    sigma_h_lim2, sigma_f_lim2 = _durability_factor(mat2, hb2)
    
    # Допускаемое контактное напряжение (берём меньшее)
    sigma_hp = min(sigma_h_lim1, sigma_h_lim2)
    logger.info(f"[σ_H]={sigma_hp:.0f}МПа (min из {sigma_h_lim1:.0f}, {sigma_h_lim2:.0f})")
    
    # === Предварительное межосевое расстояние ===
    # Формула по Шейнблит А.Е. "Курсовое проектирование деталей машин", стр. 62
    # K_a = 43 для косозубых, K_a = 49.5 для прямозубых
    K_a = 43.0 if beta > 0 else 49.5  # коэфф. для стальных колёс
    K_Hbeta = 1.05  # коэфф. концентрации нагрузки
    
    # Формула: a_w = K_a * (u+1) * cbrt(T1 * K_H / (psi_ba * u * [σ_H]^2))
    # T1 в Н·м, sigma_hp в МПа, результат a_w в мм
    a_w_prelim = K_a * (u + 1) * (T1 * 1000 * K_Hbeta / (psi_ba * u * sigma_hp ** 2)) ** (1/3)
    a_w = _round_aw(a_w_prelim)
    
    logger.info(f"Межосевое расстояние: a_w={a_w}мм (предв. {a_w_prelim:.2f})")
    
    # === Модуль ===
    # m = 2 * a_w * cos(beta) / (z1 + z2)
    # Но сначала выбираем z1 из условия отсутствия подрезания (z1 >= 17)
    z1_prelim = max(COEFFS["z_pinion_min"], 17)
    z2_prelim = round(z1_prelim * u)
    z_sum_prelim = z1_prelim + z2_prelim
    
    m_prelim = 2 * a_w * math.cos(math.radians(beta)) / z_sum_prelim
    m = _std_module(m_prelim)
    
    logger.info(f"Модуль: m={m}мм (предв. {m_prelim:.3f})")
    
    # === Числа зубьев ===
    z_sum = 2 * a_w * math.cos(math.radians(beta)) / m
    z1 = round(z_sum / (u + 1))
    z2 = round(z_sum - z1)
    
    # Корректировка для минимальных значений
    z1 = max(z1, COEFFS["z_pinion_min"])
    z2 = max(z2, COEFFS["z_gear_min"])
    u_fact = z2 / z1  # фактическое передаточное число
    
    logger.info(f"Числа зубьев: z1={z1}, z2={z2}, фактическое u={u_fact:.3f}")
    
    # === Геометрия ===
    d1 = m * z1 / math.cos(math.radians(beta))
    d2 = m * z2 / math.cos(math.radians(beta))
    b_w = psi_ba * a_w
    
    logger.info(f"Диаметры: d1={d1:.2f}мм, d2={d2:.2f}мм")
    logger.info(f"Ширина венца: b_w={b_w:.2f}мм")
    
    # === Проверка контактной прочности ===
    # По Шейнблит А.Е., стр. 65: σ_H = K * sqrt(F_t * K_Hα * K_Hβ * (u+1) / (b * d1 * u))
    # K = 376 для косозубых, K = 436 для прямозубых
    K_sigma = 376 if beta > 0 else 436
    
    # Коэффициенты нагрузки (табл. 4.2, 4.3 Шейнблит)
    K_Ha = 1.0 if beta == 0 else 1.05  # распределение нагрузки между зубьями
    K_Hb = 1.05  # концентрация нагрузки по ширине
    K_Hv = 1.05  # динамическая нагрузка (для v < 5 м/с)
    
    # Окружная сила
    F_t = 2 * T1 * 1000 / d1  # Н (T1 в Нм, d1 в мм)
    
    # σ_H = K * sqrt(F_t * K_H * (u+1) / (b_w * d1 * u))
    K_H_total = K_Ha * K_Hb * K_Hv
    sigma_h = K_sigma * math.sqrt(F_t * K_H_total * (u_fact + 1) / (b_w * d1 * u_fact))
    
    safety_h = sigma_hp / sigma_h
    logger.info(f"Контактное напряжение: σ_H={sigma_h:.1f}МПа, запас={safety_h:.2f}")
    
    # === Проверка изгибной прочности ===
    Y_F1 = 3.8  # коэфф. формы зуба (упрощённо)
    Y_F2 = 3.6
    K_F = 1.35
    
    sigma_f1 = 2 * T1 * 1000 * K_F * Y_F1 / (d1 * b_w * m)
    sigma_f2 = sigma_f1 * (z1 / z2) * (Y_F2 / Y_F1)
    
    safety_f1 = sigma_f_lim1 / sigma_f1
    safety_f2 = sigma_f_lim2 / sigma_f2
    safety_f = min(safety_f1, safety_f2)
    
    logger.info(f"Изгибные напряжения: σ_F1={sigma_f1:.1f}МПа, σ_F2={sigma_f2:.1f}МПа")
    logger.info(f"Запасы по изгибу: S_F1={safety_f1:.2f}, S_F2={safety_f2:.2f}")
    
    # === Результат ===
    result = {
        "m": m,
        "z1": z1,
        "z2": z2,
        "a_w": a_w,
        "b_w": round(b_w, 2),
        "d1": round(d1, 2),
        "d2": round(d2, 2),
        "beta": beta,
        "sigma_h": round(sigma_h, 1),
        "sigma_f1": round(sigma_f1, 1),
        "sigma_f2": round(sigma_f2, 1),
        "safety_h": round(safety_h, 2),
        "safety_f": round(safety_f, 2),
        "trace": {
            "T1": round(T1, 2),
            "T2": round(T2, 2),
            "n2": round(n2, 1),
            "sigma_hp": sigma_hp,
            "a_w_prelim": round(a_w_prelim, 2),
            "m_prelim": round(m_prelim, 3),
            "z_sum": round(z_sum, 1),
            "materials": {"pinion": mat1, "gear": mat2},
            "hardness": {"pinion": hb1, "gear": hb2}
        }
    }
    
    logger.info("=== РАСЧЁТ ПЕРЕДАЧИ ЗАВЕРШЁН ===")
    return result


def _durability_factor(material: str, hardness: float) -> Tuple[float, float]:
    """
    Вычислить допускаемые напряжения с учётом долговечности
    
    Args:
        material: Название материала
        hardness: Твёрдость HB
        
    Returns:
        (sigma_h_lim, sigma_f_lim) - МПа
    """
    sigma_h_base = COEFFS["sigma_h_lim"].get(material, 550)
    sigma_f_base = COEFFS["sigma_f_lim"].get(material, 380)
    
    # Поправка на твёрдость (упрощённо)
    k_hb = hardness / 250  # нормализация относительно средней твёрдости
    
    sigma_h_lim = sigma_h_base * k_hb * COEFFS["K_Hb"]
    sigma_f_lim = sigma_f_base * k_hb * COEFFS["K_Fb"]
    
    logger.debug(f"Материал {material}, HB={hardness}: σ_Hlim={sigma_h_lim:.0f}, σ_Flim={sigma_f_lim:.0f}")
    
    return sigma_h_lim, sigma_f_lim


def _std_module(m_prelim: float) -> float:
    """
    Округлить до стандартного модуля ГОСТ 9563
    
    Args:
        m_prelim: Предварительный модуль
        
    Returns:
        Стандартный модуль (ближайший больший)
    """
    std_modules = COEFFS["standard_modules"]
    for m_std in std_modules:
        if m_std >= m_prelim:
            return m_std
    return std_modules[-1]


def _round_aw(a_w_prelim: float) -> float:
    """
    Округлить межосевое расстояние до стандартного ряда
    
    Args:
        a_w_prelim: Предварительное значение
        
    Returns:
        Округлённое значение по ряду Ra40
    """
    # Стандартный ряд Ra40 для межосевых расстояний (упрощённо)
    std_aw = [
        63, 71, 80, 90, 100, 112, 125, 140, 160, 180, 200,
        224, 250, 280, 315, 355, 400, 450, 500
    ]
    
    for aw in std_aw:
        if aw >= a_w_prelim:
            return aw
    
    # Если больше максимального, округляем вверх до кратного 50
    return math.ceil(a_w_prelim / 50) * 50
