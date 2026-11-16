"""1. 요청 해석: 입력을 사실 진술과 질문으로 나누고, 재협진인지 판단한다."""
from datetime import datetime

import config
import llm
import prompts
from logger import log
from schemas import ParsedRequest
from support import consults, db

STEP = "1 요청 해석"


def parse(state: dict) -> dict:
    req = dict(state["request"])
    req["as_of"] = db.normalize_time(req.get("as_of") or datetime.now().strftime(db.FMT))
    req.setdefault("urgency", "일반")
    subject_id = int(req["subject_id"])

    adm = db.current_admission(subject_id, req["as_of"])
    if adm is None:
        raise ValueError(f"기준 시점({req['as_of']})에 입원 중인 기록이 없습니다: 환자 {subject_id}")

    # 재협진 판단: 같은 환자의 이전 감염내과 협진이 있는가
    prior, evidence = [], {}
    for c in consults.list_for_patient(subject_id, config.TARGET_DEPT, before=req["as_of"]):
        replies = [r for r in c["replies"] if r["replied_at"] <= req["as_of"]]   # 기준 시점 이후 회신은 제외
        prior.append({"consult_id": c["consult_id"], "as_of": c["as_of"], "requester": c["requester"],
                      "document_text": c["document_text"], "replies": replies})
        evidence[f"consult:{c['consult_id']}"] = {
            "id": f"consult:{c['consult_id']}", "table": "consults", "kind": "prior", "time": c["as_of"],
            "dates": [c["as_of"]], "text": f"이전 협진 의뢰서 (기준 시점 {c['as_of'][:16]})\n{c['document_text']}"}
        for r in replies:
            evidence[f"reply:{r['reply_id']}"] = {
                "id": f"reply:{r['reply_id']}", "table": "replies", "kind": "prior", "time": r["replied_at"],
                "dates": [r["replied_at"]],
                "text": f"감염내과 회신 ({r['replier']}, {r['replied_at'][:16]})\n{r['text']}"}

    parsed = llm.structured(ParsedRequest, prompts.PARSE,
                            f"의뢰과: {req.get('requesting_dept')}\n의뢰의 입력:\n{req.get('request_text')}")
    log(STEP, f"사실 {len(parsed.facts)}개, 질문 {len(parsed.questions)}개, "
              f"{'재협진 (이전 ' + str(len(prior)) + '건)' if prior else '신규 협진'}")
    return {"request": req, "hadm_id": adm["hadm_id"], "is_reconsult": bool(prior),
            "prior_consults": prior, "parsed": parsed.model_dump(), "evidence": evidence,
            "retry_count": 0, "status": "running"}
