from langchain.agents import create_agent

from middleware import ConsultState, approval, audit, guard_model_budget, init_consult, validation
from tools import TOOLS


def build_graph(model, system_prompt, checkpointer=None):
    """단계별 Middleware 등록.
      1  init_consult + guard_model_budget           (모델 호출 한도)
      2  + verify_gate                                (검증 전 발송 차단)
      3  + approval                                   (발송 전 의뢰의 승인)
      4  + audit_log                                  (전체: 모든 Tool 호출 기록 → UI 진행 상황)
    wrap_tool_call 은 리스트 앞쪽이 바깥에서 감싼다. audit 을 verify_gate 보다 앞에 둬야 차단된 호출도 기록된다.
    """
    layers = [init_consult, guard_model_budget, audit, validation, approval]
    return create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=system_prompt,
        middleware=layers,
        state_schema=ConsultState,
        checkpointer=checkpointer,
    )
