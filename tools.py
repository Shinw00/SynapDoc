import json

from langchain.tools import ToolRuntime, tool

from support import data, mailer
from support.verify import verify_draft as run_verify
from support.writer import get_writer


def _consult(runtime: ToolRuntime) -> data.Consult:
    return data.Consult(runtime.state["consult_id"])


def _j(x) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)


def _compact(row: dict) -> dict:
    """Agent 에게는 요약만 (토큰 절약). 전체 행은 evidence.json 에 있고 작성기가 읽는다."""
    return {k: (v[:160] + "…" if isinstance(v, str) and len(v) > 160 else v) for k, v in row.items()}


def _store(c: data.Consult, item_key: str, rows: list[dict], limit: int = 40) -> str:
    """조회 결과를 근거 풀에 넣고 Agent 에게는 요약만 돌려준다."""
    c.add_evidence(item_key, rows)
    return _j({"item": item_key, "n_rows": len(rows), "rows": [_compact(r) for r in rows[:limit]],
               "summary": f"{item_key}: {len(rows)}행",
               "note": "" if rows else "기록 없음. 필요하면 범위(days)·키워드를 바꿔 다시 조회하거나 초안에 '기록 없음'으로 쓴다."})


@tool
def get_patient_overview(runtime: ToolRuntime) -> str:
    """가장 먼저 호출한다. 의뢰의가 대강 적은 의뢰 내용, 환자 기본 정보, 과거 진단, 그리고 협진 시점까지 EMR 에
    '어떤 기록이 얼마나 있는지'(검사 항목별 건수·이상 건수, 배양 검체, 처방 약물명, 영상 목록)를 돌려준다.
    값은 주지 않으니, 이것과 의뢰 내용을 보고 어떤 search_* 툴을 어떤 인자로 부를지 계획한다."""
    c = _consult(runtime)
    e, req = c.emr, c.request
    h = e.patient_header()
    c.add_evidence("admission", [{"ref": f"admissions:{e.hadm}", "admittime": h["admittime"],
                                  "admission_type": h["admission_type"], "service": h["service"]}])
    return _j({"request": {k: req.get(k) for k in ("request_text", "diagnosis", "urgency", "consulted_dept",
                                                   "requesting_dept", "consult_time")},
               "patient": h, "prior_diagnoses": e.prior_diagnoses(),
               "emr_catalog": e.catalog(), "available_departments": data.departments(),
               "summary": "의뢰 내용·환자·EMR 목차"})


@tool
def get_dept_profile(dept: str, runtime: ToolRuntime) -> str:
    """피의뢰과를 정하고 그 과의 데이터 체크리스트(필수 여부·조회 방법 힌트)를 받는다.
    의뢰의가 피의뢰과를 비워 뒀다면 의뢰 내용을 보고 available_departments 중에서 골라 넣는다.
    의뢰의가 이미 지정했다면 그 과를 그대로 넣는다."""
    c = _consult(runtime)
    fixed = c.request.get("consulted_dept")
    if fixed and dept != fixed:
        dept, note = fixed, f"의뢰의가 지정한 '{fixed}' 를 사용합니다."
    elif dept not in data.departments():
        return _j({"error": f"'{dept}' 는 협진 가능한 과가 아닙니다.", "available_departments": data.departments()})
    else:
        note = "" if fixed else f"Agent 가 피의뢰과를 '{dept}' 로 정했습니다."
        c.update_request(consulted_dept=dept)
    p = data.profile_for(dept)
    items = [{k: it.get(k) for k in ("key", "label", "mandatory", "why", "fetch_hint")} for it in p["required_items"]]
    return _j({"dept": dept, "note": note,
               "question_types": [q["label"] for q in p["question_types"]],
               "checklist": items, "draft_guidance": p["draft_guidance"],
               "summary": f"{dept} 체크리스트 {len(items)}개 (필수 {sum(i['mandatory'] for i in items)})" if items
               else f"{dept}: 체크리스트 없음 → 의뢰 내용 기준으로 조회"})


@tool
def search_labs(labels: list[str], runtime: ToolRuntime, days: int = 7, include_baseline: bool = False) -> str:
    """검사 결과를 조회한다. labels 는 get_patient_overview 의 emr_catalog.all_lab_labels 에 있는 이름 그대로.
    days: 협진 시점 기준 며칠 전부터. include_baseline=true 면 과거 입원의 마지막 값(기저치)도 함께."""
    c = _consult(runtime)
    valid = c.emr.db.lab_labels()
    bad = [lb for lb in labels if lb not in valid]
    if bad or not labels:
        return _j({"error": f"알 수 없는 검사명 {bad}" if bad else "labels 가 비었습니다.", "valid_labels": valid})
    rows = c.emr.labs(labels, max(1, min(days, 60)), include_baseline)
    return _store(c, "labs:" + ",".join(labels), rows)


