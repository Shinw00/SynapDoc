"""3단계(수집) 에이전트에 끼우는 미들웨어.

- 도구 호출 횟수와 LLM 호출 횟수에 상한을 둔다.
- 도구가 불릴 때마다 로그를 남기고, 허용되지 않은 인자(환자, 시점)를 넘기면 걸러낸다.
- 도구가 오류를 내도 에이전트가 멈추지 않도록 오류 내용을 결과로 돌려준다.
"""
from langchain.agents.middleware import (ModelCallLimitMiddleware, ToolCallLimitMiddleware,
                                         wrap_tool_call)
from langchain_core.messages import ToolMessage

import config
from logger import log

FORBIDDEN_ARGS = {"subject_id", "patient_id", "hadm_id", "as_of", "until", "before"}


@wrap_tool_call
def guard_and_log(request, handler):
    call = request.tool_call
    args = dict(call.get("args") or {})
    dropped = [k for k in args if k in FORBIDDEN_ARGS]
    if dropped:
        # 환자와 기준 시점은 Scope 로 고정돼 있다. LLM 이 넘기려 해도 무시한다.
        args = {k: v for k, v in args.items() if k not in FORBIDDEN_ARGS}
        request = request.override(tool_call={**call, "args": args})
        log("3 수집", f"허용되지 않은 인자 무시: {dropped}")
    log("3 수집", f"도구 호출 {call['name']} {args}")
    try:
        return handler(request)
    except Exception as e:                      # 도구 오류는 결과로 돌려준다
        log("3 수집", f"도구 오류 {call['name']}: {e}")
        return ToolMessage(content=f"도구 오류: {e}", tool_call_id=call["id"], status="error")


def build_middleware() -> list:
    return [
        ModelCallLimitMiddleware(run_limit=config.MAX_MODEL_CALLS, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=config.MAX_TOOL_CALLS, exit_behavior="continue"),
        guard_and_log,
    ]
