"""3. 수집 (자율 구간): 에이전트가 체크리스트의 빈 항목을 보고 도구를 골라 조회한다.

이 노드에서만 LLM 이 경로를 정한다. 다만 결과는 코드가 다시 확인한다.
- 항목의 상태(확보/기록 없음)는 LLM 의 말이 아니라 실제로 모인 근거로 정한다.
- 에이전트가 조회하지 않고 넘어간 항목은 코드가 기본 조회로 채운다.
"""
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

import llm
import prompts
from logger import log
from middleware import build_middleware
from nodes.common import checklist_text, request_text
from tools import EvidenceStore, Scope, make_tools, run_tool

STEP = "3 수집"


def _matches(item: dict, evidence: dict[str, dict]) -> list[str]:
    """이 항목을 채우는 근거 ID."""
    key = item["key"]
    if item.get("keyword"):
        kw = item["keyword"].lower()
        return [i for i, e in evidence.items() if kw in e["text"].lower() and e["kind"] != "prior"]
    if key == "allergy":
        return [i for i, e in evidence.items() if e["table"] == "discharge" and "allerg" in e["text"].lower()]
    return [i for i, e in evidence.items() if e["kind"] == key]


def _queried(item: dict, calls: list[dict]) -> bool:
    """이 항목에 해당하는 조회가 이미 있었는가."""
    for c in calls:
        if c["tool"] != item["tool"]:
            continue
        if item["tool"] != "get_labs":
            return True
        names = [n.lower() for n in (c["args"].get("names") or [])]
        wanted = [n.lower() for n in (item.get("labs") or [item.get("keyword", "")])]
        name_ok = not names or any(w in n or n in w for w in wanted for n in names)
        scope = c["args"].get("scope", "current")
        scope_ok = scope == "all" or scope == item.get("scope", "current")
        if name_ok and scope_ok:
            return True
    return False


def _default_args(item: dict) -> dict:
    if item["tool"] == "get_labs":
        return {"names": item.get("labs") or [item.get("keyword", "")],
                "days": item.get("days", 7), "scope": item.get("scope", "current")}
    if item["tool"] in ("get_past_records", "get_admission_info"):
        return {}
    return {"days": item.get("days", 14)}


def update_checklist(checklist: list[dict], store: EvidenceStore) -> list[dict]:
    out = []
    for item in checklist:
        ids = _matches(item, store.evidence)
        status = "found" if ids else ("none" if _queried(item, store.calls) else "pending")
        out.append({**item, "status": status, "evidence_ids": ids})
    return out


def collect(state: dict) -> dict:
    req = state["request"]
    scope = Scope(subject_id=int(req["subject_id"]), as_of=req["as_of"])
    store = EvidenceStore()
    checklist = state["checklist"]

    user = (f"{request_text(state)}\n\n체크리스트:\n{checklist_text(checklist)}")
    if state.get("is_reconsult"):
        last = state["prior_consults"][-1]["as_of"]
        user += f"\n\n재협진입니다. 이전 협진의 기준 시점은 {last} 입니다. 그 이후의 변화가 드러나도록 조회하세요."

    try:
        agent = create_agent(llm.get_llm(), make_tools(scope, store),
                             system_prompt=prompts.COLLECT, middleware=build_middleware())
        agent.invoke({"messages": [HumanMessage(user)]}, config={"recursion_limit": 60})
    except Exception as e:                       # 에이전트가 실패해도 아래 보충 조회로 필수 항목은 채운다
        log(STEP, f"에이전트 오류, 보충 조회로 진행: {e}")
    agent_calls = len(store.calls)

    # 에이전트가 조회하지 않은 항목은 코드가 기본 조회로 채운다
    checklist = update_checklist(checklist, store)
    for item in checklist:
        if item["status"] == "pending":
            log(STEP, f"보충 조회: {item['item']}")
            run_tool(item["tool"], _default_args(item), scope, store)
    checklist = update_checklist(checklist, store)

    summary = ", ".join(f"{c['item'].split(' (')[0]}={'확보' if c['status'] == 'found' else '없음'}" for c in checklist)
    log(STEP, f"에이전트 조회 {agent_calls}회, 보충 {len(store.calls) - agent_calls}회, 근거 {len(store.evidence)}건")
    log(STEP, summary)
    return {"checklist": checklist, "evidence": {**state.get("evidence", {}), **store.evidence},
            "tool_log": store.calls}
