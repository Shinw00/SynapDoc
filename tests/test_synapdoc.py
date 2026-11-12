import json
import sqlite3

from fakes import COVER, ScriptedModel, ScriptedWriter, call, patient1_script
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from graph import build_graph
from llm import make_prompt
from support import data, runner, settings
from support.verify import verify_draft
from support.writer import set_writer


def _graph(script, checkpointer=None):
    return build_graph(ScriptedModel(script=script, cursor=[0]), make_prompt(),
                       checkpointer or InMemorySaver())


def test_time_filter_excludes_future_records(request_p1):
    e = data.patient_emr(request_p1)
    abx = e.prescriptions(["tazobactam", "penem", "cef"], 14)
    assert {r["drug"] for r in abx} == {"CeFAZolin", "Piperacillin-Tazobactam"}
    assert next(r for r in abx if r["drug"] == "Piperacillin-Tazobactam")["status"] == "투여 중"
    cr = e.labs(["Creatinine"], 7, include_prior_baseline=True)
    assert 1.9 not in [r["value"] for r in cr] and any(r["baseline"] and r["value"] == 0.8 for r in cr)
    assert [r["ref"] for r in e.prior_discharge_section("Allergies:")] == ["discharge:90000001-DS-3"]


def test_verify_catches_injected_errors(request_p1):
    draft = ScriptedWriter().write(None, None, "") | {"version": 1}
    rep = verify_draft(draft, data.patient_emr(request_p1), request_p1, data.profiles()["감염내과"], data.template())
    assert sorted(i["type"] for i in rep["issues"]) == ["MISSING_REQUIRED", "TIME_LEAK", "UNSUPPORTED", "VALUE_MISMATCH"]


def test_studio_style_start_from_json_message(request_p1):
    g = _graph([AIMessage(content="", tool_calls=[call("get_patient_overview", cid="a")]), AIMessage(content="확인")])
    out = g.invoke({"messages": [HumanMessage(content=json.dumps(request_p1, ensure_ascii=False))]},
                   {"configurable": {"thread_id": "studio-1"}})
    cid = out["consult_id"]
    assert data.Consult(cid).request["subject_id"] == 90000001
    bad = _graph([AIMessage(content="x")]).invoke({"messages": [HumanMessage(content="안녕")]},
                                                  {"configurable": {"thread_id": "studio-2"}})
    assert "JSON" in bad["messages"][-1].content


def test_full_flow_restart_reject_edit_reply(request_p1):
    set_writer(ScriptedWriter())
    script = patient1_script()
    model = ScriptedModel(script=script, cursor=[0])

    def fresh_graph():   # 서버 재시작 흉내: 매번 새 그래프 + 같은 SQLite 체크포인트 파일
        cp = SqliteSaver(sqlite3.connect(str(settings.CHECKPOINT_DB), check_same_thread=False))
        cp.setup()
        return build_graph(model, make_prompt(), cp)

    cid = data.create_consult(request_p1)
    runner.start(fresh_graph(), cid)
    v = runner.view(cid)
    assert v["status"] == "awaiting_approval" and v["latest_draft_version"] == 2
    assert [r["passed"] for r in v["verifications"]] == [False, True]

    runner.decide(fresh_graph(), cid, {"type": "reject", "message": "의뢰 질문에 농양 배액술 필요 여부도 추가해 주세요."})
    v = runner.view(cid)
    assert v["status"] == "awaiting_approval" and v["latest_draft_version"] == 3

    runner.decide(fresh_graph(), cid, {"type": "edit", "physician_addendum": "보호자가 배액 시술 설명을 원합니다."})
    v = runner.view(cid)
    assert v["status"] == "sent" and v["sent"]["to"]["doctor_id"] == "ID-01"
    c = data.Consult(cid)
    assert (c.dir / "sent.eml").exists() and "보호자가" in (c.dir / "sent.html").read_text(encoding="utf-8")
    tools_logged = [t["tool"] for t in v["trace"]]
    assert v["trace"][-1]["result"].startswith("발송 →")
    assert tools_logged[0] == "get_patient_overview" and tools_logged.count("send_email") == 1   # 반려된 호출은 실행 안 됨
    assert [t["result"] for t in v["trace"] if t["tool"] == "doctor_decision"] == [
        "의뢰의 수정 요청: 의뢰 질문에 농양 배액술 필요 여부도 추가해 주세요.", "의뢰의 수정 후 승인"]
    assert sorted(p.name for p in c.dir.glob("draft_v*.json")) == ["draft_v1.json", "draft_v2.json", "draft_v3.json"]


