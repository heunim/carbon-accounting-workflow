from pathlib import Path
from hashlib import sha256
from dataclasses import asdict
import html
import json
from zipfile import BadZipFile
import pandas as pd
import plotly.express as px
import streamlit as st
from carbonflow.catalog import Catalog, CatalogError
from carbonflow.models import Project, fingerprint
from carbonflow.engine import run, aggregate
from carbonflow.io import load_activities, export_excel, LABELS
from carbonflow.calculator import electricity_scenario
from carbonflow.units import UnitError
from carbonflow.ai_suggest import suggest, SuggestionError, settings

ROOT = Path(__file__).parent


def display_frame(items):
    """展示复杂字段时显式转为文本，避免Arrow混合类型歧义。"""
    frame = pd.DataFrame(items)
    for col in frame.columns:
        if frame[col].dtype == object:
            frame[col] = frame[col].map(lambda v: json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) else "" if v is None else str(v))
    return frame


st.set_page_config(page_title="CarbonFlow · 企业碳核算", page_icon="🌿", layout="wide")
st.markdown('''<style>
[data-testid="stAppViewContainer"]{background:#f6f8f5}
[data-testid="stSidebar"]{background:#102f29}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label,[data-testid="stSidebar"] p,[data-testid="stSidebar"] small{color:#eef5f0!important}
[data-testid="stSidebar"] button p,[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small{color:#163f35!important}
.block-container{padding-top:2rem;max-width:1440px}
.hero{background:#163f35;color:#f6faf5;border-radius:20px;padding:28px 32px;margin-bottom:22px}
.hero h1{font-size:34px;letter-spacing:-1px;margin:5px 0 12px;color:white}
.hero p{color:#c9dbd0;margin:0;font-size:15px}
.eyebrow{font-size:11px;letter-spacing:3px;color:#bce0be;font-weight:700}
.pill{display:inline-block;border:1px solid #769385;border-radius:99px;padding:4px 10px;margin:14px 8px 0 0;color:#daebde;font-size:12px}
[data-testid="stMetric"]{background:white;border:1px solid #e0e8df;border-radius:14px;padding:18px 20px}
[data-testid="stMetricValue"]{font-family:ui-monospace,monospace;color:#174d3a}
.tiny{font-size:12px;color:#607068}
button[kind="primary"]{background:#1d684e}
[data-testid="stTabs"]{margin-top:18px}
</style>''', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## CarbonFlow")
    st.caption("碳核算工作流 · Portfolio Edition")
    mode = st.radio("数据入口", ["虚构案例演示", "上传活动数据"], key="mode")
    uploaded = st.file_uploader("活动数据 Excel / CSV", type=["xlsx", "csv"], disabled=mode == "虚构案例演示")
    st.divider()
    name = st.text_input("项目名称", "示例制造企业（虚构）")
    year = st.number_input("核算年度", 2000, 2100, 2026, step=1)
    country = st.selectbox("默认国家", ["中国", "英国", "其他或未知"])
    province = st.text_input("默认省份", "重庆")
    control = st.selectbox("未填设施归属时", ["未知", "边界内", "边界外"], help="行级归属优先；只对缺失值使用默认，不改变组织边界方法。")
    st.caption("边界采用运营控制法。请根据企业实际情况判断设施是否纳入。")
    with st.expander("背景文件与AI设置"):
        custom_catalog = st.file_uploader("替换背景因子文件", type=["xlsx"], key="catalog_upload")
        ai_enabled = st.checkbox("启用AI建议（可选）", value=False)
        st.caption("启用后，点击建议按钮才发送所选活动名称、单位、边界信息和候选因子。数量、企业名和整份文件不会发送。")
    st.download_button("下载虚构活动模板", (ROOT / "examples/demo_activities.xlsx").read_bytes(), "demo_activities.xlsx", on_click="ignore")
    st.download_button("下载背景因子文件", (ROOT / "data/carbon_data.xlsx").read_bytes(), "carbon_data.xlsx", on_click="ignore")

st.markdown('''<div class="hero"><div class="eyebrow">CARBON ACCOUNTING WORKSPACE</div>
<h1>让每一笔排放，都有计算依据。</h1><p>从活动数据到范围汇总，把因子来源、计算过程和待处理问题放在一起。</p>
<span class="pill">Scope 1 / 2 / 3</span><span class="pill">Python确定性计算</span><span class="pill">AI辅助复核</span></div>''', unsafe_allow_html=True)
try:
    catalog_raw = custom_catalog.getvalue() if custom_catalog else (ROOT / "data/carbon_data.xlsx").read_bytes()
    catalog = Catalog.load(catalog_raw)
    if mode == "虚构案例演示":
        activity_raw = (ROOT / "examples/demo_activities.xlsx").read_bytes(); filename = "demo_activities.xlsx"
    elif uploaded:
        activity_raw = uploaded.getvalue(); filename = uploaded.name
    else:
        st.info("请在左侧上传包含活动名称、数量、单位的文件。也可以切换到虚构案例演示。")
        st.stop()
    rows = load_activities(activity_raw, filename)
except (CatalogError, ValueError, OSError, KeyError, BadZipFile) as e:
    st.error(str(e)); st.stop()

project = Project(name=name, year=int(year), country=country, province=province, control=control)
source_key = fingerprint([sha256(activity_raw).hexdigest(), catalog.digest])
if st.session_state.get("source_key") != source_key:
    st.session_state.source_key = source_key
    st.session_state.overrides = {}
    st.session_state.history = []
    st.session_state.seen_runs = []
    st.session_state.ai_feedback = {}
results, audit = run(rows, project, catalog, st.session_state.overrides, source_id=filename)
if audit.run_id not in st.session_state.seen_runs:
    st.session_state.history.extend(audit.events)
    st.session_state.seen_runs.append(audit.run_id)
a = aggregate(results)
st.session_state.latest_summary = a
st.session_state.latest_results = [r.to_dict() for r in results]
if mode == "虚构案例演示":
    st.caption("演示模式 · 12条虚构活动 · 真实来源因子 · 代理和缺省参数均按案例假设确认 · 不代表真实企业披露")
else:
    st.caption(f"{html.escape(name)} · {int(year)}年度 · GWP AR5-100 · 因子文件 {catalog.digest[:10]}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("已计算排放小计", f"{a['total_kg']/1000:,.3f}")
c1.caption("tCO₂e · 范围2位置法")
c2.metric("已计算记录", f"{a['calculated_count']} / {a['input_count']}")
c2.caption("记录处理数，不是排放覆盖率")
c3.metric("待处理记录", str(a["pending_count"]))
c3.caption("补数据或补因子后重新计算")
c4.metric("已排除记录", str(a["excluded_count"]))
c4.caption("保留原因和历史记录")

tabs = st.tabs(["核算概览", "活动与人工确认", "因子与来源", "审计记录", "项目说明"])
scenario = None
with tabs[0]:
    left, right = st.columns([1, 1.25])
    with left:
        st.subheader("范围构成")
        if a["total_kg"] > 0:
            fig = px.pie(names=list(a["scopes"]), values=list(a["scopes"].values()), hole=.7,
                         color_discrete_sequence=["#235c49", "#8cac70", "#d9ad63"])
            fig.update_traces(textinfo="percent", textposition="outside", hovertemplate="%{label}<br>%{value:,.2f} kgCO₂e<extra></extra>")
            fig.update_layout(height=335, margin=dict(l=20, r=20, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                              legend=dict(orientation="h", y=-.06), font=dict(family="sans-serif"))
            st.plotly_chart(fig, width="stretch", key="scope_chart")
        else:
            st.info("当前已计算小计为0，暂无占比图。")
    with right:
        st.subheader("排放热点 Top 3")
        top = pd.DataFrame([{"活动类型": catalog.category_name(k), "tCO₂e": v/1000} for k, v in a["top3"]])
        if not top.empty:
            fig = px.bar(top.sort_values("tCO₂e"), x="tCO₂e", y="活动类型", orientation="h", text_auto=".3f", color_discrete_sequence=["#2d7357"])
            fig.update_layout(height=335, margin=dict(l=0, r=35, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="已计算排放量 / tCO₂e", yaxis_title=None)
            st.plotly_chart(fig, width="stretch", key="hotspot_chart")
        st.caption("热点按活动类型汇总。未计算记录不计入分母，结果可能随补充数据变化。")
    if a["pending_count"]:
        st.warning(f"还有 {a['pending_count']} 条记录需要处理。当前显示已计算小计，不是完整企业排放总量。")
    with st.expander("购电假设情景 · 独立于实际核算", expanded=False):
        enable_scenario = st.checkbox("展示中国购电假设情景", key="enable_scenario")
        green = st.number_input("假设合格绿电量（kWh）", min_value=0.0, value=0.0, step=1000.0, key="green")
        st.caption("假设绿电符合所选中国规则并按零计，仅计算CO₂分量。没有凭证核验，不能称为实际市场法结果。")
        if enable_scenario:
            try:
                scenario = electricity_scenario(results, green, catalog, project)
                sc1, sc2 = st.columns(2)
                sc1.metric("电力位置法", f"{scenario['位置法kgCO2e']/1000:.3f} tCO₂e")
                sc2.metric("假设情景", f"{scenario['情景kgCO2e']/1000:.3f} tCO₂e")
                st.caption("情景可能高于位置法，两者不相加。")
            except UnitError as e:
                st.error(str(e))
    details = pd.DataFrame([{"活动": r.name, "范围": r.scope, "状态": r.status, "kgCO₂e": r.emission_kg, "提示": r.reason or "；".join(r.warnings)} for r in results])
    st.subheader("记录明细")
    st.dataframe(details, hide_index=True, width="stretch")
    st.download_button("下载核算结果 Excel", export_excel(results, project, catalog, audit, scenario), "carbon_results.xlsx", type="primary", on_click="ignore")

with tabs[1]:
    st.subheader("把不能确定的地方，交给人确认")
    st.caption("修改仅影响本次工作会话。页面刷新后请重新上传；下载结果和日志可保留本次依据。")
    st.dataframe(display_frame(rows), hide_index=True, width="stretch")
    choices = {r.activity_id: f"第{r.row_number}行 · {r.name} · {r.status}" for r in results}
    aid = st.selectbox("选择待处理或需修改的记录", list(choices), format_func=lambda x: choices[x], key="review_id")
    result = next(r for r in results if r.activity_id == aid)
    index = result.row_number - 2
    effective = dict(rows[index], **st.session_state.overrides.get(aid, {}))
    if result.reason:
        st.info(result.reason)
    if result.candidates:
        st.dataframe(display_frame([catalog.factor(fid) for fid in result.candidates])[["因子ID", "物质", "因子值", "活动单位", "地区", "核对状态", "使用条件"]], hide_index=True, width="stretch")
    with st.form("review_" + aid):
        b1, b2, b3 = st.columns(3)
        new_name = b1.text_input("活动名称", str(effective.get("活动名称", "")))
        quantity = b2.text_input("数量", str(effective.get("数量", "")))
        unit = b3.text_input("单位", str(effective.get("单位", "")))
        b1, b2, b3 = st.columns(3)
        controls = ["未知", "边界内", "边界外"]
        owner = b1.selectbox("设施归属", controls, index=controls.index(effective.get("设施归属")) if effective.get("设施归属") in controls else 0)
        purposes = ["", "固定", "移动"]
        purpose = b2.selectbox("燃料用途", purposes, index=purposes.index(effective.get("用途")) if effective.get("用途") in purposes else 0)
        density = b3.text_input("密度 kg/L（需要时填写）", str(effective.get("密度kg/L", "")))
        density_source = st.text_input("密度来源或估算假设", str(effective.get("密度来源", "")))
        rp, rc = st.columns(2)
        row_province = rp.text_input("本条地区（留空用项目默认值）", str(effective.get("地区", "")))
        row_country = rc.text_input("本条国家（留空用项目默认值）", str(effective.get("国家", "")))
        category_codes = [""] + [c["活动类型"] for c in catalog.categories]
        b1, b2, b3 = st.columns(3)
        code = b1.selectbox("人工活动类型（留空按规则）", category_codes, index=category_codes.index(effective.get("确认活动类型", "")), format_func=lambda x: catalog.category_name(x) if x else "按规则判断")
        scope_options = ["范围1", "范围2", "范围3"]
        scope = b2.selectbox("人工范围（配合活动类型）", scope_options, index=scope_options.index(effective.get("确认范围")) if effective.get("确认范围") in scope_options else 0)
        substance = b3.text_input("具体物质或服务标签（需要时）", str(effective.get("物质", "")))
        factor_options = [""] + result.candidates
        factor_id = st.selectbox("候选因子（留空自动选择唯一候选）", factor_options, index=factor_options.index(effective.get("确认因子ID")) if effective.get("确认因子ID") in factor_options else 0)
        st.caption("先修改用途或活动类型并保存，系统会重新提供适用候选；无法选择全库中不适用的因子。")
        flags = {}
        cc = st.columns(3)
        for i, (key, label) in enumerate([("确认适用条件", "确认所选因子的适用条件"), ("确认代理", "确认国外代理适用性"),
                                         ("确认泄漏量", "确认是泄漏或合格维修补充量"), ("确认待核因子", "核实并接受待核因子估算"),
                                         ("标准体积已确认", "确认m³与因子标准状态一致"), ("车公里已确认", "确认距离是总车公里")]):
            flags[key] = "是" if cc[i % 3].checkbox(label, value=effective.get(key) == "是") else "否"
        p1, p2, p3 = st.columns(3)
        people = p1.text_input("人数（km转人公里）", str(effective.get("人数", "")))
        trips = p2.text_input("行程次数", str(effective.get("行程次数", 1)))
        mass = p3.text_input("载重t（km转吨公里）", str(effective.get("载重t", "")))
        group = st.text_input("同一活动计算组（仅需关联燃油与里程等替代记录时）", str(effective.get("计算组", "")))
        exclude = st.checkbox("不计入当前小计", value=effective.get("不计入") == "是")
        exclude_reason = st.text_input("排除原因", str(effective.get("排除原因", "")))
        submitted = st.form_submit_button("保存确认并重新计算", type="primary")
    if submitted:
        update = {"活动名称": new_name, "数量": quantity, "单位": unit, "设施归属": owner,
                  "用途": purpose, "密度kg/L": density, "密度来源": density_source,
                  "地区": row_province, "国家": row_country,
                  "确认活动类型": code, "确认范围": scope if code else "", "物质": substance,
                  "确认因子ID": factor_id, "人数": people, "行程次数": trips, "载重t": mass,
                  "计算组": group, "不计入": "是" if exclude else "否", "排除原因": exclude_reason, **flags}
        st.session_state.overrides[aid] = update
        st.rerun()
    if result.formula:
        st.success(result.formula)
    if ai_enabled:
        st.markdown("**AI建议需人工确认，不能直接改变结果。**")
        if st.button("获取这条记录的AI建议", key="ask_ai"):
            try:
                with st.spinner("请求建议…"):
                    feedback = suggest(effective, [catalog.factor(fid) for fid in result.candidates], [c["活动类型"] for c in catalog.categories])
                st.session_state.ai_feedback[aid] = feedback
                audit.log("ai_suggestion", aid, actor="AI建议", suggestion=feedback)
                st.session_state.history.append(audit.events[-1])
            except SuggestionError as e:
                st.warning(str(e))
        if aid in st.session_state.ai_feedback:
            st.json(st.session_state.ai_feedback[aid])
            st.caption("请核对后在上方表单选择。AI建议本身不计入结果。")

with tabs[2]:
    st.subheader("可追溯的精选因子")
    st.caption(f"当前 {len(catalog.factors)} 条候选 · 版本 {catalog.digest[:10]} · 查不到时留待人工补充")
    st.dataframe(display_frame(catalog.factors), hide_index=True, width="stretch",
                 column_config={"来源URL": st.column_config.LinkColumn("来源URL")})
    with st.expander("查看归类规则与GWP"):
        st.dataframe(display_frame(catalog.rules), hide_index=True)
        st.dataframe(display_frame(catalog.gwps), hide_index=True)
    st.info("请下载背景文件，在因子库中补充数值、单位、气体、来源、年份及适用条件，然后在左侧重新加载。")

with tabs[3]:
    st.subheader("本次会话审计记录")
    st.caption("每次有效计算记录输入、规则、候选、转换、因子快照和结果。下载后可保存依据；服务端不永久存储活动文件。")
    st.dataframe(display_frame(st.session_state.history), hide_index=True, width="stretch")
    log = "\n".join(json.dumps(e, ensure_ascii=False, default=str) for e in st.session_state.history)
    st.download_button("下载审计日志 JSONL", log, "audit.jsonl", mime="application/x-ndjson", on_click="ignore")
with tabs[4]:
    st.subheader("这个项目展示什么能力")
    st.markdown("- 将企业碳核算方法转成可执行规则，区分范围1/2/3。\n- 用Python完成单位转换和CO₂e计算，保留因子及来源。\n- 识别缺数据、缺因子和模糊活动，让人能够复核。\n- 通过Excel维护背景数据，可选AI只做有限候选建议。")
    st.markdown("**当前边界**：采用有限因子的估算原型。部分燃料仅含CO₂，国外数据需要代理判断。正式市场法、完整范围3清单、行业工艺排放和自动凭证核验尚未实现。")
    st.caption("适合演示碳核算分析、ESG数据管理和AI产品实现，不代表第三方核查或真实企业项目成果。")
