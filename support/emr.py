"""EMR 조회 계층 (SQLite 가상 데이터 / MIMIC-IV PostgreSQL 공통).

에이전트(LLM)는 SQL 을 직접 쓰지 않고 PatientEMR 의 함수만 부른다. 모든 함수는
  1) 협진 시점(consult_time)에 의료진이 실제로 볼 수 있었던 기록만 돌려주고
  2) 각 행에 근거 ID(ref = "테이블:기본키")를 붙인다.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import bindparam, create_engine, text

TS = "%Y-%m-%d %H:%M:%S"

TABLE_META = {
    "labevents": {"pk": "labevent_id", "avail": "storetime", "module": "hosp"},
    "microbiologyevents": {"pk": "microevent_id", "avail": "storetime", "module": "hosp"},
    "prescriptions": {"pk": "pharmacy_id", "avail": "starttime", "module": "hosp"},
    "emar": {"pk": "emar_id", "avail": "storetime", "module": "hosp"},
    "admissions": {"pk": "hadm_id", "avail": "admittime", "module": "hosp"},
    "patients": {"pk": "subject_id", "avail": None, "module": "hosp"},
    "radiology": {"pk": "note_id", "avail": "storetime", "module": "note"},
    "discharge": {"pk": "note_id", "avail": "storetime", "module": "note"},
}
OTHER_TABLES = {"transfers": "hosp", "services": "hosp", "d_labitems": "hosp", "radiology_detail": "note",
                "discharge_detail": "note", "diagnoses_icd": "hosp", "d_icd_diagnoses": "hosp"}


def parse(ts) -> datetime | None:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    return datetime.strptime(str(ts)[:19], TS)


def _norm(v):
    if isinstance(v, datetime):
        return v.strftime(TS)
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d") + " 00:00:00"
    if isinstance(v, Decimal):
        return float(v)
    return v


class EMRDatabase:
    """엔진은 앱 전체에서 하나만 만든다."""

    def __init__(self, url: str, table_style: str = "flat"):
        kw = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
        self.engine = create_engine(url, **kw)
        self.dialect = self.engine.dialect.name
        self.style = table_style

    def t(self, name: str) -> str:
        if self.style != "mimiciv":
            return name
        module = TABLE_META.get(name, {}).get("module") or OTHER_TABLES[name]
        return f"mimiciv_{module}.{name}"

    def ts(self, param: str) -> str:
        return f"CAST(:{param} AS TIMESTAMP)" if self.dialect == "postgresql" else f":{param}"

    def query(self, sql: str, params: dict, expanding: tuple[str, ...] = ()) -> list[dict]:
        stmt = text(sql)
        if expanding:
            stmt = stmt.bindparams(*[bindparam(e, expanding=True) for e in expanding])
        with self.engine.connect() as c:
            rows = c.execute(stmt, params).mappings().all()
        return [{k: _norm(v) for k, v in r.items()} for r in rows]

    def for_patient(self, subject_id: int, hadm_id: int, consult_time: str) -> "PatientEMR":
        return PatientEMR(self, subject_id, hadm_id, consult_time)

    # UI 보조: 환자의 입원 목록
    def admissions(self, subject_id: int) -> list[dict]:
        return self.query(f"SELECT hadm_id, admittime, dischtime, admission_type FROM {self.t('admissions')} "
                          "WHERE subject_id=:sid ORDER BY admittime DESC", {"sid": subject_id})

    def search_patients(self, query: str = "", limit: int = 10) -> list[dict]:
        """UI 검색용 환자 목록. 실제 MIMIC에는 이름이 없어 안전한 표시명으로 대체한다."""
        q = f"%{query.strip()}%"
        try:
            return self.query(
                f"SELECT subject_id, display_name, gender, anchor_age FROM {self.t('patients')} "
                "WHERE CAST(subject_id AS TEXT) LIKE :q OR display_name LIKE :q "
                "ORDER BY subject_id LIMIT :limit", {"q": q, "limit": max(1, min(limit, 50))})
        except Exception:
            rows = self.query(
                f"SELECT subject_id, gender, anchor_age FROM {self.t('patients')} "
                "WHERE CAST(subject_id AS TEXT) LIKE :q ORDER BY subject_id LIMIT :limit",
                {"q": q, "limit": max(1, min(limit, 50))})
            return [{**r, "display_name": f"환자 {r['subject_id']}"} for r in rows]

    def active_admission(self, subject_id: int, consult_time: str) -> int | None:
        """협진 시점에 입원 중인 건 (없으면 그 시점 이전의 가장 최근 입원)."""
        ct = parse(consult_time)
        rows = [a for a in self.admissions(subject_id) if parse(a["admittime"]) <= ct]
        cur = [a for a in rows if not a["dischtime"] or parse(a["dischtime"]) >= ct]
        pick = (cur or rows)[:1]
        return int(pick[0]["hadm_id"]) if pick else None

    def lab_labels(self) -> list[str]:
        return [r["label"] for r in self.query(f"SELECT label FROM {self.t('d_labitems')} ORDER BY label", {})]


class PatientEMR:
    def __init__(self, db: EMRDatabase, subject_id: int, hadm_id: int, consult_time: str):
        self.db, self.sid, self.hadm, self.ct = db, int(subject_id), int(hadm_id), consult_time
        self.ct_dt = parse(consult_time)

    def _p(self, **extra) -> dict:
        return {"sid": self.sid, "hadm": self.hadm, "ct": self.ct, **extra}

    def since(self, days: int) -> str:
        return (self.ct_dt - timedelta(days=days)).strftime(TS)

    @staticmethod
    def ref(table: str, row: dict) -> str:
        return f"{table}:{row[TABLE_META[table]['pk']]}"

    # ---------- 헤더 ----------
    def patient_header(self) -> dict:
        t, ts = self.db.t, self.db.ts
        p = self.db.query(f"SELECT * FROM {t('patients')} WHERE subject_id=:sid", self._p())
        a = self.db.query(f"SELECT * FROM {t('admissions')} WHERE hadm_id=:hadm AND subject_id=:sid", self._p())
        if not p or not a:
            raise ValueError(f"환자 {self.sid} / 입원 {self.hadm} 을 찾을 수 없습니다.")
        p, a = p[0], a[0]
        if parse(a["admittime"]) > self.ct_dt:
            raise ValueError("협진 시점이 입원일보다 앞섭니다.")
        svc = self.db.query(f"SELECT curr_service FROM {t('services')} WHERE hadm_id=:hadm AND transfertime<={ts('ct')} "
                            "ORDER BY transfertime DESC LIMIT 1", self._p())
        unit = self.db.query(f"SELECT careunit FROM {t('transfers')} WHERE hadm_id=:hadm AND intime<={ts('ct')} "
                             "AND careunit IS NOT NULL ORDER BY intime DESC LIMIT 1", self._p())
        return {"subject_id": self.sid, "hadm_id": self.hadm, "display_name": p.get("display_name") or f"환자 {self.sid}", "gender": p["gender"],
                "age": p["anchor_age"] + (self.ct_dt.year - p["anchor_year"]),
                "admittime": a["admittime"], "admission_type": a["admission_type"],
                "service": svc[0]["curr_service"] if svc else None,
                "careunit": unit[0]["careunit"] if unit else None}

    # ---------- Agent 가 조회 계획을 세우기 위한 목차 ----------
    def catalog(self) -> dict:
        """협진 시점까지 이 입원에 '어떤 기록이 얼마나 있는지'만 알려 준다 (값은 주지 않는다).
        Agent 는 이것과 의뢰 내용을 보고 무엇을 조회할지 스스로 정한다."""
        t, ts = self.db.t, self.db.ts
        p = self._p()
        labs = self.db.query(
            f"SELECT d.label, COUNT(*) AS n, MIN(l.charttime) AS first, MAX(l.charttime) AS last, "
            f"SUM(CASE WHEN l.flag='abnormal' THEN 1 ELSE 0 END) AS n_abnormal FROM {t('labevents')} l "
            f"JOIN {t('d_labitems')} d ON l.itemid=d.itemid WHERE l.subject_id=:sid AND l.hadm_id=:hadm "
            f"AND l.storetime<={ts('ct')} GROUP BY d.label ORDER BY d.label", p)
        micro = self.db.query(
            f"SELECT spec_type_desc, COUNT(DISTINCT micro_specimen_id) AS n_specimens, "
            f"MAX(CASE WHEN org_name IS NOT NULL THEN 1 ELSE 0 END) AS has_growth FROM {t('microbiologyevents')} "
            f"WHERE subject_id=:sid AND hadm_id=:hadm AND storetime<={ts('ct')} GROUP BY spec_type_desc", p)
        meds = self.db.query(
            f"SELECT DISTINCT drug FROM {t('prescriptions')} WHERE subject_id=:sid AND hadm_id=:hadm "
            f"AND starttime<={ts('ct')} ORDER BY drug", p)
        rad = self.db.query(
            f"SELECT r.charttime, d.field_value AS exam_name FROM {t('radiology')} r LEFT JOIN {t('radiology_detail')} d "
            f"ON r.note_id=d.note_id AND d.field_name='exam_name' WHERE r.subject_id=:sid AND r.hadm_id=:hadm "
            f"AND r.storetime<={ts('ct')} ORDER BY r.charttime", p)
        prior = self.db.query(
            f"SELECT COUNT(*) AS n FROM {t('discharge')} WHERE subject_id=:sid AND hadm_id<>:hadm AND storetime<={ts('ct')}", p)
        return {
            "labs": labs, "microbiology_specimens": micro, "medications_ordered": [m["drug"] for m in meds],
            "imaging": rad, "prior_discharge_notes": prior[0]["n"] if prior else 0,
            "all_lab_labels": self.db.lab_labels(),
        }

    def prior_diagnoses(self) -> list[str]:
        """과거 입원의 진단명 (조회 계획용 맥락. 현재 입원의 ICD 는 퇴원 시 부여되므로 협진 시점에 없다)."""
        t = self.db.t
        rows = self.db.query(
            f"SELECT DISTINCT d.long_title FROM {t('diagnoses_icd')} x JOIN {t('d_icd_diagnoses')} d "
            f"ON x.icd_code=d.icd_code AND x.icd_version=d.icd_version WHERE x.subject_id=:sid AND x.hadm_id<>:hadm",
            self._p())
        return [r["long_title"] for r in rows]

    # ---------- 항목별 조회 ----------
    def micro(self, window_days: int) -> list[dict]:
        t, ts = self.db.t, self.db.ts
        rows = self.db.query(
            f"SELECT * FROM {t('microbiologyevents')} WHERE subject_id=:sid AND hadm_id=:hadm "
            f"AND storetime<={ts('ct')} AND charttime>={ts('since')} ORDER BY charttime, micro_specimen_id, ab_name",
            self._p(since=self.since(window_days)))
        keep = ["charttime", "storetime", "spec_type_desc", "test_name", "org_name", "ab_name", "dilution_text",
                "interpretation", "comments"]
        return [{"ref": self.ref("microbiologyevents", r), **{k: r[k] for k in keep}} for r in rows]

    def prescriptions(self, keywords: list[str], window_days: int) -> list[dict]:
        t, ts = self.db.t, self.db.ts
        rows = self.db.query(
            f"SELECT * FROM {t('prescriptions')} WHERE subject_id=:sid AND hadm_id=:hadm AND starttime<={ts('ct')} "
            f"AND (stoptime IS NULL OR stoptime>={ts('since')}) ORDER BY starttime",
            self._p(since=self.since(window_days)))
        out = []
        for r in rows:
            if keywords and not any(k.lower() in (r["drug"] or "").lower() for k in keywords):
                continue
            active = r["stoptime"] is None or parse(r["stoptime"]) > self.ct_dt
            out.append({"ref": self.ref("prescriptions", r), "drug": r["drug"],
                        "dose": f'{r["dose_val_rx"]} {r["dose_unit_rx"]}', "route": r["route"],
                        "doses_per_24_hrs": r["doses_per_24_hrs"], "starttime": r["starttime"],
                        "stoptime": None if active else r["stoptime"],  # 미래 종료시각은 가린다
                        "status": "투여 중" if active else "종료"})
        return out

    def emar(self, keywords: list[str], window_days: int) -> list[dict]:
        t, ts = self.db.t, self.db.ts
        rows = self.db.query(
            f"SELECT * FROM {t('emar')} WHERE subject_id=:sid AND hadm_id=:hadm AND storetime<={ts('ct')} "
            f"AND charttime>={ts('since')} ORDER BY charttime", self._p(since=self.since(window_days)))
        return [{"ref": self.ref("emar", r), "medication": r["medication"], "charttime": r["charttime"],
                 "event_txt": r["event_txt"]}
                for r in rows if not keywords or any(k.lower() in (r["medication"] or "").lower() for k in keywords)]

    def labs(self, labels: list[str], window_days: int, include_prior_baseline: bool = False) -> list[dict]:
        t, ts = self.db.t, self.db.ts
        base = (f"SELECT l.*, d.label FROM {t('labevents')} l JOIN {t('d_labitems')} d ON l.itemid=d.itemid "
                f"WHERE l.subject_id=:sid AND d.label IN :labels AND l.storetime<={ts('ct')} ")
        rows = self.db.query(base + f"AND l.hadm_id=:hadm AND l.charttime>={ts('since')} ORDER BY d.label, l.charttime",
                             self._p(labels=labels, since=self.since(window_days)), expanding=("labels",))
        if include_prior_baseline:
            for lab in labels:
                rows += self.db.query(base + "AND l.hadm_id<>:hadm AND l.valuenum IS NOT NULL "
                                             "ORDER BY l.charttime DESC LIMIT 1",
                                      self._p(labels=[lab]), expanding=("labels",))
        return [{"ref": self.ref("labevents", r), "label": r["label"], "itemid": r["itemid"],
                 "charttime": r["charttime"], "value": r["valuenum"], "unit": r["valueuom"], "flag": r["flag"],
                 "baseline": r["hadm_id"] != self.hadm} for r in rows]

    def radiology(self, window_days: int) -> list[dict]:
        t, ts = self.db.t, self.db.ts
        rows = self.db.query(
            f"SELECT r.*, d.field_value AS exam_name FROM {t('radiology')} r LEFT JOIN {t('radiology_detail')} d "
            f"ON r.note_id=d.note_id AND d.field_name='exam_name' WHERE r.subject_id=:sid AND r.hadm_id=:hadm "
            f"AND r.storetime<={ts('ct')} AND r.charttime>={ts('since')} ORDER BY r.charttime",
            self._p(since=self.since(window_days)))
        return [{"ref": self.ref("radiology", r), "exam_name": r["exam_name"], "charttime": r["charttime"],
                 "text": r["text"]} for r in rows]

    def prior_discharge_section(self, section: str, max_notes: int = 3) -> list[dict]:
        """과거 입원 퇴원요약지에서 섹션 하나만 잘라 온다 (현재 입원의 퇴원요약지는 협진 시점에 없다)."""
        t, ts = self.db.t, self.db.ts
        rows = self.db.query(f"SELECT * FROM {t('discharge')} WHERE subject_id=:sid AND hadm_id<>:hadm "
                             f"AND storetime<={ts('ct')} ORDER BY charttime DESC LIMIT {int(max_notes)}", self._p())
        out = []
        for r in rows:
            txt = r["text"] or ""
            i = txt.find(section)
            if i < 0:
                continue
            m = re.search(r"\n[ \t]*\n", txt[i:])
            out.append({"ref": self.ref("discharge", r), "hadm_id": r["hadm_id"], "charttime": r["charttime"],
                        "section": txt[i: i + m.start() if m else None].strip()})
        return out

    # ---------- 검증용: 시점 필터 없이 원본 행 ----------
    def raw(self, table: str, pk_value) -> dict | None:
        meta = TABLE_META[table]
        if isinstance(pk_value, str) and pk_value.isdigit():
            pk_value = int(pk_value)
        rows = self.db.query(f"SELECT * FROM {self.db.t(table)} WHERE {meta['pk']}=:pk", {"pk": pk_value})
        return rows[0] if rows else None
