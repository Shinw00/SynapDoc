"""승인된 초안을 의뢰서 글과 메일로 만든다. 여기서는 LLM 을 쓰지 않는다."""
import html

import config

MARK = {"requester": " (의뢰의 기재)", "requester_edit": " (의뢰의 수정)"}


def subject(state: dict) -> str:
    r = state["request"]
    head = "재협진의뢰" if state.get("is_reconsult") else "협진의뢰"
    return f"[{head}][{r.get('urgency', '일반')}] {r.get('requesting_dept')} → {config.TARGET_DEPT} | 환자 {r['subject_id']}"


def _sentences(sec: dict) -> str:
    return " ".join(s["text"] + MARK.get(s.get("source"), "") for s in sec["sentences"])


def _questions(draft: dict) -> list[str]:
    out = []
    for q in draft["questions"]:
        if q.get("approved"):
            out.append(q["text"] + (" (승인 단계에서 의뢰의가 추가)" if q["origin"] == "added" else ""))
    return out


def document_text(state: dict) -> str:
    r, draft = state["request"], state["draft"]
    lines = [subject(state),
             f"의뢰의: {r.get('requesting_dept')} {r.get('requester')} / 기준 시점: {r['as_of'][:16]}", ""]
    for sec in draft["sections"]:
        lines += [f"■ {sec['title']}", _sentences(sec), ""]
    qs = _questions(draft)
    if qs:
        lines += ["■ 의뢰 질문"] + [f"{i}. {q}" for i, q in enumerate(qs, 1)] + [""]
    memo = state.get("approval", {}).get("memo")
    if memo:
        lines += ["■ 의뢰의 추가 메모", memo, ""]
    return "\n".join(lines).strip()


def document_html(state: dict) -> str:
    r, draft = state["request"], state["draft"]
    e = html.escape
    parts = [f"<h2>{e(subject(state))}</h2>",
             f"<p>의뢰의: {e(str(r.get('requesting_dept')))} {e(str(r.get('requester')))} / "
             f"기준 시점: {e(r['as_of'][:16])}</p>"]
    for sec in draft["sections"]:
        parts.append(f"<h3>{e(sec['title'])}</h3><p>{e(_sentences(sec))}</p>")
    qs = _questions(draft)
    if qs:
        parts.append("<h3>의뢰 질문</h3><ol>" + "".join(f"<li>{e(q)}</li>" for q in qs) + "</ol>")
    memo = state.get("approval", {}).get("memo")
    if memo:
        parts.append(f"<h3>의뢰의 추가 메모</h3><p>{e(memo)}</p>")
    return ("<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'><title>협진 의뢰서</title></head>"
            "<body style='font-family:sans-serif;max-width:760px;margin:24px auto;line-height:1.6'>"
            + "".join(parts) + "</body></html>")


def mail_body(state: dict) -> str:
    """메일 본문. 검증을 통과한 '의뢰 사유' 문장을 그대로 쓰므로 새 내용이 들어가지 않는다."""
    r = state["request"]
    to = f"{r['recipient']} 교수님" if r.get("recipient") else f"{config.TARGET_DEPT} 교수님"
    reason = next((_sentences(s) for s in state["draft"]["sections"] if s["key"] == "reason"), "")
    return (f"{to}, {r.get('requesting_dept')} {r.get('requester')}입니다.\n\n{reason}\n\n"
            "협진 의뢰서 전문은 첨부 파일을 확인해 주십시오.").replace("\n\n\n\n", "\n\n")
