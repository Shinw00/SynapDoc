"""9단계를 잇는 그래프.

    1 요청 해석 → 2 체크리스트 → 3 수집 → 4 교차 확인 → 5 초안 → 6 검증
                                                              ↑        │ 문제 있음 (최대 MAX_REVISE 회)
                                                         7 재생성 ←────┤
                                                                       ↓ 문제 없음 또는 횟수 소진
                                                                  8 의사 승인 (여기서 멈춤)
                                                                       │ 승인      │ 거절
                                                                  9 발송·저장      끝

순서는 고정이다. LLM 이 경로를 정하는 곳은 3단계 안쪽뿐이다.
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

import config
from nodes.approve import approve
from nodes.collect import collect
from nodes.crosscheck import crosscheck
from nodes.draft import draft
from nodes.parse import parse
from nodes.plan import plan
from nodes.revise import revise
from nodes.send import send
from nodes.verify import has_issues, verify
from state import State


def route_after_verify(state: dict) -> str:
    if has_issues(state) and state.get("retry_count", 0) < config.MAX_REVISE:
        return "revise"
    return "approve"          # 남은 문제는 경고로 표시해 의사에게 넘긴다


def route_after_approve(state: dict) -> str:
    return "send" if state.get("status") == "approved" else END


def build_graph(checkpointer=None):
    g = StateGraph(State)
    for name, fn in [("parse", parse), ("plan", plan), ("collect", collect), ("crosscheck", crosscheck),
                     ("draft", draft), ("verify", verify), ("revise", revise), ("approve", approve),
                     ("send", send)]:
        g.add_node(name, fn)
    g.add_edge(START, "parse")
    g.add_edge("parse", "plan")
    g.add_edge("plan", "collect")
    g.add_edge("collect", "crosscheck")
    g.add_edge("crosscheck", "draft")
    g.add_edge("draft", "verify")
    g.add_conditional_edges("verify", route_after_verify, ["revise", "approve"])
    g.add_edge("revise", "verify")
    g.add_conditional_edges("approve", route_after_approve, ["send", END])
    g.add_edge("send", END)
    # 8단계에서 멈췄다가 이어가려면 상태를 저장해 둘 곳(checkpointer)이 필요하다
    return g.compile(checkpointer=checkpointer or MemorySaver())
