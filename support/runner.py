"""FastAPI·CLI 공통 실행기: 그래프 실행 → (send_email 직전 정지) → 의뢰의 결정으로 재개 → 종료.

Studio(langgraph dev)는 이 파일을 쓰지 않는다. Studio 가 직접 실행·정지·재개를 관리한다.
"""
import json
import threading

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from support import data
from support.schemas import Decision

CANCEL_MSG = "[협진 취소] 의뢰의가 협진을 취소했습니다. 더 이상 Tool 을 호출하지 말고 종료하세요."
_locks: dict[str, threading.Lock] = {}


def _lock(cid):
    return _locks.setdefault(cid, threading.Lock())


def cfg(cid: str) -> dict:
    return {"configurable": {"thread_id": cid}, "recursion_limit": 100}


def kickoff_message(request: dict) -> str:
    return "다음 협진 요청에 대한 의뢰서를 작성해 승인 후 발송해 주세요.\n" + json.dumps(request, ensure_ascii=False, indent=1)


def start(graph, cid: str):
    """처음 실행. 승인 대기 또는 종료까지 진행 (수십 초~수 분 → API 는 백그라운드로)."""
    with _lock(cid):
        c = data.Consult(cid)
        _drive(graph, cid, lambda: graph.invoke(
            {"messages": [HumanMessage(content=kickoff_message(c.request))], "consult_id": cid, "request": c.request},
            cfg(cid)))


def submit_decision(cid: str, decision) -> tuple[dict, bool]:
    """결정을 검사하고 상태를 즉시 running 으로 바꾼다 (빠름)."""
    d = decision if isinstance(decision, Decision) else Decision.model_validate(decision)
    with _lock(cid):
        c = data.Consult(cid)
        st = c.status()
        if st.get("status") != "awaiting_approval":
            raise ValueError(f"승인 대기 상태가 아닙니다 (현재: {st.get('status')}).")
        pending = st["pending"]
        if d.type == "approve":
            hitl = {"type": "approve"}
        elif d.type == "edit":
            args = dict(pending["args"])
            for k in ("to_doctor_id", "cover_message", "physician_addendum"):
                if getattr(d, k) is not None:
                    args[k] = getattr(d, k)
            hitl = {"type": "edit", "edited_action": {"name": pending["name"], "args": args}}
        elif d.type == "reject":
            if not d.message.strip():
                raise ValueError("수정 요청에는 메시지가 필요합니다.")
            hitl = {"type": "reject", "message": f"[의뢰의 수정 요청] {d.message}"}
        else:
            hitl = {"type": "reject", "message": CANCEL_MSG + (f" 사유: {d.message}" if d.message else "")}
        c.set_status("running", pending=None)
        label = {"approve": "승인", "edit": "수정 후 승인", "reject": "수정 요청", "cancel": "협진 취소"}[d.type]
        c.log("doctor_decision", d.model_dump(exclude_none=True), f"의뢰의 {label}" + (f": {d.message}" if d.message else ""))
    return hitl, d.type == "cancel"


def resume(graph, cid: str, hitl: dict, cancelled: bool = False):
    with _lock(cid):
        _drive(graph, cid, lambda: graph.invoke(Command(resume={"decisions": [hitl]}), cfg(cid)), cancelled)


def decide(graph, cid: str, decision):
    resume(graph, cid, *submit_decision(cid, decision))


def _drive(graph, cid: str, invoke, cancelled: bool = False):
    c = data.Consult(cid)
    try:
        result = invoke()
    except Exception as e:  # noqa: BLE001
        c.set_status("error", error=f"{type(e).__name__}: {e}")
        return
    if "__interrupt__" in result:
        req = result["__interrupt__"][0].value["action_requests"][0]
        c.set_status("awaiting_approval", pending={"name": req["name"], "args": req["args"],
                                                   "description": req.get("description", "")})
        return
    final = result["messages"][-1].content if result.get("messages") else ""
    if isinstance(final, list):
        final = " ".join(p.get("text", "") for p in final if isinstance(p, dict))
    status = "sent" if c.sent() and c.sent().get("delivered") != "pending" else "cancelled" if cancelled else "needs_attention"
    c.set_status(status, final_message=final, pending=None)


def view(cid: str) -> dict:
    """UI 가 폴링하는 상태 묶음."""
    c = data.Consult(cid)
    st, d = c.status(), c.draft()
    return {"consult_id": cid, "status": st.get("status"), "request": c.request, "pending": st.get("pending"),
            "consultant_id": st.get("consultant_id"), "sent": c.sent(), "reply": c.reply(),
            "final_message": st.get("final_message"), "error": st.get("error"),
            "latest_draft_version": d["version"] if d else None,
            "verifications": c.verifications(), "trace": c.trace()}
