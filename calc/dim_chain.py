"""
Размерная цепь (Dimension Chain)
Используется для расчёта длин участков вала и валидации сборки
"""
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ShaftSection:
    """Участок вала"""
    name: str  # Название участка (напр. "bearing_1", "gear", "coupling")
    length: float  # Длина, мм
    diameter: float  # Диаметр, мм
    tolerance: float = 0.0  # Допуск, мм
    
    def __post_init__(self):
        if self.length <= 0:
            raise ValueError(f"Длина участка {self.name} должна быть положительной: {self.length}")
        if self.diameter <= 0:
            raise ValueError(f"Диаметр участка {self.name} должен быть положительным: {self.diameter}")


class DimChain:
    """
    Размерная цепь для вала
    Управляет участками вала и их последовательностью
    """
    
    def __init__(self, shaft_name: str = "main_shaft"):
        self.shaft_name = shaft_name
        self.sections: List[ShaftSection] = []
        logger.info(f"Создана размерная цепь для вала: {shaft_name}")
    
    def add(self, section: ShaftSection) -> "DimChain":
        """
        Добавить участок вала
        
        Args:
            section: Объект ShaftSection
            
        Returns:
            self для цепочечных вызовов
        """
        self.sections.append(section)
        logger.debug(
            f"Добавлен участок '{section.name}': "
            f"L={section.length}мм, D={section.diameter}мм"
        )
        return self
    
    def total_length(self) -> float:
        """
        Вычислить общую длину вала
        
        Returns:
            Суммарная длина всех участков, мм
        """
        total = sum(s.length for s in self.sections)
        logger.debug(f"Общая длина вала {self.shaft_name}: {total}мм")
        return total
    
    def validate(self, max_length: Optional[float] = None) -> Dict[str, Any]:
        """
        Валидировать размерную цепь
        
        Args:
            max_length: Максимально допустимая длина вала, мм
            
        Returns:
            Словарь с результатами валидации:
            {
                "valid": bool,
                "errors": List[str],
                "warnings": List[str],
                "total_length": float,
                "section_count": int
            }
        """
        errors: List[str] = []
        warnings: List[str] = []
        
        # Проверка наличия участков
        if not self.sections:
            errors.append("Размерная цепь пуста, нет участков вала")
            return {
                "valid": False,
                "errors": errors,
                "warnings": warnings,
                "total_length": 0.0,
                "section_count": 0
            }
        
        # Проверка длины вала
        total = self.total_length()
        if max_length and total > max_length:
            errors.append(
                f"Общая длина вала ({total:.2f}мм) превышает максимально допустимую ({max_length}мм)"
            )
        
        # Проверка минимальной длины
        if total < 50:
            warnings.append(f"Очень короткий вал: {total:.2f}мм")
        
        # Проверка на монотонность диаметров (рекомендация)
        diameters = [s.diameter for s in self.sections]
        if len(set(diameters)) == 1:
            warnings.append("Все участки вала имеют одинаковый диаметр")
        
        # Проверка резких переходов диаметров
        for i in range(len(self.sections) - 1):
            d1 = self.sections[i].diameter
            d2 = self.sections[i + 1].diameter
            ratio = max(d1, d2) / min(d1, d2)
            if ratio > 2.0:
                warnings.append(
                    f"Резкий переход диаметра между '{self.sections[i].name}' "
                    f"и '{self.sections[i+1].name}': {d1:.1f}мм → {d2:.1f}мм (x{ratio:.1f})"
                )
        
        # Проверка слишком коротких участков
        for section in self.sections:
            if section.length < section.diameter * 0.5:
                warnings.append(
                    f"Участок '{section.name}' очень короткий относительно диаметра: "
                    f"L={section.length}мм < 0.5*D={section.diameter * 0.5:.1f}мм"
                )
        
        valid = len(errors) == 0
        logger.info(
            f"Валидация размерной цепи {self.shaft_name}: "
            f"{'УСПЕШНО' if valid else 'ПРОВАЛЕНО'}, "
            f"ошибок: {len(errors)}, предупреждений: {len(warnings)}"
        )
        
        return {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "total_length": total,
            "section_count": len(self.sections)
        }
    
    def to_drawing_params(self) -> List[Dict[str, Any]]:
        """
        Конвертировать в параметры для чертежа
        
        Returns:
            Список участков в формате для Drawing Engine:
            [{"name": str, "length": float, "diameter": float, "position": float}, ...]
        """
        params = []
        position = 0.0
        
        for section in self.sections:
            params.append({
                "name": section.name,
                "length": section.length,
                "diameter": section.diameter,
                "tolerance": section.tolerance,
                "position": position,
                "position_end": position + section.length
            })
            position += section.length
        
        logger.debug(f"Сгенерированы параметры чертежа для {len(params)} участков")
        return params
    
    def to_trace(self) -> Dict[str, Any]:
        """
        Экспорт трассировки для отладки и отчётов
        
        Returns:
            Словарь с подробной информацией о цепи
        """
        validation = self.validate()
        
        trace = {
            "shaft_name": self.shaft_name,
            "total_length": self.total_length(),
            "section_count": len(self.sections),
            "sections": [
                {
                    "name": s.name,
                    "length": s.length,
                    "diameter": s.diameter,
                    "tolerance": s.tolerance
                }
                for s in self.sections
            ],
            "validation": validation
        }
        
        return trace
    
    def __repr__(self) -> str:
        return (
            f"DimChain('{self.shaft_name}', "
            f"sections={len(self.sections)}, "
            f"total_length={self.total_length():.2f}мм)"
        )
