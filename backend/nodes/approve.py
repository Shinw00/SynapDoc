"""8. 의사 승인: 초안과 근거를 보여주고 멈춘다. 승인이 와야 다음으로 간다.

interrupt 로 멈춘 뒤 다시 시작하면 이 노드는 처음부터 다시 실행된다.
그래서 interrupt 앞에는 되돌릴 수 없는 일을 두지 않는다.
"""
from langgraph.types import interrupt

from logger import log
from nodes.common import build_review

STEP = "8 승인"


def approve(state: dict) -> dict:
    decision = interrupt(build_review(state)) or {}
    draft = state["draft"]

    if not decision.get("approved"):
        log(STEP, "의뢰의가 승인하지 않음 → 발송하지 않고 종료")
        return {"approval": decision, "status": "cancelled"}

    edits = decision.get("edits") or {}                 # {문장 ID: 고친 문장}
    deleted = set(decision.get("deleted") or [])
    for sec in draft["sections"]:
        kept = []
        for s in sec["sentences"]:
            if s["sid"] in deleted:
                continue
            if s["sid"] in edits and edits[s["sid"]].strip() != s["text"]:
                s = {**s, "text": edits[s["sid"]].strip(), "source": "requester_edit"}   # 의뢰의가 고친 문장
            kept.append(s)
        sec["sentences"] = kept
    draft["sections"] = [sec for sec in draft["sections"] if sec["sentences"]]

    rejected = set(decision.get("rejected_questions") or [])   # 질문 목록에서의 순번 (0부터)
    questions = []
    for i, q in enumerate(draft["questions"]):
        if i in rejected:
            continue
        questions.append({**q, "approved": True})
    for text in decision.get("added_questions") or []:
        if text.strip():
            questions.append({"text": text.strip(), "origin": "added", "reason": "", "approved": True})
    draft["questions"] = questions

    request = {**state["request"]}
    if decision.get("recipient"):
        request["recipient"] = decision["recipient"]
    log(STEP, f"승인 (수정 {len(edits)}개, 삭제 {len(deleted)}개, 질문 추가 "
              f"{len(decision.get('added_questions') or [])}개, 질문 제외 {len(rejected)}개)")
    return {"approval": {**decision, "memo": (decision.get("memo") or "").strip()},
            "draft": draft, "request": request, "status": "approved"}
