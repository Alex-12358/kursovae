"""
Calc Engine - оркестратор всех расчётных модулей.
"""
import logging
from typing import Dict, Any

from calc.gear import calculate_gear
from calc.dim_chain import DimChain, ShaftSection
from calc.shaft import calculate_shaft
from calc.bearings import select_bearing
from calc.keys import calculate_key
from calc.coupling import select_coupling

logger = logging.getLogger(__name__)


def run_calculations(task_data: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("=== СТАРТ CALC ENGINE ===")
    
    calc_params = {}
    calc_trace = {}
    
    # 1. GEAR CALCULATION
    logger.info("Этап 1/5: Расчёт зубчатой передачи")
    gear_result = calculate_gear(task_data)
    calc_params["gear"] = gear_result
    calc_trace["gear"] = gear_result.get("trace", {})
    
    # 2. SHAFT CALCULATION
    logger.info("Этап 2/5: Расчёт валов")
    shaft_result = calculate_shaft(task_data, gear_result)
    calc_params["shaft"] = shaft_result
    calc_trace["shaft"] = shaft_result.get("trace", {})
    
    # 3. BEARINGS
    logger.info("Этап 3/5: Подбор подшипников")
    d_bearing = shaft_result.get("d_bearing_seat", 25)
    rpm = task_data.get("rpm_input", 1000)
    life_hours = task_data.get("service_life", 10000)
    T1 = gear_result.get("T1", 0)
    d1 = gear_result.get("d1", 50)
    Ft = 2 * T1 * 1000 / d1 if d1 > 0 else 1000
    Fr = 1.2 * Ft
    
    bearings_result = select_bearing(d=d_bearing, radial_load=Fr, rpm=rpm, life_hours=life_hours)
    calc_params["bearings"] = bearings_result
    calc_trace["bearings"] = bearings_result.get("trace", {})
    
    # 4. KEYS & COUPLING
    logger.info("Этап 4/5: Расчёт шпонок и муфты")
    d_gear = shaft_result.get("d_gear_seat", 25)
    b_w = gear_result.get("b_w", 50)
    L_key = int(b_w * 0.8)
    
    key_gear = calculate_key(d=d_gear, T=T1, L=L_key)
    d_coupling = shaft_result.get("d_coupling_seat", 25)
    key_coupling = calculate_key(d=d_coupling, T=T1, L=int(L_key * 0.6))
    
    keys_result = {"key_gear": key_gear, "key_coupling": key_coupling}
    calc_params["keys"] = keys_result
    calc_trace["keys"] = {"status": "calculated"}
    
    coupling_result = select_coupling(d=d_coupling, T=T1, rpm=rpm)
    calc_params["coupling"] = coupling_result
    calc_trace["coupling"] = coupling_result.get("trace", {})
    
    # 5. DIM CHAIN
    logger.info("Этап 5/5: Построение размерной цепи")
    chain = DimChain("main_shaft")
    coupling_L = coupling_result.get("L", 100)
    bearing_B = bearings_result.get("B", 23)
    
    shaft = {
        "d_coupling_seat": d_coupling,
        "d_bearing_seat": d_bearing,
        "d_gear_seat": d_gear,
        "d_end": shaft_result.get("d_end", d_bearing-5)
    }
    chain.add(ShaftSection(name="coupling_seat", length=coupling_L, diameter=shaft["d_coupling_seat"]))
    chain.add(ShaftSection(name="transition_1", length=20, diameter=shaft["d_bearing_seat"]))
    chain.add(ShaftSection(name="bearing_1", length=bearing_B, diameter=shaft["d_bearing_seat"]))
    chain.add(ShaftSection(name="gear_seat", length=b_w+10, diameter=shaft["d_gear_seat"]))
    chain.add(ShaftSection(name="bearing_2", length=bearing_B, diameter=shaft["d_bearing_seat"]))
    chain.add(ShaftSection(name="end_section", length=30, diameter=shaft.get("d_end", shaft["d_bearing_seat"]-5)))
    
    calc_params["dim_chain"] = chain.to_drawing_params()
    calc_trace["dim_chain"] = chain.to_trace()
    
    logger.info("=== CALC ENGINE ЗАВЕРШЁН ===")
    
    return {"calculated_params": calc_params, "calc_trace": calc_trace}
