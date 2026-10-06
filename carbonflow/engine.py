from dataclasses import asdict
from collections import Counter
import math
from .models import Project, Result, Audit, fingerprint, yes
from .classifier import classify
from .matcher import candidates
from .units import number, convert, UnitError
from .calculator import calculate


def clean_records(rows):
    """消除pandas空值，保留真实0。"""
    return [{str(k): ("" if v is None or isinstance(v, float) and math.isnan(v) else str(v) if isinstance(v, float) and not math.isfinite(v) else v)
             for k, v in row.items()} for row in rows]


def run(rows, project, catalog, overrides=None, source_id="uploaded"):
    rows = clean_records(rows)
    overrides = {k: clean_records([v])[0] for k, v in (overrides or {}).items()}
    ids = [fingerprint([source_id, i + 2]) for i in range(len(rows))]
    effective = [dict(row, **overrides.get(aid, {})) for row, aid in zip(rows, ids)]
    run_id = fingerprint([rows, overrides, asdict(project), catalog.digest, source_id])
    audit = Audit(run_id, catalog.digest)
    audit.log("project", project=asdict(project), source=source_id)
    # 明确关联的替代计量记录互斥，未知关联不凭名称自动合并。
    groups = Counter(str(r.get("计算组")) for r in effective if r.get("计算组") and not yes(r.get("不计入")))
    results = []
    for index, (original, row, aid) in enumerate(zip(rows, effective, ids)):
        r = Result(aid, str(row.get("活动名称", "")), row.get("数量", ""), str(row.get("单位", "")), index + 2)
        results.append(r)
        audit.log("input", aid, input=row, original=original, row=index + 2)
        if aid in overrides:
            audit.log("confirmation", aid, actor="用户", changes=overrides[aid])
        if yes(row.get("不计入")):
            r.status = "已排除"; r.reason = str(row.get("排除原因") or "用户确认排除或采用另一计量方法")
            continue
        if row.get("计算组") and groups[str(row["计算组"])] > 1:
            r.reason = "同一计算组有多条记录，请保留一种方法并排除替代记录"
            continue
        try:
            number(r.quantity)
        except UnitError as e:
            r.status = "无效输入"; r.reason = str(e); continue
        if not r.name.strip() or not r.unit.strip():
            r.status = "无效输入"; r.reason = "活动名称和单位不能为空"; continue
        classification, reason = classify(row, project, catalog)
        audit.log("classify", aid, result=classification, reason=reason)
        if classification is None:
            r.reason = reason; continue
        r.scope = classification["范围"]; r.category = classification["活动类型"]
        r.substance = classification.get("物质", ""); r.rule_id = classification["规则ID"]
        pool, warnings = candidates(classification, row, project, catalog)
        r.candidates = [f["因子ID"] for f in pool]; r.warnings.extend(warnings)
        audit.log("match", aid, candidates=r.candidates)
        if not pool:
            r.status = "待补因子"; r.reason = f"缺少适用因子：{catalog.category_name(r.category)} / {r.substance or '需明确物质'} / {r.unit}。请补充来源、单位及适用条件。"; continue
        selected = row.get("确认因子ID")
        if selected and selected not in r.candidates:
            r.reason = "已确认因子不再适用于当前条件，请重新选择"; continue
        if len(pool) > 1 and not selected:
            r.reason = "存在多个适用候选，请选择具体因子"; continue
        f = next((f for f in pool if f["因子ID"] == selected), pool[0])
        r.factor_id = f["因子ID"]; r.factor_value = f["因子值"] if f["因子值"] != "" else None
        r.factor_unit = f"{f.get('气体质量单位') or 'kg'}{f['排放表示']}/{f['活动单位']}"
        r.source = f["来源"]; r.source_url = f["来源URL"]; r.source_locator = f.get("来源定位", "")
        r.factor_year = f["数据年份"] or f"未单列；发布版本{f.get('发布版本', '')}"
        r.verification = f["核对状态"]; r.gas = f["排放表示"]
        r.gwp_basis = f.get("GWP口径") or project.gwp_basis
        if r.factor_value is None:
            r.status = "待补因子"; r.reason = "候选因子值为空，不能按0计算"; continue
        if not r.source or not r.source_url:
            r.reason = "因子来源不完整，请补齐来源及链接"; continue
        if f["核对状态"] != "已核实":
            if not yes(row.get("确认待核因子")):
                r.reason = "因子尚待核对，请核实来源和适用条件后确认"; continue
            r.warnings.append("用户确认使用待核因子，仅供估算")
        if yes(f.get("代理")) and (row.get("国家") or project.country) != f.get("国家"):
            if not yes(row.get("确认代理")):
                r.reason = "此因子来自国外场景，请确认代理适用性"; continue
            r.warnings.append("国外代理因子，已人工确认")
        if f.get("使用条件") and not yes(row.get("确认适用条件")):
            r.reason = f"请确认适用条件：{f['使用条件']}"; continue
        if r.category == "refrigerant" and not yes(row.get("确认泄漏量")):
            r.reason = "请确认数量为泄漏量或满足条件的维修补充量，采购量不能直接代入"; continue
        try:
            q, conversion = convert(r.quantity, r.unit, f["活动单位"], row)
            r.standard_quantity = q
            audit.log("unit_convert", aid, formula=conversion, standard_quantity=q)
            r.emission_kg, r.gwp, r.gwp_key, formula = calculate(q, f, catalog, project)
            r.formula = conversion + "；" + formula
        except UnitError as e:
            r.status = "待补数据"; r.reason = str(e); continue
        r.status = "已计算"
        if r.gas == "CO2":
            r.warnings.append("仅CO₂分量，未补齐其他气体")
        if f.get("参数说明"):
            r.warnings.append(f["参数说明"])
        audit.log("calculate", aid, result=r.to_dict(), factor_snapshot=f)
    for r in results:
        audit.log("outcome", r.activity_id, status=r.status, reason=r.reason)
    return results, audit


def aggregate(results):
    scopes = {s: 0.0 for s in ["范围1", "范围2", "范围3"]}
    types = {}
    for r in results:
        if r.status == "已计算":
            scopes[r.scope] += r.emission_kg
            types[r.category] = types.get(r.category, 0) + r.emission_kg
    total = sum(scopes.values())
    done = sum(r.status == "已计算" for r in results)
    excluded = sum(r.status == "已排除" for r in results)
    return {"total_kg": total, "scopes": scopes, "categories": types,
            "shares": {s: v / total if total else 0 for s, v in scopes.items()},
            "top3": sorted(types.items(), key=lambda t: t[1], reverse=True)[:3],
            "input_count": len(results), "calculated_count": done,
            "excluded_count": excluded, "pending_count": len(results) - done - excluded}
