import argparse
import json
from pathlib import Path
from .catalog import Catalog
from .models import Project
from .engine import run, aggregate
from .io import load_activities, export_excel
from .calculator import electricity_scenario


def main():
    p = argparse.ArgumentParser(description="CarbonFlow 企业碳核算命令行")
    p.add_argument("--input", default="examples/demo_activities.xlsx")
    p.add_argument("--catalog", default="data/carbon_data.xlsx")
    p.add_argument("--province", default="重庆")
    p.add_argument("--year", type=int, default=2026)
    p.add_argument("--name", default="示例制造企业（虚构）")
    p.add_argument("--overrides", help="人工确认JSON文件，以记录ID作为键")
    p.add_argument("--green-kwh", type=float, help="可选购电假设情景，非实际市场法")
    p.add_argument("--output", default="outputs")
    args = p.parse_args()
    catalog = Catalog.load(args.catalog)
    rows = load_activities(args.input, args.input)
    project = Project(name=args.name, year=args.year, province=args.province)
    overrides = json.loads(Path(args.overrides).read_text(encoding="utf-8")) if args.overrides else {}
    results, audit = run(rows, project, catalog, overrides, source_id=Path(args.input).name)
    summary = aggregate(results)
    scenario = electricity_scenario(results, args.green_kwh, catalog, project) if args.green_kwh is not None else None
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    (out / "carbon_results.xlsx").write_bytes(export_excel(results, project, catalog, audit, scenario))
    (out / "audit.jsonl").write_text(audit.jsonl(), encoding="utf-8")
    (out / "results.json").write_text(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"已导出 {out.resolve()}。待处理记录未按0排放计算。")


if __name__ == "__main__":
    main()
