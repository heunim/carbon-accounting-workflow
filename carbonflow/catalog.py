from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import math
import openpyxl


class CatalogError(ValueError):
    pass


def read_bytes(source):
    if isinstance(source, bytes):
        return source
    if hasattr(source, "getvalue"):
        return source.getvalue()
    return Path(source).read_bytes()


def records(sheet):
    values = list(sheet.values)
    if not values:
        return []
    headers = [str(x).strip() if x is not None else "" for x in values[0]]
    if len(set(headers)) != len(headers):
        raise CatalogError(f"{sheet.title}含重复列名")
    return [{k: ("" if v is None else v) for k, v in zip(headers, row)}
            for row in values[1:] if any(x is not None for x in row)]


@dataclass
class Catalog:
    categories: list
    rules: list
    factors: list
    gwps: list
    regions: list
    digest: str

    @classmethod
    def load(cls, source):
        raw = read_bytes(source)
        book = openpyxl.load_workbook(BytesIO(raw), data_only=True, read_only=True)
        required = {"类别框架": ["活动类型", "名称"],
                    "归类规则": ["规则ID", "优先级", "关键词", "活动类型", "范围", "边界要求"],
                    "因子库": ["因子ID", "活动类型", "物质", "因子值", "活动单位", "排放表示", "来源", "来源URL", "数据年份", "核对状态", "地区", "方法"],
                    "GWP转换表": ["GWP键", "GWP值", "口径", "来源"]}
        for name, cols in required.items():
            if name not in book:
                raise CatalogError(f"缺少工作表：{name}。请使用项目自带模板。")
            headers = list(next(book[name].values))
            missing = set(cols) - set(headers)
            if missing:
                raise CatalogError(f"{name}缺少列：{', '.join(sorted(missing))}")
        tables = {name: records(book[name]) for name in required}
        for name, key in [("因子库", "因子ID"), ("归类规则", "规则ID"), ("GWP转换表", "GWP键")]:
            ids = [str(r[key]) for r in tables[name]]
            if "" in ids or len(ids) != len(set(ids)):
                raise CatalogError(f"{name}存在空白或重复的{key}")
        for row in tables["因子库"]:
            value = row["因子值"]
            if value != "" and (not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0):
                raise CatalogError(f"{row['因子ID']}因子值必须为空或非负有限数值")
        for row in tables["GWP转换表"]:
            value = row["GWP值"]
            if not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
                raise CatalogError(f"{row['GWP键']}的GWP必须为正数")
        cats = {r["活动类型"] for r in tables["类别框架"]}
        for row in tables["归类规则"]:
            if row["活动类型"] not in cats or row["范围"] not in ["范围1", "范围2", "范围3"]:
                raise CatalogError(f"规则{row['规则ID']}的范围或活动类型无效")
            try:
                row["优先级"] = int(row["优先级"])
            except (ValueError, TypeError):
                raise CatalogError("规则优先级必须是整数") from None
        regions = records(book["地区映射"]) if "地区映射" in book else []
        book.close()
        return cls(tables["类别框架"], sorted(tables["归类规则"], key=lambda r: r["优先级"]),
                   tables["因子库"], tables["GWP转换表"], regions, sha256(raw).hexdigest())

    def factor(self, factor_id):
        return next((r for r in self.factors if r["因子ID"] == factor_id), None)

    def category_name(self, code):
        return next((r["名称"] for r in self.categories if r["活动类型"] == code), code)
