"""여러 노드가 같이 쓰는 작은 함수들."""
import config


def catalog(evidence: dict[str, dict]) -> str:
    """근거 목록을 LLM 에게 보여줄 글로 만든다."""
    if not evidence:
        return "(수집된 근거 없음)"
    return "\n".join(f"[{e['id']}] {e['text']}" for e in evidence.values())


def checklist_text(checklist: list[dict]) -> str:
    label = {"pending": "미탐색", "found": "확보", "none": "기록 없음"}
    lines = []
    for c in checklist:
        hint = f"도구 {c['tool']}"
        if c.get("labs"):
            hint += f", 검사 {c['labs']}, 범위 {c.get('scope', 'current')}"
        if c.get("keyword"):
            hint += f", 검색어 {c['keyword']}"
        need = "필수" if c["required"] else "선택"
        lines.append(f"- [{label[c['status']]}] {c['item']} ({need}; {hint})")
    return "\n".join(lines)


def request_text(state: dict) -> str:
    r = state["request"]
    kind = "재협진" if state.get("is_reconsult") else "신규 협진"
    return (f"의뢰과: {r.get('requesting_dept')} / 의뢰의: {r.get('requester')} / 수신과: {config.TARGET_DEPT}\n"
            f"응급도: {r.get('urgency')} / 기준 시점: {r['as_of']} / 구분: {kind}\n"
            f"의뢰의 입력:\n{r.get('request_text')}")


def all_sentences(draft: dict) -> list[dict]:
    return [s for sec in draft.get("sections", []) for s in sec["sentences"]]


def section_titles(is_reconsult: bool) -> list[tuple[str, str]]:
    return ([config.PRIOR_SECTION] if is_reconsult else []) + config.SECTIONS


def build_review(state: dict) -> dict:
    """승인 화면에 보여줄 내용. 8단계 interrupt 와 API 조회가 같은 모양을 쓴다."""
    ver = {v["sid"]: v for v in state.get("verification", [])}
    sections = []
    for sec in state.get("draft", {}).get("sections", []):
        sections.append({"key": sec["key"], "title": sec["title"], "sentences": [
            {**s, "verdict": ver.get(s["sid"], {}).get("verdict"),
             "reason": ver.get(s["sid"], {}).get("reason", "")} for s in sec["sentences"]]})
    used = {i for s in all_sentences(state.get("draft", {})) for i in s.get("evidence_ids", [])}
    used |= {i for c in state.get("crosscheck", []) for i in c.get("evidence_ids", [])}
    evidence = state.get("evidence", {})
    return {
        "request": state.get("request"),
        "is_reconsult": state.get("is_reconsult", False),
        "sections": sections,
        "questions": state.get("draft", {}).get("questions", []),
        "crosscheck": state.get("crosscheck", []),
        "checklist": [{k: c.get(k) for k in ("key", "item", "required", "status", "evidence_ids")}
                      for c in state.get("checklist", [])],
        "warnings": [v for v in state.get("verification", []) if v["verdict"] in ("불일치", "근거 없음")],
        "evidence": {i: evidence[i] for i in used if i in evidence},   # 화면에서 문장을 누르면 보여줄 원문
        "retry_count": state.get("retry_count", 0),
    }
