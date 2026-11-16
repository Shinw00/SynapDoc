"""7. 재생성: 검증에서 걸린 문장만 고친다. 전체를 다시 쓰지 않는다."""
import llm
import prompts
from logger import log
from nodes.common import all_sentences, catalog
from schemas import Revision

STEP = "7 재생성"


def revise(state: dict) -> dict:
    draft = state["draft"]
    bad = {v["sid"]: v for v in state["verification"] if v["verdict"] in ("불일치", "근거 없음")}
    sentences = {s["sid"]: s for s in all_sentences(draft)}
    listing = "\n".join(f"- {sid} | 문장: {sentences[sid]['text']} | 인용: {sentences[sid]['evidence_ids']} "
                        f"| 문제: {v['reason']}" for sid, v in bad.items() if sid in sentences)
    res = llm.structured(Revision, prompts.REVISE,
                         f"기준 시점: {state['request']['as_of']}\n\n고칠 문장:\n{listing}\n\n"
                         f"수집된 근거:\n{catalog(state['evidence'])}")

    fixes = {f.sid: f for f in res.fixes if f.sid in bad}      # 문제없는 문장은 건드리지 못하게 한다
    replaced = deleted = 0
    for sec in draft["sections"]:
        kept = []
        for s in sec["sentences"]:
            f = fixes.get(s["sid"])
            if f is None:
                kept.append(s)
            elif f.action == "delete" or not f.text.strip():
                deleted += 1
            else:
                kept.append({**s, "text": f.text.strip(), "evidence_ids": list(f.evidence_ids), "source": f.source})
                replaced += 1
        sec["sentences"] = kept
    draft["sections"] = [sec for sec in draft["sections"] if sec["sentences"]]
    log(STEP, f"수정 {replaced}개, 삭제 {deleted}개")
    return {"draft": draft, "retry_count": state.get("retry_count", 0) + 1}
