def match_terms(text, expression):
    """受限语法：+表示同时，|表示任一。不执行任意表达式。"""
    if not expression:
        return False
    text = str(text).casefold()
    return all(any(word.strip().casefold() in text for word in group.split("|") if word.strip())
               for group in str(expression).split("+"))


def classify(row, project, catalog):
    name = str(row.get("活动名称", ""))
    control = row.get("设施归属") or project.control
    matches = []
    blocked = []
    for rule in catalog.rules:
        if not match_terms(name, rule["关键词"]):
            continue
        if rule.get("排除词") and match_terms(name, rule["排除词"]):
            continue
        if rule.get("用途") and row.get("用途") != rule["用途"]:
            continue
        need = rule["边界要求"]
        if need and need != "不限" and need != control:
            blocked.append(rule)
            continue
        matches.append(rule)
    if row.get("确认活动类型"):
        code = row["确认活动类型"]
        scope = row.get("确认范围", "")
        if code not in {r['活动类型'] for r in catalog.categories} or scope not in ["范围1", "范围2", "范围3"]:
            return None, "人工确认的类型或范围无效"
        permitted = [r for r in catalog.rules if r["活动类型"] == code and r["范围"] == scope
                     and r["边界要求"] in ("不限", "", control)]
        if not permitted:
            return None, "人工分类与设施归属不匹配，请先确认设施是否纳入组织边界"
        return {"活动类型": code, "范围": scope, "物质": row.get("物质", ""), "规则ID": "USER"}, ""
    if not matches:
        if blocked:
            return None, "请确认设施归属。关键词已匹配，但组织边界条件不满足"
        return None, "用途或活动类型不明确，请补充描述或人工选择类型与范围"
    first = matches[0]
    # 不把优先级当作绕过实质冲突的理由。
    if any(r["范围"] != first["范围"] for r in matches):
        return None, "命中相互冲突的范围，请人工确认用途和边界"
    result = dict(first)
    if row.get("物质"):
        result["物质"] = row["物质"]
    return result, ""
