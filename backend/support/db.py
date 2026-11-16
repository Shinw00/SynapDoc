"""EMR 조회 계층. 읽기 전용이며, 모든 조회에 기준 시점(as_of) 필터가 들어간다.

- 도구(tools.py)와 검증 노드(nodes/verify.py)가 함께 쓴다.
- 조회 결과는 "근거(evidence)" 형태로 통일한다.
    {"id": "lab:1113", "table": "labevents", "kind": "renal",
     "time": "2181-05-16 07:10:00",   # 이 기록이 시스템에 들어온 시각 (시점 필터 기준)
     "dates": [...],                  # 기록에 들어 있는 모든 시각
     "text": "사람이 읽는 한 줄"}
- 시점 필터는 "측정 시각"이 아니라 "결과가 들어온 시각"으로 건다 (검사·배양·판독문은 storetime).
"""
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

import config

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
FMT = "%Y-%m-%d %H:%M:%S"


def _db_path() -> Path:
    p = Path(os.getenv("EMR_DB_PATH", "support/test/test.sqlite"))
    return p if p.is_absolute() else ROOT / p


def connect() -> sqlite3.Connection:
    path = _db_path()
    if not path.exists():
        # 테스트 DB 가 아직 없으면 xlsx 에서 만든다.
        from support.test import load_test
        if path == load_test.DB and load_test.XLSX.exists():
            load_test.build()
        else:
            raise FileNotFoundError(f"EMR DB 가 없습니다: {path}")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)   # 읽기 전용으로 연다
    con.row_factory = sqlite3.Row
    return con


