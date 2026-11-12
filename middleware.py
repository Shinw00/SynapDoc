"""SynapDoc Middleware.

  init_consult        before_agent   협진 요청을 받아 의뢰 폴더를 만들고 state 에 consult_id 를 넣는다
  guard_model_budget  before_model   모델 호출 한도 (한도를 넘으면 종료)
  audit_log           wrap_tool_call 모든 Tool 호출을 trace.jsonl 에 기록 (차단된 호출 포함)
  verify_gate         wrap_tool_call 검증을 통과하지 않은 초안의 발송 차단, 초안 작성 횟수 제한
  approval            HITL           send_email 실행 직전 의뢰의 승인 (승인 / 수정 / 반려)
"""
import json
from inspect import isawaitable

from langchain.agents.middleware import (
    AgentMiddleware, AgentState, HumanInTheLoopMiddleware, before_agent, before_model, wrap_tool_call,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import ValidationError
from typing_extensions import NotRequired

from support import data, settings
from tools import TOOLS

MAX_MODEL_CALLS = settings.MAX_MODEL_CALLS
MAX_DRAFTS = settings.MAX_DRAFTS


class ConsultState(AgentState):
    consult_id: NotRequired[str]
    request: NotRequired[dict]
    model_call_count: NotRequired[int]


# ───────────────────────── 0. 의뢰 시작 ─────────────────────────
def _request_from_messages(state):
    """Studio 에서는 채팅창에 의뢰 JSON 을 붙여 넣어 시작할 수 있다."""
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage) and isinstance(m.content, str):
            text = m.content
            i, j = text.find("{"), text.rfind("}")
            if i >= 0 and j > i:
                try:
                    return json.loads(text[i:j + 1])
                except json.JSONDecodeError:
                    return None
    return None


@before_agent(state_schema=ConsultState, can_jump_to=["end"])
def init_consult(state, runtime):
    if state.get("consult_id"):        # FastAPI 경로는 미리 만들어 넘긴다 / 승인 후 재개도 여기서 통과
        return None
    raw = state.get("request") or _request_from_messages(state)
    if not raw:
        return {"messages": [AIMessage(content="협진 요청 JSON 을 보내 주세요. 예시는 scenarios/patient1_request.json 입니다.")],
                "jump_to": "end"}
    try:
        cid = data.create_consult(raw)          # 빈 칸(입원·의뢰과 등)은 여기서 디렉터리·EMR 로 채운다
    except (ValidationError, ValueError) as e:
        return {"messages": [AIMessage(content=f"협진 요청을 시작할 수 없습니다: {e}")], "jump_to": "end"}
    return {"consult_id": cid, "request": data.Consult(cid).request}


# ───────────────────────── 1. 모델 호출 한도 ─────────────────────────
@before_model(state_schema=ConsultState, can_jump_to=["end"])
def guard_model_budget(state, runtime):
    n = state.get("model_call_count", 0)
    if n >= MAX_MODEL_CALLS:
        return {"messages": [AIMessage(content=f"모델 호출 한도({MAX_MODEL_CALLS}회)에 도달해 중단합니다. "
                                               "지금까지의 초안과 검증 결과를 확인해 주세요.")],
                "jump_to": "end"}
    return {"model_call_count": n + 1}


# ───────────────────────── 2. 검증 게이트 ─────────────────────────
def _block(call, reason: str, **extra) -> ToolMessage:
    return ToolMessage(content=json.dumps({"error": reason, **extra}, ensure_ascii=False),
                       tool_call_id=call["id"], name=call["name"], status="error")


