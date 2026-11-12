"""데이터 관리.

1) 리소스 JSON: 피의뢰과 프로파일, 의사 디렉터리, 의뢰서 템플릿
2) EMR 연결 (support/emr.py)
3) 의뢰별 폴더: support/consults/<의뢰번호>/
     request.json      UI 입력
     status.json       running / awaiting_approval / sent / replied / needs_attention / cancelled / error
     evidence.json     search_emr 로 모은 근거 풀 (ref → 행)
     draft_v1.json …   초안 버전별
     verify_v1.json …  버전별 근거 대조 결과
     trace.jsonl       툴 호출 기록 (audit_log 미들웨어)
     sent.json, <의뢰번호>.eml, sent.html   발송 기록
     reply.json        피의뢰과 회신
"""
import json
import secrets
from datetime import datetime
from functools import lru_cache
from threading import RLock

from support import settings
from support.emr import EMRDatabase, PatientEMR

RES = settings.SUPPORT / "resources"
LOCK = RLock()


# ---------------- 리소스 ----------------
@lru_cache
def load(name):
    return json.loads((RES / name).read_text(encoding="utf-8"))


@lru_cache
def profiles() -> dict:
    """dept_profile_*.json → {'감염내과': {...}}"""
    return {p["dept_name"]: p for p in (json.loads(f.read_text(encoding="utf-8"))
                                        for f in sorted(RES.glob("dept_profile_*.json")))}


def departments() -> list[str]:
    """협진을 보낼 수 있는 과: 프로파일이 있는 과 + 의사 디렉터리에 있는 과."""
    return list(dict.fromkeys([*profiles(), *(d["dept_name"] for d in doctors())]))


def profile_for(dept: str) -> dict:
    """프로파일이 없는 과는 체크리스트 없는 기본 프로파일 (Agent 가 의뢰 내용만 보고 판단)."""
    if dept in profiles():
        return profiles()[dept]
    return {"dept_name": dept or "(미정)", "question_types": [], "required_items": [],
            "draft_guidance": ["의뢰 내용에서 묻는 것과 직접 관련된 기록 위주로 쓸 것",
                               "의뢰 질문은 2~4개로 구체적으로, 한 문장에 하나씩 쓸 것 (번호는 자동으로 매겨지므로 붙이지 않는다)"]}


def doctors() -> list[dict]:
    return load("doctors.json")["doctors"]


def find_doctor(doctor_id: str):
    return next((d for d in doctors() if d["doctor_id"] == doctor_id), None)


def template() -> dict:
    return load("consult_template.json")


# ---------------- EMR ----------------
def _refresh_xlsx_emr():
    """가상 SQLite가 없거나 XLSX가 더 최신이면 자동으로 다시 만든다."""
    if settings.EMR_TABLE_STYLE == "mimiciv" or not settings.EMR_XLSX.exists():
        return
    db_path = settings.SUPPORT / "emr.sqlite"
    if db_path.exists() and db_path.stat().st_mtime >= settings.EMR_XLSX.stat().st_mtime:
        return
    from support.build_synthetic import main
    main()


@lru_cache
def emr_db() -> EMRDatabase:
    _refresh_xlsx_emr()
    return EMRDatabase(settings.EMR_URL, settings.EMR_TABLE_STYLE)


def patient_emr(request: dict) -> PatientEMR:
    return emr_db().for_patient(request["subject_id"], request["hadm_id"], request["consult_time"])


