"""2. 체크리스트 구성: 고정 항목표를 깔고, 이 환자에게만 필요한 항목을 LLM 이 더한다."""
import copy

import config
import llm
import prompts
from logger import log
from nodes.common import request_text
from schemas import PlanAdjust

STEP = "2 체크리스트"


def plan(state: dict) -> dict:
    checklist = [{**copy.deepcopy(c), "status": "pending", "evidence_ids": []} for c in config.CHECKLIST]
    optional = [c for c in checklist if not c["required"]]
    user = (f"{request_text(state)}\n\n사실 진술: {state['parsed']['facts']}\n질문: {state['parsed']['questions']}\n\n"
            "현재 항목표:\n" + "\n".join(f"- {c['key']}: {c['item']} ({'필수' if c['required'] else '선택'})"
                                       for c in checklist)
            + f"\n\n선택 항목 key: {[c['key'] for c in optional]}\n쓸 수 있는 도구: {config.TOOL_NAMES}")
    try:
        adj = llm.structured(PlanAdjust, prompts.PLAN, user)
    except Exception as e:                       # 조정에 실패해도 고정 항목표로 진행한다
        log(STEP, f"조정 실패, 고정 항목표만 사용: {e}")
        adj = PlanAdjust()

    for c in checklist:
        if c["key"] in adj.promote:
            c["required"] = True
    for i, x in enumerate(adj.extras[:4], 1):    # 항목이 불어나지 않게 최대 4개
        checklist.append({"key": f"extra_{i}", "item": x.item, "required": True, "tool": x.tool,
                          "keyword": x.keyword, "days": 14, "status": "pending", "evidence_ids": [],
                          "added_by": "agent", "reason": x.reason})
    log(STEP, f"항목 {len(checklist)}개 (필수로 올림 {adj.promote}, 추가 {[x.item for x in adj.extras[:4]]})")
    return {"checklist": checklist}
