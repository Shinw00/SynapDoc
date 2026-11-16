"""API 키 없이 전체 흐름을 확인한다.   python -m tests.test_offline"""
import os
import tempfile

tmp = tempfile.mkdtemp()
os.environ["CONSULT_DB_PATH"] = os.path.join(tmp, "consults.sqlite")
os.environ["CHECKPOINT_DB_PATH"] = os.path.join(tmp, "checkpoints.sqlite")
os.environ["MAIL_DRY_RUN"] = "true"

import json
from pathlib import Path

import llm
from tests.fake_llm import FakeLLM

fake = FakeLLM()
llm.get_llm, llm.structured = fake.get_llm, fake.structured

from langgraph.types import Command

from graph import build_graph
from support import consults

request = json.loads((Path(__file__).parent.parent / "support/test/scenarios.json").read_text(encoding="utf-8"))["1"]


def run_once(req, decision, thread="t1"):
    graph = build_graph()
    cfg = {"configurable": {"thread_id": thread}}
    out = graph.invoke({"request": req, "thread_id": thread}, cfg)
    review = out["__interrupt__"][0].value
    final = graph.invoke(Command(resume=decision), cfg)
    return review, final


def main():
    review, final = run_once(request, {"approved": True, "added_questions": ["문합부 인접 농양에 대한 경피적 배액술 필요 여부에 대해서도 의견 부탁드립니다."],
                                       "memo": "환자 보호자가 배액 시술에 대해 미리 설명 듣기를 원합니다."})
    texts = [s["text"] for sec in review["sections"] for s in sec["sentences"]]
    status = {c["key"]: c["status"] for c in review["checklist"]}

    assert all(v == "found" for v in status.values()), status                     # 보충 조회로 전부 채워짐
    assert not any("반코마이신" in t for t in texts), "지어낸 문장이 남아 있음"
    assert not any("5/17" in t for t in texts), "없는 근거를 단 문장이 남아 있음"
    assert any("5/15 215" in t for t in texts), "날짜 오류가 고쳐지지 않음"
    assert review["retry_count"] == 1 and not review["warnings"], review["warnings"]
    assert [c["verdict"] for c in review["crosscheck"]] == ["확인 불가", "일치", "일치", "일치"]
    assert "없는:ID" not in review["crosscheck"][2]["evidence_ids"]
    assert final["status"] == "sent" and final["mail"]["result"]["dry_run"] is True
    assert "경피적 배액술" in final["document"]["text"] and "(의뢰의 기재)" in final["document"]["text"]
    assert len(consults.list_for_patient(request["subject_id"])) == 1
    print("\n[통과] 신규 협진: 보충 조회, 검증, 재생성, 승인, 발송, 저장")

    # 거절하면 발송도 저장도 되지 않는다
    _, final = run_once(request, {"approved": False}, thread="t2")
    assert final["status"] == "cancelled" and not final.get("mail")
    assert len(consults.list_for_patient(request["subject_id"])) == 1
    print("[통과] 승인 거절: 발송하지 않음")

    # 회신을 저장한 뒤 나중 시점에 다시 의뢰하면 재협진으로 분류된다
    c = consults.list_for_patient(request["subject_id"])[0]
    consults.add_reply(c["consult_id"], "이서준", "메로페넴으로 변경하십시오.", "2181-05-16 13:40:00")
    later = {**request, "as_of": "2181-05-17 09:00:00"}
    review, _ = run_once(later, {"approved": False}, thread="t3")
    assert review["is_reconsult"] is True
    print("[통과] 재협진 분류")

    # 기준 시점을 앞당기면 그 뒤에 보고된 배양 결과는 근거로 쓸 수 없다
    early = {**request, "as_of": "2181-05-15 08:00:00"}
    review, _ = run_once(early, {"approved": False}, thread="t4")
    texts = " ".join(s["text"] for sec in review["sections"] for s in sec["sentences"])
    assert review["is_reconsult"] is False
    assert "ESCHERICHIA" not in texts and "MEROPENEM" not in texts, "기준 시점 이후 근거가 통과됨"
    print("[통과] 시점 필터: 5/15 08:00 기준에서는 5/16 에 보고된 배양 결과를 쓴 문장이 모두 걸러짐")


if __name__ == "__main__":
    main()
