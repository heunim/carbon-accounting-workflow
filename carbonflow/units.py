import math
from .models import yes


class UnitError(ValueError):
    pass


ALIASES = {"千瓦时": "kWh", "kwh": "kWh", "mwh": "MWh", "吨": "t", "公斤": "kg",
           "千克": "kg", "升": "L", "l": "L", "m³": "m3", "立方米": "m3", "方": "m3",
           "nm3": "Nm3", "Nm³": "Nm3", "标方": "Nm3", "标准立方米": "Nm3",
           "人公里": "person.km", "人·km": "person.km", "人·公里": "person.km", "passenger.km": "person.km",
           "吨公里": "t.km", "t·km": "t.km", "t·公里": "t.km", "tonne.km": "t.km",
           "车公里": "vehicle.km", "车·km": "vehicle.km", "公里": "km", "gj": "GJ", "mj": "MJ"}
UNITS = {"kg": ("mass", 1), "t": ("mass", 1000), "g": ("mass", .001),
         "L": ("volume", .001), "m3": ("volume", 1), "Nm3": ("standard_volume", 1),
         "kWh": ("energy", .0036), "MWh": ("energy", 3.6), "GJ": ("energy", 1), "MJ": ("energy", .001),
         "km": ("distance", 1), "person.km": ("passenger_distance", 1),
         "vehicle.km": ("vehicle_distance", 1), "t.km": ("freight_distance", 1)}


def normalize(unit):
    u = str(unit).strip().replace(" ", "")
    return ALIASES.get(u, u)


def number(value, label="数量", positive=False):
    if isinstance(value, bool) or value in (None, ""):
        raise UnitError(f"{label}缺失或不是有效数值")
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise UnitError(f"{label}必须是数值") from None
    if not math.isfinite(n) or n < 0 or (positive and n == 0):
        raise UnitError(f"{label}必须是{'正' if positive else '非负'}有限数值")
    return n


def convert(quantity, source, target, params=None):
    """只作有定义的换算。物理参数缺失时抛出明确待补原因。"""
    p = params or {}
    q = number(quantity)
    a, b = normalize(source), normalize(target)
    if a not in UNITS or b not in UNITS:
        raise UnitError(f"暂不支持单位 {a} 或 {b}，请人工核对")
    if a == b:
        return q, f"{q:g} {a}（单位一致）"
    da, ma = UNITS[a]; db, mb = UNITS[b]
    if da == db:
        return q * ma / mb, f"{q:g} {a} × {ma / mb:g} = {q * ma / mb:g} {b}"
    if da == "volume" and db == "mass":
        density = number(p.get("密度kg/L"), "密度kg/L", positive=True)
        if not p.get("密度来源"):
            raise UnitError("请补充密度来源或明确估算假设")
        out = q * ma * 1000 * density / mb
        return out, f"{q:g} {a} × {ma * 1000:g} L/{a} × {density:g} kg/L ÷ {mb:g} kg/{b}"
    if da == "volume" and b == "Nm3":
        if not yes(p.get("标准体积已确认")):
            raise UnitError("m³的标准状态未确认，不能直接当作Nm³")
        return q * ma, f"已确认同一标准状态；{q:g} {a} × {ma:g}"
    if a == "km" and b == "person.km":
        people = number(p.get("人数"), "人数", positive=True)
        trips = number(p.get("行程次数", 1), "行程次数", positive=True)
        return q * people * trips, f"{q:g} km × {people:g} 人 × {trips:g} 次"
    if a == "km" and b == "t.km":
        mass = number(p.get("载重t"), "载重t", positive=True)
        return q * mass, f"{q:g} km × {mass:g} t（同一运输段）"
    if a == "km" and b == "vehicle.km" and yes(p.get("车公里已确认")):
        return q, f"{q:g} km已确认为总车公里"
    raise UnitError(f"{a}不能直接换成{b}，请补充相应活动量或选择适用因子")
