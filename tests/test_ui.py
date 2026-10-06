from pathlib import Path
import pytest

streamlit=pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest
APP=Path(__file__).resolve().parents[1]/"app.py"


def test_demo_ui_and_rerun():
    at=AppTest.from_file(str(APP),default_timeout=30).run()
    assert not at.exception
    assert at.session_state["latest_summary"]["calculated_count"]==9
    before=at.session_state["latest_summary"]["total_kg"]
    at.run()
    assert not at.exception
    assert at.session_state["latest_summary"]["total_kg"]==before
    assert len(at.session_state["seen_runs"])==1


def test_ui_scenario_does_not_change_main_total():
    at=AppTest.from_file(str(APP),default_timeout=30).run()
    before=at.session_state["latest_summary"]["total_kg"]
    at.checkbox(key="enable_scenario").check().run()
    at.number_input(key="green").set_value(5000).run()
    assert not at.exception
    assert at.session_state["latest_summary"]["total_kg"]==before


def test_manual_diesel_review_updates_results():
    at=AppTest.from_file(str(APP),default_timeout=30).run()
    aid=at.session_state["latest_results"][9]["activity_id"]
    at.selectbox(key="review_id").set_value(aid).run()
    for widget in at.selectbox:
        if widget.label=="燃料用途":widget.set_value("移动")
    for widget in at.text_input:
        if widget.label=="密度 kg/L（需要时填写）":widget.set_value("0.84")
        if widget.label=="密度来源或估算假设":widget.set_value("虚构演示参数")
    for widget in at.button:
        if widget.label=="保存确认并重新计算":widget.click()
    at.run()
    assert not at.exception
    assert at.session_state["latest_summary"]["calculated_count"]==10
    assert at.session_state["latest_results"][9]["emission_kg"]==pytest.approx(50*.84/1000*3186.3)
