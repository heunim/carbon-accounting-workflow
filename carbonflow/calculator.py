from .models import yes
from .units import number, UnitError
import math


def calculate(quantity, factor, catalog, project):
    quantity = number(quantity, "标准活动量")
    value = number(factor["因子值"], "因子值")
    gas = factor["排放表示"]
    mass = factor.get("气体质量单位", "kg") or "kg"
    multipliers = {"kg": 1, "t": 1000, "g": .001}
    if mass not in multipliers:
        raise UnitError("气体质量单位未识别")
    mult = multipliers[mass]
    g = 1.0; key = str(factor.get("GWP键", ""))
    if gas not in ("CO2", "CO2e"):
        if gas == "CO2e+RF":
            raise UnitError("含RF因子不能并入默认温室气体小计")
        entry = next((r for r in catalog.gwps if r["GWP键"] == key), None)
        if entry is None:
            raise UnitError(f"缺少{gas}的GWP参数")
        if entry.get("报告处理") == "总量外单列":
            raise UnitError("该气体需在总量外单列，本版不并入默认小计")
        if entry["口径"] != project.gwp_basis:
            raise UnitError("GWP版本与项目设置不一致，请选相同口径因子")
        g = number(entry["GWP值"], "GWP", positive=True)
    elif gas == "CO2e" and factor.get("GWP口径") and factor["GWP口径"] != project.gwp_basis:
        raise UnitError("聚合CO₂e的GWP口径与项目不同，不能按比例直接换版")
    emission = quantity * value * mult * g
    if not math.isfinite(emission):
        raise UnitError("计算结果超出有效数值范围，请检查活动量与因子")
    if gas == "CO2e":
        formula = f"{quantity:g} × {value:g} × {mult:g} = {emission:.8g} kgCO₂e（不重复乘GWP）"
    else:
        formula = f"{quantity:g} × {value:g} × {mult:g} × GWP({gas}) {g:g} = {emission:.8g} kgCO₂e"
    return emission, g, key, formula


def electricity_scenario(results, green_kwh, catalog, project):
    """中国购电假设情景，独立于位置法小计。"""
    electricity = [r for r in results if r.status == "已计算" and r.category == "electricity"]
    total = sum(r.standard_quantity for r in electricity)
    green = number(green_kwh, "假设绿电量")
    if green > total:
        raise UnitError("假设绿电量不能超过已计算的外购电量")
    fs = [f for f in catalog.factors if f["方法"] == "中国购电情景" and int(f["数据年份"]) <= project.year
          and f["活动单位"] == "kWh" and f["排放表示"] == "CO2" and f["核对状态"] == "已核实"]
    if not fs or project.country != "中国":
        raise UnitError("没有适用的中国购电情景因子")
    f = max(fs, key=lambda x: int(x["数据年份"]))
    return {"情景": "中国购电假设情景（非实际市场法）", "总电量kWh": total,
            "假设绿电kWh": green, "剩余电量因子": f["因子值"],
            "情景kgCO2e": (total - green) * f["因子值"], "位置法kgCO2e": sum(r.emission_kg for r in electricity),
            "因子ID": f["因子ID"], "来源URL": f["来源URL"],
            "说明": "假设绿电符合所选中国规则并按零计；仅覆盖已计算电力的CO₂分量，不纳入主小计。"}
