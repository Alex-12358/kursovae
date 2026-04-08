"""
Input Validator - проверка task.json до старта
Валидирует REQUIRED_PARAMS и PARAM_RANGES согласно ГОСТ
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# === ОБЯЗАТЕЛЬНЫЕ ПАРАМЕТРЫ ===
REQUIRED_PARAMS = [
    "power",  # Мощность, кВт
    "rpm_input",  # Обороты входного вала, об/мин
    "gear_ratio",  # Передаточное отношение
    "service_life",  # Срок службы, часы
    "load_type",  # Тип нагрузки: 'constant', 'variable', 'shock'
    "material_pinion",  # Материал шестерни
    "material_gear",  # Материал колеса
    "hardness_pinion",  # Твёрдость шестерни HB
    "hardness_gear"  # Твёрдость колеса HB
]

# === ДИАПАЗОНЫ ПАРАМЕТРОВ ===
PARAM_RANGES = {
    "power": (0.5, 500.0),  # кВт
    "rpm_input": (100, 3000),  # об/мин
    "gear_ratio": (1.5, 80.0),  # u (до 80 для червячных передач)
    "service_life": (1000, 50000),  # часы
    "hardness_pinion": (180, 450),  # HB (до 450 для HRC 45)
    "hardness_gear": (80, 350),  # HB (от 80 для бронзы)
    "z_pinion": (17, 150),  # количество зубьев (опционально)
    "z_gear": (30, 300),
    "beta": (8, 20),  # угол наклона зуба, град (опционально)
    "psi_ba": (0.2, 0.4)  # коэфф. ширины венца (опционально)
}

# === ДОПУСТИМЫЕ ЗНАЧЕНИЯ ===
VALID_LOAD_TYPES = ["constant", "variable", "shock"]
VALID_MATERIALS = [
    "Сталь45",
    "Сталь40Х",
    "Сталь20ХН2М",
    "Сталь40ХН",
    "Сталь12ХН3А",
    "БрА9Ж3Л",
    "БрО10Ф1",
    "БрА10Ж4Н4Л",
    "ЛАЖМц66-6-3-2"
]


@dataclass
class ValidationResult:
    """Результат валидации входных данных"""
    valid: bool
    errors: List[str]
    warnings: List[str]
    
    def __bool__(self) -> bool:
        return self.valid
    
    def report(self) -> str:
        """Форматированный отчёт о валидации"""
        lines = []
        if self.errors:
            lines.append("ОШИБКИ:")
            for error in self.errors:
                lines.append(f"  ❌ {error}")
        if self.warnings:
            lines.append("ПРЕДУПРЕЖДЕНИЯ:")
            for warning in self.warnings:
                lines.append(f"  ⚠️  {warning}")
        if self.valid and not self.warnings:
            lines.append("✓ Валидация пройдена успешно")
        return "\n".join(lines)


def validate_input(task_data: Dict[str, Any]) -> ValidationResult:
    """
    Валидирует task.json до старта расчётов
    
    Args:
        task_data: Словарь с параметрами задачи
        
    Returns:
        ValidationResult с результатами проверки
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    logger.info("Начало валидации входных параметров")
    
    # === 1. Проверка обязательных параметров ===
    for param in REQUIRED_PARAMS:
        if param not in task_data:
            errors.append(f"Отсутствует обязательный параметр: {param}")
            logger.error(f"Missing required parameter: {param}")
    
    if errors:
        # Если отсутствуют обязательные параметры, дальше не проверяем
        return ValidationResult(valid=False, errors=errors, warnings=warnings)
    
    # === 2. Проверка диапазонов ===
    for param, (min_val, max_val) in PARAM_RANGES.items():
        if param in task_data:
            value = task_data[param]
            if not isinstance(value, (int, float)):
                errors.append(f"Параметр {param} должен быть числом, получен {type(value).__name__}")
                logger.error(f"Invalid type for {param}: {type(value)}")
                continue
            
            if not (min_val <= value <= max_val):
                errors.append(
                    f"Параметр {param}={value} вне допустимого диапазона [{min_val}, {max_val}]"
                )
                logger.error(f"Parameter {param}={value} out of range [{min_val}, {max_val}]")
    
    # === 3. Проверка типа нагрузки ===
    load_type = task_data.get("load_type", "")
    if load_type not in VALID_LOAD_TYPES:
        errors.append(
            f"Недопустимый тип нагрузки: {load_type}. "
            f"Допустимые значения: {', '.join(VALID_LOAD_TYPES)}"
        )
        logger.error(f"Invalid load_type: {load_type}")
    
    # === 4. Проверка материалов ===
    for mat_param in ["material_pinion", "material_gear"]:
        material = task_data.get(mat_param, "")
        if material not in VALID_MATERIALS:
            errors.append(
                f"Недопустимый материал для {mat_param}: {material}. "
                f"Допустимые: {', '.join(VALID_MATERIALS)}"
            )
            logger.error(f"Invalid material for {mat_param}: {material}")
    
    # === 5. Проверка соотношений ===
    # Твёрдость шестерни должна быть >= твёрдости колеса
    hb_pinion = task_data.get("hardness_pinion", 0)
    hb_gear = task_data.get("hardness_gear", 0)
    if hb_pinion < hb_gear:
        warnings.append(
            f"Твёрдость шестерни ({hb_pinion} HB) меньше твёрдости колеса ({hb_gear} HB). "
            "Рекомендуется HB_pinion >= HB_gear"
        )
        logger.warning(f"Pinion hardness ({hb_pinion}) < gear hardness ({hb_gear})")
    
    # Передаточное отношение и числа зубьев (если указаны)
    if "z_pinion" in task_data and "z_gear" in task_data:
        z1 = task_data["z_pinion"]
        z2 = task_data["z_gear"]
        u_specified = task_data["gear_ratio"]
        u_calculated = z2 / z1
        
        if abs(u_calculated - u_specified) > 0.1:
            errors.append(
                f"Несоответствие передаточного отношения: "
                f"u={u_specified} (задано) vs u={u_calculated:.2f} (z2/z1)"
            )
            logger.error(f"Gear ratio mismatch: {u_specified} vs {u_calculated:.2f}")
    
    # === 6. Проверка мощности и оборотов ===
    power = task_data.get("power", 0)
    rpm = task_data.get("rpm_input", 0)
    if power > 0 and rpm > 0:
        torque = 9550 * power / rpm  # Н·м
        if torque > 50000:
            warnings.append(
                f"Очень большой крутящий момент ({torque:.0f} Н·м). "
                "Проверьте корректность входных данных."
            )
            logger.warning(f"Very high torque: {torque:.0f} Nm")
    
    # === 7. Логирование результата ===
    valid = len(errors) == 0
    if valid:
        logger.info(f"Валидация завершена успешно. Предупреждений: {len(warnings)}")
    else:
        logger.error(f"Валидация провалена. Ошибок: {len(errors)}, предупреждений: {len(warnings)}")
    
    return ValidationResult(valid=valid, errors=errors, warnings=warnings)