@tool
def search_medications(runtime: ToolRuntime, keywords: list[str] | None = None, days: int = 14,
                       include_administration: bool = False) -> str:
    """처방 약물을 조회한다(용량·경로·시작일·투여 중 여부). keywords 는 약물명 일부(영문, 대소문자 무시, 예: 'tazobactam', 'cef').
    비우면 기간 내 전체 처방. include_administration=true 면 실제 투여 기록(eMAR)도 함께 조회한다."""
    c = _consult(runtime)
    kws = [k for k in (keywords or []) if k.strip()]
    days = max(1, min(days, 60))
    rows = c.emr.prescriptions(kws, days)
    out = json.loads(_store(c, "medications:" + (",".join(kws) or "all"), rows))
    if include_administration:
        adm = c.emr.emar(kws, days)
        c.add_evidence("administration:" + (",".join(kws) or "all"), adm)
        out["administration"] = {"n_rows": len(adm), "rows": [_compact(r) for r in adm[:40]]}
        out["summary"] += f", 투여기록 {len(adm)}행"
    return _j(out)


@tool
def search_microbiology(runtime: ToolRuntime, days: int = 14, specimen: str = "") -> str:
    """배양 검사와 항생제 감수성을 조회한다. 음성 배양도 포함된다. specimen 으로 검체 종류를 거를 수 있다(예: 'BLOOD', 'URINE')."""
    c = _consult(runtime)
    rows = c.emr.micro(max(1, min(days, 60)))
    if specimen.strip():
        rows = [r for r in rows if specimen.lower() in (r["spec_type_desc"] or "").lower()]
    return _store(c, "micro" + (f":{specimen}" if specimen else ""), rows, limit=60)


@tool
def search_imaging(runtime: ToolRuntime, days: int = 14, keyword: str = "") -> str:
    """영상 판독문을 조회한다. keyword 를 주면 검사명이나 판독문에 그 단어가 있는 것만(예: 'CT', 'abscess')."""
    c = _consult(runtime)
    rows = c.emr.radiology(max(1, min(days, 60)))
    if keyword.strip():
        k = keyword.lower()
        rows = [r for r in rows if k in (r["exam_name"] or "").lower() or k in (r["text"] or "").lower()]
    return _store(c, "imaging" + (f":{keyword}" if keyword else ""), rows)


@tool
def search_prior_notes(section: str, runtime: ToolRuntime) -> str:
    """과거 입원 퇴원요약지에서 섹션 하나를 잘라 온다(현재 입원 퇴원요약지는 협진 시점에 없다).
    예: 'Allergies:', 'Past Medical History:', 'Discharge Medications:', 'Social History:'."""
    c = _consult(runtime)
    rows = c.emr.prior_discharge_section(section)
    return _store(c, f"notes:{section}", rows)


@tool
def draft_consult(plan: str, runtime: ToolRuntime, feedback: str = "", from_physician: bool = False) -> str:
    """근거 풀만 사용해 협진 의뢰서 초안을 작성한다. 이전 초안과 검증 결과는 자동으로 반영된다.
    plan 에는 Agent 가 조회 결과를 보고 정리한 작성 계획을 넣는다:
      - 의뢰의 메모를 해석한 핵심 임상 상황과 구체적 의뢰 질문 2~4개
      - 각 섹션에 담을 핵심 근거(ref)와 강조점 (예: 현재 항생제에 내성인 균)
      - 의뢰의 메모와 EMR 기록이 다른 부분 (기록 기준으로 쓴다)
    의뢰의의 수정 요청을 반영할 때는 그 내용을 feedback 에 넣고 from_physician=true."""
    c = _consult(runtime)
    if not c.evidence():
        return _j({"error": "근거 풀이 비어 있습니다. search_* 툴로 먼저 기록을 조회하세요."})
    draft = get_writer().write(c, data.template(), feedback, plan=plan)
    v = c.add_draft(draft, feedback, from_physician, plan=plan)
    n = sum(len(s["sentences"]) for s in draft["sections"])
    return _j({"version": v, "sections": [s["id"] for s in draft["sections"]], "n_sentences": n,
               "summary": f"v{v}, {len(draft['sections'])}개 섹션, {n}문장", "next": "verify_draft 로 검사하세요."})


