from .units import normalize


def candidates(classification, row, project, catalog):
    kind = classification["活动类型"]
    substance = classification.get("物质", "")
    region = row.get("地区") or project.province
    country = row.get("国家") or project.country
    found = [f for f in catalog.factors if f["活动类型"] == kind and f.get("方法") not in ["中国购电情景", "含RF情景"]]
    if substance:
        found = [f for f in found if f.get("物质") == substance]
    found = [f for f in found if int(f["数据年份"] or 0) <= project.year
             and (not f.get("适用年度") or int(f["适用年度"]) == project.year)]
    warnings = []
    if kind == "electricity":
        if country != "中国":
            found = []
        else:
            mapped = next((r["区域"] for r in catalog.regions if r["省份"] == region), "")
            order = [r for r in [region, mapped, "全国"] if r]
            found = [f for f in found if f["地区"] in order]
            if found:
                rank = min(order.index(f["地区"]) for f in found)
                found = [f for f in found if order.index(f["地区"]) == rank]
                if found[0]["地区"] != region:
                    warnings.append(f"地区回退：{region or '省份未填'}采用{found[0]['地区']}因子")
    else:
        # 国内专用参数不默认为其他国家的适用值；国外代理仍需后续确认。
        found = [f for f in found if f.get("国家") in ("全球", country) or f.get("代理") == "是"]
    if found:
        # 首先过滤适用性，之后选择来源优先级及最接近核算期的年份。
        priority = min(int(f.get("来源优先级") or 9) for f in found)
        found = [f for f in found if int(f.get("来源优先级") or 9) == priority]
        year = max(int(f["数据年份"] or 0) for f in found)
        found = [f for f in found if int(f["数据年份"] or 0) == year]
        direct = [f for f in found if normalize(f["活动单位"]) == normalize(row.get("单位", ""))]
        if direct:
            found = direct
    return found, warnings
