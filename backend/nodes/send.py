"""9. 메일 생성과 저장: 승인된 의뢰서를 보내고, 재협진에 쓰도록 협진 이력에 남긴다.

그래프에서 이 노드로 오는 길은 '승인됨' 하나뿐이다. (graph.py 의 route_after_approve)
"""
import os

import config
import render
from logger import log
from support import consults, mailer

STEP = "9 발송"


def send(state: dict) -> dict:
    if state.get("status") != "approved":            # 승인 없이는 절대 보내지 않는다
        raise RuntimeError("승인되지 않은 의뢰서는 발송할 수 없습니다.")
    r = state["request"]
    text, html = render.document_text(state), render.document_html(state)
    to = config.RECIPIENTS.get(r.get("recipient") or "") or os.getenv("MAIL_TO_DEFAULT") or None
    mail = {"to": to, "subject": render.subject(state), "body": render.mail_body(state)}

    try:
        result = mailer.send(to, mail["subject"], mail["body"], f"consult_{r['subject_id']}.html", html)
        status = "sent"
    except Exception as e:
        log(STEP, f"메일 발송 실패: {e}")
        result, status = {"sent": False, "error": str(e)}, "mail_failed"
    mail["result"] = result

    consult_id = consults.save_consult(
        thread_id=state.get("thread_id"), subject_id=int(r["subject_id"]), hadm_id=state.get("hadm_id"),
        requesting_dept=r.get("requesting_dept"), requester=r.get("requester"),
        target_dept=config.TARGET_DEPT, recipient=r.get("recipient"), urgency=r.get("urgency"),
        as_of=r["as_of"], request_text=r.get("request_text"), document_text=text,
        document_json={"draft": state["draft"], "verification": state.get("verification", [])},
        mail_json=mail, status=status)
    how = "시험 모드 (outbox 에 저장)" if result.get("dry_run") else ("발송 완료" if result.get("sent") else "실패")
    log(STEP, f"{mail['subject']} → {to or '수신 주소 없음'} : {how}, 협진 이력 #{consult_id}")
    return {"document": {"text": text, "html": html}, "mail": mail, "consult_id": consult_id, "status": status}