@tool
def verify_draft(runtime: ToolRuntime) -> str:
    """최신 초안의 모든 문장을 EMR 원본과 대조한다: 근거 존재, 협진 시점 이후 정보 사용, 날짜·수치 일치,
    근거 없는 문장, 피의뢰과 필수 항목 누락. 발송 전 반드시 통과해야 한다."""
    c = _consult(runtime)
    draft = c.draft()
    if not draft:
        return _j({"error": "초안이 없습니다. draft_consult 를 먼저 호출하세요."})
    rep = run_verify(draft, c.emr, c.request, c.profile, data.template(), physician_feedback=c.physician_feedback())
    c.add_verification(rep)
    items = {it["key"]: it for it in c.profile["required_items"]}
    missing = [f"{items[k]['label']} → {items[k].get('fetch_hint', '')}" for k, ok in rep["coverage"].items() if not ok]
    nxt = (f"초안에 빠진 필수 항목 {missing}. 아직 조회하지 않았다면 해당 툴로 조회하고, 이미 조회했다면 plan 에 넣어 "
           "draft_consult 를 다시 호출하세요." if missing
           else "draft_consult 를 다시 호출하면 이슈가 자동 반영됩니다." if not rep["passed"]
           else "통과. find_consultant 후 send_email 을 호출하세요.")
    return _j({**rep, "next": nxt,
               "summary": f"v{rep['draft_version']} {'통과' if rep['passed'] else '실패'} "
                          f"({rep['n_supported']}/{rep['n_sentences']}), 이슈 {len(rep['issues'])}건"})


@tool
def find_consultant(runtime: ToolRuntime) -> str:
    """피의뢰 교수를 정한다. UI에서 지정했으면 그 교수, 비어 있으면 의뢰 내용과 세부전공이 가장 많이 겹치는 교수."""
    c = _consult(runtime)
    req = c.request
    if req.get("consulted_doctor_id"):
        doc, reason = data.find_doctor(req["consulted_doctor_id"]), "UI에서 지정"
        if not doc:
            return _j({"error": f"디렉터리에 없는 의사 ID {req['consulted_doctor_id']}"})
    else:
        if not req.get("consulted_dept"):
            return _j({"error": "피의뢰과가 정해지지 않았습니다. get_dept_profile(dept=...) 로 먼저 정하세요."})
        cands = [d for d in data.doctors() if d["dept_name"] == req["consulted_dept"]]
        if not cands:
            return _j({"error": f"{req['consulted_dept']} 소속 의사가 디렉터리에 없습니다."})
        text = req["request_text"] + " " + req.get("diagnosis", "")
        doc = max(cands, key=lambda d: sum(k in text for k in d["subspecialty"]))
        reason = f"세부전공 키워드 일치 {[k for k in doc['subspecialty'] if k in text]}"
    c.set_status(c.status().get("status", "running"), consultant_id=doc["doctor_id"])
    return _j({"doctor_id": doc["doctor_id"], "name": doc["name"], "email": doc["email"], "reason": reason,
               "summary": f"{doc['name']}({doc['doctor_id']}) - {reason}"})


@tool
def send_email(to_doctor_id: str, cover_message: str, runtime: ToolRuntime, physician_addendum: str = "") -> str:
    """최신 초안을 피의뢰 교수에게 메일로 보낸다. 실행 직전에 의뢰의 승인 단계가 자동으로 들어간다.
    cover_message 는 의뢰의 명의의 짧은 인사·요청 문구(2~3문장)."""
    c = _consult(runtime)
    if c.sent():
        return _j({"status": "already_sent", "summary": "이미 발송됨"})
    to = data.find_doctor(to_doctor_id)
    if not to:
        return _j({"error": f"디렉터리에 없는 의사 {to_doctor_id}"})
    c.set_status(c.status().get("status", "running"), consultant_id=to["doctor_id"])
    draft = c.draft()
    sent = {"to": to, "draft_version": draft["version"], "addendum": physician_addendum, "cover_message": cover_message}
    c.set_sent({**sent, "delivered": "pending"})        # 발송본 HTML 에 메모가 들어가도록 먼저 기록
    html = data.document_html(c)
    req = c.request
    sender = data.find_doctor(req["requesting_doctor_id"]) or {"name": req["requesting_doctor"],
                                                               "email": "noreply@synapdoc-hospital.test"}
    s1 = next((s["sentences"][0]["text"] for s in draft["sections"] if s["id"] == "S1" and s["sentences"]), "")
    qs = next((s["sentences"] for s in draft["sections"] if s["id"] == "S8"), [])
    msg = mailer.build_message(c.id, req, sender, to, cover_message, html,
                               [s1] + [f"질문 {i}: {q['text']}" for i, q in enumerate(qs, 1)])
    try:
        where = mailer.deliver(msg, c.dir)
    except Exception as e:  # noqa: BLE001
        (c.dir / "sent.json").unlink(missing_ok=True)
        return _j({"error": f"발송 실패: {e}"})
    (c.dir / "sent.html").write_text(html, encoding="utf-8")
    c.set_sent({**sent, "delivered": where, "sent_at": data.now()})
    c.set_status("sent")
    return _j({"status": "sent", "to": to["email"], "delivered": where, "summary": f"발송 → {to['email']} ({where})"})


TOOLS = [get_patient_overview, get_dept_profile, search_labs, search_medications, search_microbiology, search_imaging,
         search_prior_notes, draft_consult, verify_draft, find_consultant, send_email]