def test_async_path_like_studio(request_p1):
    """langgraph dev(Studio)는 ainvoke 로 실행한다: 비동기에서도 게이트·기록·승인 정지가 동작해야 한다."""
    import asyncio

    from langgraph.types import Command
    set_writer(ScriptedWriter())
    g = _graph(patient1_script())
    cfg = {"configurable": {"thread_id": "studio-async"}}

    async def go():
        out = await g.ainvoke({"messages": [HumanMessage(content=json.dumps(request_p1, ensure_ascii=False))]}, cfg)
        assert "__interrupt__" in out
        cid = out["consult_id"]
        out = await g.ainvoke(Command(resume={"decisions": [{"type": "reject", "message": "배액술 질문 추가"}]}), cfg)
        assert "__interrupt__" in out
        out = await g.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), cfg)
        return cid, out

    cid, out = asyncio.run(go())
    c = data.Consult(cid)
    assert c.sent() and c.status()["status"] == "sent" and len(c.versions()) == 3
    assert any(t["tool"] == "verify_draft" for t in c.trace())


def test_rough_request_fills_admission_and_requester():
    req = data.normalize_request({"requesting_doctor_id": "SUR-01", "subject_id": 90000001,
                                  "request_text": "열남. 항생제 봐주세요", "consult_time": "2181-05-16 11:30:00"})
    assert req["hadm_id"] == 90100001 and req["requesting_dept"] == "외과" and req["consulted_dept"] == ""


def test_agent_picks_dept_and_chooses_search_args():
    """피의뢰과를 비워 두면 Agent 가 고른다. 검사명이 틀리면 유효 목록을 돌려줘 Agent 가 스스로 고치게 한다."""
    req = {"requesting_doctor_id": "SUR-01", "subject_id": 90000001, "request_text": "Cr 오르는데 pip/tazo 용량 괜찮은지",
           "consult_time": "2181-05-16 11:30:00"}
    script = [AIMessage(content="", tool_calls=[call("get_patient_overview", cid="a")]),
              AIMessage(content="", tool_calls=[call("get_dept_profile", {"dept": "신장내과"}, "b")]),
              AIMessage(content="", tool_calls=[call("search_labs", {"labels": ["Cr"]}, "c")]),
              AIMessage(content="", tool_calls=[call("search_labs", {"labels": ["Creatinine"], "include_baseline": True}, "d"),
                                                call("search_medications", {"keywords": ["tazobactam"]}, "e")]),
              AIMessage(content="끝")]
    out = _graph(script).invoke({"messages": [HumanMessage(content=json.dumps(req, ensure_ascii=False))]},
                                {"configurable": {"thread_id": "rough-1"}})
    c = data.Consult(out["consult_id"])
    assert c.request["consulted_dept"] == "신장내과" and c.profile["required_items"] == []
    tool_msgs = {m.tool_call_id: json.loads(m.content) for m in out["messages"] if getattr(m, "tool_call_id", None)}
    assert "Creatinine" in tool_msgs["c"]["valid_labels"]
    assert "Lactate" in [x["label"] for x in tool_msgs["a"]["emr_catalog"]["labs"]]
    assert {e["item_key"] for e in c.evidence().values()} == {"admission", "labs:Creatinine", "medications:tazobactam"}
    assert any(e.get("baseline") for e in c.evidence().values())


def test_same_note_sections_are_merged_not_overwritten(request_p1):
    """알레르기와 과거력은 같은 퇴원요약지(ref)에서 나온다. 나중 조회가 앞 조회를 덮어쓰면 안 된다."""
    c = data.Consult(data.create_consult(request_p1))
    for sec in ("Allergies:", "Past Medical History:"):
        c.add_evidence(f"notes:{sec}", c.emr.prior_discharge_section(sec))
    (row,) = c.evidence().values()
    assert "Allergies:" in row["section"] and "Past Medical History:" in row["section"]
