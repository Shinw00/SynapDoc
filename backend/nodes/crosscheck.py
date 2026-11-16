"""4. 교차 확인: 의뢰의가 말한 사실이 기록과 맞는지 본다."""
import llm
import prompts
from logger import log
from nodes.common import catalog
from schemas import CrossCheck

STEP = "4 교차 확인"


def crosscheck(state: dict) -> dict:
    facts = state["parsed"]["facts"]
    evidence = state["evidence"]
    if not facts:
        return {"crosscheck": []}
    try:
        res = llm.structured(CrossCheck, prompts.CROSSCHECK,
                             f"기준 시점: {state['request']['as_of']}\n\n사실 진술:\n"
                             + "\n".join(f"- {f}" for f in facts) + f"\n\n수집된 근거:\n{catalog(evidence)}")
        results = [r.model_dump() for r in res.results]
    except Exception as e:
        log(STEP, f"교차 확인 실패: {e}")
        results = [{"fact": f, "verdict": "확인 불가", "evidence_ids": [], "note": "교차 확인을 수행하지 못함"}
                   for f in facts]

    for r in results:
        r["evidence_ids"] = [i for i in r["evidence_ids"] if i in evidence]   # 없는 근거 ID 는 버린다
        if r["verdict"] == "일치" and not r["evidence_ids"]:
            r["verdict"], r["note"] = "확인 불가", "뒷받침하는 근거가 지정되지 않음"
    log(STEP, ", ".join(f"{r['verdict']}" for r in results))
    for r in results:
        if r["verdict"] != "일치":
            log(STEP, f"  {r['verdict']}: {r['fact']} — {r['note']}")
    return {"crosscheck": results}
