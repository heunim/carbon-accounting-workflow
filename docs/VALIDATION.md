# 验证记录

验证日期：2026-10-05。环境为Linux、Python 3.12.14，采用requirements.txt中的依赖版本。

## 已完成

- `python -m pytest -q`：40项测试通过。
- 默认命令行案例完整运行并导出Excel、明细JSON、汇总JSON和审计JSONL。
- 独立算式核对：12条虚构活动中9条已计算、3条待处理，已计算小计16,351.19746 kgCO₂e。
- Streamlit AppTest验证默认页面、重复运行不累加、购电情景不改主小计，以及人工修改柴油用途和参数后的重新计算。
- Chromium实际浏览器验证页面加载、核算概览、人工确认与审计页签，未观察到页面JavaScript异常；README截图来自实际运行界面。
- 输出工作簿包含待处理清单、计算细节、来源、因子及GWP快照。文本被当作文本输出，测试覆盖Excel公式注入防护。

测试涉及分类歧义、煤与煤油、边界冲突、缺因子、空值与真实0、CO₂e不重复折算、GWP版本与特殊报告气体、单位量纲、密度和标准状态参数、省份回退、未来年份、重复计算组、绿色电量情景约束，以及AI输出白名单与失败路径。

## 尚未验证

- 未在真实Windows电脑手动安装运行。仓库已提供Windows启动脚本及GitHub Actions的Windows/Linux测试矩阵，远程任务需上传后触发。
- 可选AI模块已验证模拟响应和异常路径，未连接真实付费模型API；没有Key时核心流程仍可运行。
- 未用真实企业完整清单验证，也未接受第三方核查。测试通过说明程序在覆盖的条件下按设计运行，不代表所有因子均适用于任意企业。

## 复验

在项目虚拟环境内运行：

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m carbonflow.cli --input examples/demo_activities.xlsx --output outputs
python -m streamlit run app.py
```

示例输入中的代理接受、密度、边界及维修泄漏量均为虚构案例设定。将项目用于真实活动时，应重新核实这些输入。
