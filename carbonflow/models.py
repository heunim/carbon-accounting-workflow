from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json


def fingerprint(value) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:20]


def yes(value) -> bool:
    return str(value).strip().lower() in {"是", "true", "1", "yes"}


@dataclass
class Project:
    name: str = "示例制造企业（虚构）"
    year: int = 2026
    country: str = "中国"
    province: str = "重庆"
    control: str = "未知"
    gwp_basis: str = "AR5-100"
    boundary: str = "运营控制法，按设施归属确认"


@dataclass
class Result:
    activity_id: str
    name: str
    quantity: object
    unit: str
    row_number: int
    status: str = "待确认"
    reason: str = ""
    scope: str = ""
    category: str = ""
    substance: str = ""
    factor_id: str = ""
    factor_value: float | None = None
    factor_unit: str = ""
    standard_quantity: float | None = None
    emission_kg: float | None = None
    gas: str = ""
    gwp: float | None = None
    gwp_key: str = ""
    gwp_basis: str = ""
    formula: str = ""
    source: str = ""
    source_url: str = ""
    source_locator: str = ""
    factor_year: object = ""
    verification: str = ""
    warnings: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    rule_id: str = ""

    def to_dict(self):
        return asdict(self)


class Audit:
    """每次运行构建事件快照。汇总不从历史日志累加。"""
    def __init__(self, run_id: str, catalog_hash: str):
        self.run_id = run_id
        self.catalog_hash = catalog_hash
        self.events = []

    def log(self, step, activity_id="", actor="规则", **details):
        self.events.append({"time": datetime.now(timezone.utc).isoformat(),
                            "run_id": self.run_id, "catalog_hash": self.catalog_hash,
                            "step": step, "activity_id": activity_id,
                            "actor": actor, **details})

    def jsonl(self):
        return "\n".join(json.dumps(e, ensure_ascii=False, default=str, allow_nan=False) for e in self.events) + "\n"
