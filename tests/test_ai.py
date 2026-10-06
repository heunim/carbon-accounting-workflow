import json
import pytest
from carbonflow.ai_suggest import validate_suggestion,suggest,SuggestionError


def response(ids=None):
    return {"建议类别":"fuel","建议范围":"范围1","候选因子ID列表":ids or [],"理由":"用途需要确认","需补充信息":["设备用途"]}


def test_valid_suggestion_is_data_only():
    value=validate_suggestion(json.dumps(response(["F1"])),{"F1"},{"fuel"})
    assert value["候选因子ID列表"]==["F1"]


@pytest.mark.parametrize("payload", ["not json",json.dumps(response(["EVIL"])),json.dumps(dict(response(),因子值=2.3)),json.dumps(dict(response(),建议范围="范围4"))])
def test_invalid_ai_response_rejected(payload):
    with pytest.raises(SuggestionError):validate_suggestion(payload,{"F1"},{"fuel"})


def test_empty_candidates_cannot_invent_ids():
    with pytest.raises(SuggestionError):validate_suggestion(json.dumps(response(["F1"])),set(),{"fuel"})


def test_no_key_is_optional():
    with pytest.raises(SuggestionError,match="未配置"):
        suggest({},[],[],config={})


def test_mock_http_and_timeout():
    cfg={"key":"test-secret","base_url":"https://example.invalid/v1","model":"test-model"}
    requests=[]
    class Reply:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,*args):return json.dumps({"choices":[{"message":{"content":json.dumps(response())}}]}).encode()
    def mock(request,timeout):
        requests.append(request)
        return Reply()
    assert suggest({"数量":999,"企业名称":"private","活动名称":"柴油","单位":"L"},[],["fuel"],cfg,mock)["建议类别"]=="fuel"
    assert b"999" not in requests[0].data and b"private" not in requests[0].data
    def timeout(*args,**kwargs):raise TimeoutError()
    with pytest.raises(SuggestionError):suggest({},[],["fuel"],cfg,timeout)