# ---------------- 의뢰 폴더 ----------------
def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Consult:
    def __init__(self, consult_id: str):
        self.id = consult_id
        self.dir = settings.CONSULT_DIR / consult_id
        if not self.dir.exists():
            raise FileNotFoundError(f"의뢰 {consult_id} 가 없습니다.")

    # --- 기본 입출력 ---
    def _read(self, name, default=None):
        p = self.dir / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

    def _write(self, name, obj):
        with LOCK:
            (self.dir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    @property
    def request(self) -> dict:
        return self._read("request.json")

    @property
    def profile(self) -> dict:
        return profile_for(self.request.get("consulted_dept", ""))

    def update_request(self, **fields):
        """Agent 가 정한 값(피의뢰과 등)을 요청에 반영한다."""
        with LOCK:
            self._write("request.json", {**self.request, **fields})

    @property
    def emr(self) -> PatientEMR:
        return patient_emr(self.request)

    # --- 상태 ---
    def status(self) -> dict:
        return self._read("status.json", {})

    def set_status(self, status: str, **extra):
        with LOCK:
            s = {**self.status(), "status": status, "updated_at": now(), **extra}
            self._write("status.json", s)

    # --- 근거 풀 ---
    def add_evidence(self, item_key: str, rows: list[dict]):
        with LOCK:
            ev = self._read("evidence.json", {})
            for r in rows:
                old = ev.get(r["ref"])
                if old and old.get("section") and r.get("section") and r["section"] not in old["section"]:
                    # 같은 퇴원요약지에서 다른 섹션(예: Allergies / Past Medical History)을 잘라 온 경우 덮어쓰지 않고 합친다
                    r = {**r, "section": old["section"] + "\n\n" + r["section"]}
                    item_key = old["item_key"] + "+" + item_key
                ev[r["ref"]] = {"item_key": item_key, **r}
            self._write("evidence.json", ev)

    def evidence(self) -> dict:
        return self._read("evidence.json", {})

    def retrieved_items(self) -> set:
        return {r["item_key"] for r in self.evidence().values()}

    # --- 초안 / 검증 ---
    def versions(self) -> list[int]:
        return sorted(int(p.stem.split("_v")[1]) for p in self.dir.glob("draft_v*.json"))

    def add_draft(self, draft: dict, feedback: str, from_physician: bool, plan: str = "") -> int:
        with LOCK:
            v = (self.versions() or [0])[-1] + 1
            self._write(f"draft_v{v}.json", {**draft, "version": v, "feedback": feedback, "plan": plan,
                                             "from_physician": from_physician, "created_at": now()})
        return v

    def draft(self, version: int | None = None):
        vs = self.versions()
        if not vs:
            return None
        return self._read(f"draft_v{version or vs[-1]}.json")

    def physician_feedback(self) -> str:
        return "\n".join(d["feedback"] for d in (self.draft(v) for v in self.versions())
                         if d.get("from_physician") and d.get("feedback"))

    def add_verification(self, report: dict):
        self._write(f"verify_v{report['draft_version']}.json", report)

    def verification(self, version: int | None = None):
        d = self.draft(version)
        return self._read(f"verify_v{d['version']}.json") if d else None

    def verifications(self) -> list[dict]:
        return [r for r in (self._read(f"verify_v{v}.json") for v in self.versions()) if r]

    # --- 기록 ---
    def log(self, tool: str, args: dict, result: str):
        with LOCK:
            step = len(self.trace()) + 1
            with open(self.dir / "trace.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"step": step, "tool": tool, "args": args, "result": result, "at": now()},
                                   ensure_ascii=False, default=str) + "\n")

    def trace(self) -> list[dict]:
        p = self.dir / "trace.jsonl"
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []

    def sent(self):
        return self._read("sent.json")

    def set_sent(self, sent: dict):
        self._write("sent.json", sent)

    def reply(self):
        return self._read("reply.json")

    def set_reply(self, reply: dict):
        self._write("reply.json", reply)

    def consultant(self):
        s = self.status()
        return find_doctor(s["consultant_id"]) if s.get("consultant_id") else None


def normalize_request(request: dict) -> dict:
    """의사가 비워 둔 칸을 디렉터리·EMR 로 채운다. 피의뢰과·진단은 비워 두면 Agent 몫으로 남긴다."""
    from support.schemas import ConsultRequest
    req = ConsultRequest.model_validate(request).model_dump()
    me = find_doctor(req["requesting_doctor_id"])
    if not me and not (req["requesting_doctor"] and req["requesting_dept"]):
        raise ValueError(f"의사 디렉터리에 없는 의뢰의 ID {req['requesting_doctor_id']}")
    req["requesting_doctor"] = req["requesting_doctor"] or me["name"]
    req["requesting_dept"] = req["requesting_dept"] or me["dept_name"]
    if req["consulted_dept"] and req["consulted_dept"] not in departments():
        raise ValueError(f"'{req['consulted_dept']}' 은 협진 가능한 과가 아닙니다. 가능: {departments()}")
    if not req["hadm_id"]:
        req["hadm_id"] = emr_db().active_admission(req["subject_id"], req["consult_time"])
        if not req["hadm_id"]:
            raise ValueError(f"환자 {req['subject_id']} 의 {req['consult_time']} 시점 입원 기록이 없습니다.")
    return req


def create_consult(request: dict) -> str:
    """의뢰 폴더를 만들고 의뢰번호를 돌려준다. 환자·입원·시점을 먼저 확인한다."""
    request = normalize_request(request)
    patient_emr(request).patient_header()  # 없는 환자/입원이면 여기서 ValueError
    cid = f"CR-{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
    d = settings.CONSULT_DIR / cid
    d.mkdir(parents=True)
    (d / "request.json").write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    Consult(cid).set_status("running", created_at=now())
    return cid


def list_consults(limit=50) -> list[dict]:
    if not settings.CONSULT_DIR.exists():
        return []
    out = []
    for d in sorted(settings.CONSULT_DIR.iterdir(), reverse=True)[:limit]:
        if (d / "request.json").exists():
            c = Consult(d.name)
            out.append({"consult_id": d.name, **c.status(), "request": c.request})
    return out


def document_html(c: Consult, version: int | None = None, with_reply: bool = False) -> str:
    """의뢰서 HTML (미리보기 / 발송본 / 회신 포함본)."""
    from support import render
    draft = c.draft(version)
    if not draft:
        return "<p>아직 초안이 없습니다.</p>"
    sent = c.sent() or {}
    h = render.header(c.id, c.request, c.emr.patient_header(), c.consultant())
    return render.render(h, draft, c.verification(draft["version"]),
                         addendum=sent.get("addendum", "") if sent.get("draft_version") == draft["version"] else "",
                         reply=c.reply() if with_reply else None)