def gate_error(request):
    """막아야 하면 오류 ToolMessage, 아니면 None."""
    call = request.tool_call
    cid = (request.state or {}).get("consult_id")
    if not cid:
        return None
    c = data.Consult(cid)
    if call["name"] == "draft_consult" and len(c.versions()) >= MAX_DRAFTS:
        return _block(call, f"초안 작성 최대 횟수({MAX_DRAFTS})를 넘었습니다. 남은 검증 문제를 요약해 의뢰의 확인을 요청하고 종료하세요.")
    if call["name"] == "send_email":
        if c.sent():
            return _block(call, "이미 발송된 의뢰입니다.")
        d = c.draft()
        rep = c.verification(d["version"]) if d else None
        if not d or not rep:
            return _block(call, "검증되지 않은 초안은 보낼 수 없습니다. verify_draft 를 먼저 실행하세요.")
        if not rep["passed"]:
            return _block(call, f"최신 초안 v{d['version']} 이 검증을 통과하지 못했습니다.", issues=rep["issues"])
    return None


@wrap_tool_call
def verify_gate(request, handler):
    error = gate_error(request)
    return error if error is not None else handler(request)


# ───────────────────────── 3. 기록 ─────────────────────────
def _summary(result) -> str:
    content = getattr(result, "content", "")
    if isinstance(content, str) and not content.lstrip().startswith("{"):
        # HITL edit 후에는 결과 앞에 안내문(원래 인자 JSON 포함)이 붙는다 → 맨 뒤의 JSON 을 찾는다
        for i in [k for k, ch in enumerate(content) if ch == "{"][::-1]:
            try:
                json.loads(content[i:])
                content = content[i:]
                break
            except ValueError:
                continue
    try:
        obj = json.loads(content)
        return ("차단/오류: " + obj["error"]) if "error" in obj else obj.get("summary", "")[:200]
    except (TypeError, ValueError):
        return str(content)[:200]


@wrap_tool_call
def audit_log(request, handler):
    result = handler(request)
    cid = (request.state or {}).get("consult_id")
    if cid:
        call = request.tool_call
        data.Consult(cid).log(call["name"], call["args"], _summary(result))
    return result


class _AsyncSafe(AgentMiddleware):
    """langgraph dev(Studio)는 비동기로 실행되므로 동기 wrap_tool_call 을 비동기에서도 쓰게 감싼다 (W05 와 같은 방식)."""

    def __init__(self, inner):
        super().__init__()
        self.inner = inner

    @property
    def name(self):
        return self.inner.name

    def wrap_tool_call(self, request, handler):
        return self.inner.wrap_tool_call(request, handler)

    async def awrap_tool_call(self, request, handler):
        if self.inner is verify_gate:
            error = gate_error(request)
            return error if error is not None else await handler(request)
        result = handler(request)
        result = await result if isawaitable(result) else result
        cid = (request.state or {}).get("consult_id")
        if cid:
            data.Consult(cid).log(request.tool_call["name"], request.tool_call["args"], _summary(result))
        return result


# ───────────────────────── 4. 의뢰의 승인 ─────────────────────────
def _describe(tool_call, state, runtime) -> str:
    c = data.Consult(state["consult_id"])
    d = c.draft()
    v = c.verification(d["version"]) if d else None
    to = data.find_doctor(tool_call["args"].get("to_doctor_id", ""))
    who = f"{to['dept_name']} {to['name']} {to['title']} ({to['email']})" if to else "?"
    return (f"초안 v{d['version'] if d else '?'}을 {who}에게 발송합니다. "
            f"근거 대조 {'통과' if v and v['passed'] else '미통과'} ({v['n_supported'] if v else 0}/{v['n_sentences'] if v else 0}문장). "
            f"미리보기: support/consults/{c.id}/draft_v{d['version'] if d else '?'}.json")


approval = HumanInTheLoopMiddleware(
    interrupt_on={
        "send_email": {"allowed_decisions": ["approve", "edit", "reject"], "description": _describe},
        **{t.name: False for t in TOOLS if t.name != "send_email"},
    },
    description_prefix="협진 의뢰서 발송 전 의뢰의 확인 / 승인·수정·반려",
)
validation = _AsyncSafe(verify_gate)
audit = _AsyncSafe(audit_log)
