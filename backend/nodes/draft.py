"""5. 초안 생성: 수집한 근거만으로 쓰고, 문장마다 근거 ID 를 붙인다."""
import llm
import prompts
from logger import log
from nodes.common import catalog, checklist_text, request_text, section_titles
from schemas import Draft

STEP = "5 초안"


def draft(state: dict) -> dict:
    titles = dict(section_titles(state.get("is_reconsult", False)))
    cross = "\n".join(f"- [{c['verdict']}] {c['fact']} {c['note']}" for c in state.get("crosscheck", [])) or "(없음)"
    user = (f"{request_text(state)}\n\n의뢰의의 질문: {state['parsed']['questions']}\n\n"
            f"쓸 수 있는 섹션 (key: 제목):\n" + "\n".join(f"- {k}: {v}" for k, v in titles.items())
            + f"\n\n체크리스트 상태:\n{checklist_text(state['checklist'])}"
            + f"\n\n의뢰의 진술의 교차 확인 결과:\n{cross}"
            + f"\n\n수집된 근거:\n{catalog(state['evidence'])}")
    if state.get("is_reconsult"):
        user += ("\n\n재협진입니다. prior 섹션에 이전 의뢰와 회신을 2~3문장으로 요약하고 "
                 "(근거: consult:, reply: ID), 그 이후 새로 생긴 경과를 이어서 씁니다.")
    res = llm.structured(Draft, prompts.DRAFT, user)

    order = list(titles)
    sections, n = [], 0
    for sec in sorted(res.sections, key=lambda s: order.index(s.key) if s.key in order else 99):
        if sec.key not in titles or not sec.sentences:
            continue
        sentences = []
        for s in sec.sentences:
            n += 1
            sentences.append({"sid": f"s{n}", "text": s.text.strip(), "evidence_ids": list(s.evidence_ids),
                              "source": s.source})
        sections.append({"key": sec.key, "title": titles[sec.key], "sentences": sentences})
    questions = [{"text": q.text.strip(), "origin": q.origin, "reason": q.reason,
                  "approved": True if q.origin == "requester" else None}   # 제안 질문은 승인을 기다린다
                 for q in res.questions]
    log(STEP, f"섹션 {len(sections)}개, 문장 {n}개, 질문 {len(questions)}개 "
              f"(제안 {sum(q['origin'] == 'agent' for q in questions)}개)")
    return {"draft": {"sections": sections, "questions": questions, "next_sid": n + 1}}
