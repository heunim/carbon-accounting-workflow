"""从可审查JSON种子重建Excel背景文件与虚构示例。"""
from pathlib import Path
import json
import sys
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from carbonflow.io import add_sheet


def build():
    seed = json.loads((ROOT / "data/catalog_seed.json").read_text(encoding="utf-8"))
    categories = [("electricity", "外购电力"), ("gas", "天然气燃烧"), ("fuel", "其他燃料燃烧"),
                  ("refrigerant", "制冷剂泄漏"), ("freight", "第三方货运"), ("air", "航空差旅"),
                  ("rail", "铁路差旅"), ("water", "自来水供应"), ("waste", "外包废物处置")]
    rules = []
    def rule(words, kind, scope, control, substance, exclude="", purpose=""):
        rules.append([f"R{len(rules)+1:03d}", len(rules)+1, words, exclude, control, purpose, kind, scope, substance])
    rule("外购电|用电|电锅炉", "electricity", "范围2", "边界内", "电力", "自发自用|售电|出售电")
    rule("天然气+锅炉|炉窑|固定", "gas", "范围1", "边界内", "天然气")
    rule("天然气+车辆|货车", "gas", "范围1", "边界内", "天然气")
    rule("天然气", "gas", "范围1", "边界内", "天然气", purpose="固定")
    for fuel in ["柴油", "汽油", "液化石油气", "一般烟煤"]:
        rule(fuel+"+锅炉|发电机|炉窑", "fuel", "范围1", "边界内", fuel)
        rule(fuel+"+公务车|货车|车辆|叉车", "fuel", "范围1", "边界内", fuel)
        rule(fuel, "fuel", "范围1", "边界内", fuel, purpose="固定")
        rule(fuel, "fuel", "范围1", "边界内", fuel, purpose="移动")
    for gas in ["R410A", "R32", "R134a"]:
        rule(gas, "refrigerant", "范围1", "边界内", gas)
    rule("外包|第三方+货运|物流|运输", "freight", "范围3", "边界外", "非冷藏柴油铰接货车")
    rule("国际+差旅|机票|航班+经济舱", "air", "范围3", "边界外", "国际经济舱")
    rule("高铁|铁路|火车", "rail", "范围3", "边界外", "中国铁路")
    rule("自来水|供水", "water", "范围3", "不限", "自来水")
    rule("居民|生活+垃圾+填埋", "waste", "范围3", "边界外", "居民混合垃圾填埋")
    rule("商业|工业+废物|垃圾+填埋", "waste", "范围3", "边界外", "商业工业废物填埋")
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    add_sheet(wb, "使用说明", ["项目", "说明"], [
        ["用途", "CarbonFlow求职作品演示背景文件。精选52条候选，不是完整因子库。"],
        ["数据来源", "来自本项目此前核对的NCSC、生态环境部、IPCC和英国官方资料，逐行保留URL与定位。"],
        ["原始值与派生值", "燃料CO₂质量/体积因子由能量因子及缺省热值相乘得到，须确认适用条件。"],
        ["缺口", "中国铁路无适用因子。不得用英国铁路代替。空白数值不等于0。"],
        ["更新方法", "编辑因子库、GWP转换表与归类规则后，在界面加载修改后的背景文件。保留ID唯一。"],
        ["时间口径", "示例报告年2026。中国电力数据年2023，发布版本与数据年分别记录。"],
        ["区域回退", "地区映射仅配置明确示例，未配置的省份在省级缺失时降为全国并提示。"],
        ["来源版本", seed["review_date"]]])
    add_sheet(wb, "类别框架", ["活动类型", "名称"], categories)
    add_sheet(wb, "归类规则", ["规则ID", "优先级", "关键词", "排除词", "边界要求", "用途", "活动类型", "范围", "物质"], rules)
    fs = seed["factors"]
    add_sheet(wb, "因子库", list(fs[0]), [list(f.values()) for f in fs])
    gs = seed["gwp"]
    add_sheet(wb, "GWP转换表", list(gs[0]), [list(g.values()) for g in gs])
    add_sheet(wb, "地区映射", ["省份", "区域"], [["重庆", "西南"], ["四川", "西南"], ["北京", "华北"], ["上海", "华东"], ["广东", "南方"]])
    wb.save(ROOT / "data/carbon_data.xlsx")
    common = {"确认适用条件": "是", "确认代理": "是"}
    rows = [
        {"活动名称": "重庆办公楼外购电", "数量": 10000, "单位": "kWh", "设施归属": "边界内", "地区": "重庆"},
        {"活动名称": "四川工厂外购电", "数量": 20, "单位": "MWh", "设施归属": "边界内", "地区": "四川"},
        {"活动名称": "天然气锅炉", "数量": 1000, "单位": "Nm3", "设施归属": "边界内"},
        {"活动名称": "公务车柴油", "数量": 200, "单位": "L", "设施归属": "边界内", "密度kg/L": .84, "密度来源": "虚构案例给定密度，仅用于演示"},
        {"活动名称": "R410A空调泄漏", "数量": 2, "单位": "kg", "设施归属": "边界内", "确认泄漏量": "是"},
        {"活动名称": "第三方非冷藏柴油铰接货车运输", "数量": 1000, "单位": "t.km", "设施归属": "边界外"},
        {"活动名称": "国际差旅机票经济舱", "数量": 2000, "单位": "person.km", "设施归属": "边界外"},
        {"活动名称": "自来水供应", "数量": 100, "单位": "m3", "设施归属": "边界内"},
        {"活动名称": "生活垃圾外包填埋", "数量": 2, "单位": "t", "设施归属": "边界外"},
        {"活动名称": "柴油", "数量": 50, "单位": "L", "设施归属": "边界内"},
        {"活动名称": "员工高铁差旅", "数量": 800, "单位": "person.km", "设施归属": "边界外"},
        {"活动名称": "办公纸张采购", "数量": 30, "单位": "kg", "设施归属": "边界内"},
    ]
    rows = [dict(common, **r) for r in rows]
    headers = ["活动名称", "数量", "单位", "设施归属", "地区", "用途", "密度kg/L", "密度来源", "确认适用条件", "确认代理", "确认泄漏量"]
    demo = openpyxl.Workbook(); demo.remove(demo.active)
    add_sheet(demo, "活动数据", headers, [[r.get(k, "") for k in headers] for r in rows])
    add_sheet(demo, "示例说明", ["项目", "说明"], [
        ["虚构声明", "本文件所有活动及数量均为虚构，用于求职作品演示，不代表任何真实企业。"],
        ["确认字段", "示例中的确认仅表示演示假设，不能用于证明真实业务中的代理或因子适用性。"],
        ["预期缺口", "柴油用途未知、高铁缺因子、纸张活动未覆盖，均应保留待处理。"],
        ["自建数据", "活动名称、数量、单位为必需列。其他字段按需提供，或在界面逐条确认。"]])
    demo.save(ROOT / "examples/demo_activities.xlsx")
    (ROOT / "examples/demo_activities.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built {len(fs)} factors, {len(rules)} rules, {len(rows)} fictional activities")


if __name__ == "__main__":
    build()