def _q(sql: str, params: tuple = ()) -> list[dict]:
    con = connect()
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def has_table(name: str) -> bool:
    return bool(_q("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)))


def normalize_time(value: str) -> str:
    value = str(value).strip().replace("T", " ")
    for fmt in (FMT, "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime(FMT)
        except ValueError:
            pass
    raise ValueError(f"시각 형식을 읽을 수 없습니다: {value}")


def _since(as_of: str, days: int | None) -> str:
    if not days:
        return "0000-00-00 00:00:00"
    return (datetime.strptime(as_of, FMT) - timedelta(days=days)).strftime(FMT)


def _short(t) -> str:
    return str(t)[:16] if t else "-"


def _ev(eid, table, kind, time, text, dates) -> dict:
    return {"id": eid, "table": table, "kind": kind, "time": time, "text": text,
            "dates": [str(d) for d in dates if d]}


# ── 환자, 입원 ────────────────────────────────────────────────────────

def list_patients() -> list[dict]:
    return _q("SELECT subject_id, gender, anchor_age, anchor_year FROM patients ORDER BY subject_id")


def current_admission(subject_id: int, as_of: str) -> dict | None:
    """기준 시점에 입원 중인 입원 건."""
    rows = _q("""SELECT * FROM admissions
                 WHERE subject_id=? AND admittime<=? AND (dischtime IS NULL OR dischtime>?)
                 ORDER BY admittime DESC LIMIT 1""", (subject_id, as_of, as_of))
    return rows[0] if rows else None


def admission_info(subject_id: int, as_of: str) -> list[dict]:
    adm = current_admission(subject_id, as_of)
    pat = _q("SELECT * FROM patients WHERE subject_id=?", (subject_id,))
    if not adm or not pat:
        return []
    p = pat[0]
    age = int(p["anchor_age"]) + int(as_of[:4]) - int(p["anchor_year"])
    svc = _q("""SELECT curr_service FROM services WHERE hadm_id=? AND transfertime<=?
                ORDER BY transfertime DESC LIMIT 1""", (adm["hadm_id"], as_of)) if has_table("services") else []
    code = svc[0]["curr_service"] if svc else None
    dept = config.SERVICE_NAMES.get(code, code or "-")
    sex = {"M": "남성", "F": "여성"}.get(p["gender"], p["gender"])
    text = (f"환자 {subject_id}: {age}세 {sex}. 현재 입원 {adm['hadm_id']} "
            f"(입원 {_short(adm['admittime'])}, 유형 {adm['admission_type']}, 진료과 {dept}/{code}).")
    return [_ev(f"adm:{adm['hadm_id']}", "admissions", "admission", adm["admittime"], text,
                [adm["admittime"]])]


# ── 미생물 ────────────────────────────────────────────────────────────

def microbiology(subject_id: int, as_of: str, days: int | None = 14) -> list[dict]:
    """배양 결과와 감수성. 보고 시각(storetime)이 기준 시점 이전인 것만."""
    rows = _q("""SELECT * FROM microbiologyevents
                 WHERE subject_id=? AND storetime IS NOT NULL AND storetime<=? AND charttime>=?
                 ORDER BY charttime, micro_specimen_id, storetime, microevent_id""",
              (subject_id, as_of, _since(as_of, days)))
    return [_micro_ev(r) for r in rows]


def _micro_ev(r: dict) -> dict:
    parts = [f"{r['spec_type_desc']} (검체 {r['micro_specimen_id']}, 채취 {_short(r['charttime'])}, "
             f"보고 {_short(r['storetime'])})", f"검사: {r['test_name']}"]
    if r.get("org_name"):
        parts.append(f"균: {r['org_name']}")
    if r.get("ab_name"):
        parts.append(f"항생제: {r['ab_name']} MIC {r.get('dilution_text') or '-'} → 판정 {r.get('interpretation') or '-'}")
    if r.get("comments"):
        parts.append(f"비고: {r['comments']}")
    return _ev(f"micro:{r['microevent_id']}", "microbiologyevents", "microbiology", r["storetime"],
               " | ".join(parts), [r["charttime"], r["storetime"]])


# ── 검사 ──────────────────────────────────────────────────────────────

def lab_items() -> list[str]:
    return [r["label"] for r in _q("SELECT label FROM d_labitems ORDER BY label")]


def labs(subject_id: int, as_of: str, names: list[str], days: int | None = 7,
         scope: str = "current") -> list[dict]:
    """검사 수치. names 는 검사 이름의 일부 (예: 'Creatinine'). scope: current | past | all."""
    adm = current_admission(subject_id, as_of)
    hadm = adm["hadm_id"] if adm else -1
    where, params = ["l.subject_id=?", "l.storetime<=?"], [subject_id, as_of]
    if names:
        where.append("(" + " OR ".join("d.label LIKE ?" for _ in names) + ")")
        params += [f"%{n}%" for n in names]
    if scope == "current":
        where += ["l.hadm_id=?", "l.charttime>=?"]
        params += [hadm, _since(as_of, days)]
    elif scope == "past":
        where.append("(l.hadm_id IS NULL OR l.hadm_id<>?)")
        params.append(hadm)
    rows = _q(f"""SELECT l.*, d.label FROM labevents l JOIN d_labitems d ON d.itemid=l.itemid
                  WHERE {' AND '.join(where)} ORDER BY d.label, l.charttime""", tuple(params))
    return [_lab_ev(r, hadm) for r in rows]


def _lab_ev(r: dict, current_hadm) -> dict:
    past = r["hadm_id"] != current_hadm
    label = r["label"]
    if "creatinine" in label.lower():
        kind = "renal_baseline" if past else "renal"
    elif any(k in label.lower() for k in ("white blood", "c-reactive", "lactate")):
        kind = "inflammation"
    else:
        kind = "lab_other"
    flag = f", {r['flag']}" if r.get("flag") else ""
    where = f"과거 입원 {r['hadm_id']}" if past else "현재 입원"
    text = (f"{label} {r['value']} {r.get('valueuom') or ''} (채혈 {_short(r['charttime'])}, {where}, "
            f"참고범위 {r.get('ref_range_lower')}~{r.get('ref_range_upper')}{flag})")
    return _ev(f"lab:{r['labevent_id']}", "labevents", kind, r["storetime"], text,
               [r["charttime"], r["storetime"]])


# ── 처방, 투여 ────────────────────────────────────────────────────────

def prescriptions(subject_id: int, as_of: str, days: int | None = 14) -> list[dict]:
    """현재 입원의 처방. 기준 시점 이후에 끝나는 처방은 종료 시각을 숨기고 '투여 중'으로 본다."""
    adm = current_admission(subject_id, as_of)
    if not adm:
        return []
    rows = _q("""SELECT * FROM prescriptions
                 WHERE subject_id=? AND hadm_id=? AND starttime<=?
                   AND (stoptime IS NULL OR stoptime>=?)
                 ORDER BY starttime""", (subject_id, adm["hadm_id"], as_of, _since(as_of, days)))
    out = []
    for r in rows:
        active = r["stoptime"] is None or r["stoptime"] > as_of
        stop = "투여 중 (종료 시각 없음)" if active else f"종료 {_short(r['stoptime'])}"
        text = (f"{r['drug']} {r['dose_val_rx']} {r['dose_unit_rx']} {r['route']}, "
                f"1일 {r['doses_per_24_hrs']}회, 시작 {_short(r['starttime'])}, {stop}")
        out.append(_ev(f"rx:{r['pharmacy_id']}", "prescriptions", "antibiotics", r["starttime"], text,
                       [r["starttime"], None if active else r["stoptime"]]))
    return out


def administrations(subject_id: int, as_of: str, days: int | None = 14,
                    medication: str | None = None) -> list[dict]:
    """실제 투여 기록(emar). 처방만 되고 안 들어간 경우를 구분하는 데 쓴다."""
    if not has_table("emar"):
        return []
    where, params = ["subject_id=?", "charttime<=?", "charttime>=?"], [subject_id, as_of, _since(as_of, days)]
    if medication:
        where.append("medication LIKE ?")
        params.append(f"%{medication}%")
    rows = _q(f"SELECT * FROM emar WHERE {' AND '.join(where)} ORDER BY charttime", tuple(params))
    return [_ev(f"emar:{r['emar_id']}", "emar", "administration", r["charttime"],
                f"{r['medication']} {r['event_txt']} (투여 {_short(r['charttime'])})", [r["charttime"]])
            for r in rows]


# ── 판독문, 과거 기록 ─────────────────────────────────────────────────

def radiology(subject_id: int, as_of: str, days: int | None = 14) -> list[dict]:
    if not has_table("radiology"):
        return []
    rows = _q("""SELECT * FROM radiology WHERE subject_id=? AND storetime<=? AND charttime>=?
                 ORDER BY charttime""", (subject_id, as_of, _since(as_of, days)))
    return [_ev(f"rad:{r['note_id']}", "radiology", "imaging", r["storetime"],
                f"영상 판독문 (촬영 {_short(r['charttime'])}, 판독 {_short(r['storetime'])})\n{r['text']}",
                [r["charttime"], r["storetime"]]) for r in rows]


def past_records(subject_id: int, as_of: str) -> list[dict]:
    """과거 입원의 퇴원요약지와 진단 코드. 알레르기와 기저질환의 출처."""
    out = []
    if has_table("discharge"):
        for r in _q("""SELECT * FROM discharge WHERE subject_id=? AND storetime<=?
                       ORDER BY charttime""", (subject_id, as_of)):
            out.append(_ev(f"ds:{r['note_id']}", "discharge", "history", r["storetime"],
                           f"퇴원요약지 (입원 {r['hadm_id']}, 작성 {_short(r['storetime'])})\n{r['text']}",
                           [r["charttime"], r["storetime"]]))
    if has_table("diagnoses_icd"):
        # 진단 코드는 퇴원 후에 붙으므로, 기준 시점 전에 퇴원한 입원 것만 쓴다.
        for r in _q("""SELECT x.hadm_id, x.seq_num, x.icd_code, d.long_title, a.dischtime
                       FROM diagnoses_icd x
                       JOIN admissions a ON a.hadm_id=x.hadm_id
                       LEFT JOIN d_icd_diagnoses d ON d.icd_code=x.icd_code AND d.icd_version=x.icd_version
                       WHERE x.subject_id=? AND a.dischtime IS NOT NULL AND a.dischtime<=?
                       ORDER BY x.hadm_id, x.seq_num""", (subject_id, as_of)):
            out.append(_ev(f"dx:{r['hadm_id']}-{r['seq_num']}", "diagnoses_icd", "history", r["dischtime"],
                           f"과거 입원 {r['hadm_id']} 진단: {r['long_title'] or r['icd_code']} ({r['icd_code']})",
                           [r["dischtime"]]))
    return out


# ── 검증용 재조회 ─────────────────────────────────────────────────────

def refetch(evidence_id: str, subject_id: int, as_of: str) -> dict | None:
    """근거 ID 로 원본 행을 다시 조회한다. 기준 시점 이후의 행이면 None (TIME_LEAK 방지).

    검증 단계는 state 에 저장된 사본이 아니라 이 함수로 다시 읽은 원문과 대조한다.
    """
    table, _, key = evidence_id.partition(":")
    pool: list[dict]
    if table == "micro":
        pool = microbiology(subject_id, as_of, None)
    elif table == "lab":
        pool = labs(subject_id, as_of, [], None, "all")
    elif table == "rx":
        pool = prescriptions(subject_id, as_of, None)
    elif table == "emar":
        pool = administrations(subject_id, as_of, None)
    elif table == "rad":
        pool = radiology(subject_id, as_of, None)
    elif table in ("ds", "dx"):
        pool = past_records(subject_id, as_of)
    elif table == "adm":
        pool = admission_info(subject_id, as_of)
    else:
        return None
    for ev in pool:
        if ev["id"] == evidence_id and ev["time"] <= as_of:
            return ev
    return None
