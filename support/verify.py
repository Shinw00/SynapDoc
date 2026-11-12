"""근거 대조 검사 (verify_draft).

초안의 모든 문장은 evidence(근거 ref 목록)를 달고 나온다. 이 모듈은 LLM을 쓰지 않고
DB 원본을 다시 읽어 다음을 확인한다.

  NOT_FOUND       근거로 단 ref 가 DB에 없음 (LLM이 ID를 지어냄)
  WRONG_PATIENT   다른 환자의 기록을 근거로 씀
  TIME_LEAK       협진 시점 이후에야 알 수 있었던 기록을 씀
  QUOTE_MISMATCH  노트 인용문이 원문에 없음
  DATE_MISMATCH   문장 속 날짜가 근거 기록의 날짜와 다름
  VALUE_MISMATCH  문장 속 숫자가 근거 기록의 값에 없음
  UNSUPPORTED     근거가 하나도 없는 문장
  MISSING_REQUIRED  감염내과 프로파일의 필수 항목이 초안 어디에도 근거로 안 들어감
  MISSING_SECTION   템플릿 필수 섹션이 비어 있음

숫자/날짜 대조는 규칙 기반이라 '의미'까지는 못 본다(예: S/R 을 뒤바꿔 쓴 경우).
그 부분은 semantic_check 훅에 LLM 판정을 붙여 보완하도록 남겨 두었다.
"""
from __future__ import annotations

import re

from support.emr import PatientEMR as EMR, TABLE_META, parse

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})|(?<![\d.])(\d{1,2})/(\d{1,2})(?![\d/])")
TIME_RE = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
NUM_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")
TIME_COLS = ("charttime", "storetime", "starttime", "stoptime", "admittime", "intime", "scheduletime", "chartdate")
NON_VALUE_COLS = set(TIME_COLS) | {"subject_id", "hadm_id", "labevent_id", "specimen_id", "microevent_id",
                                   "micro_specimen_id", "pharmacy_id", "poe_seq", "emar_seq", "note_seq", "itemid",
                                   "spec_itemid", "test_itemid", "org_itemid", "ab_itemid", "storedate",
                                   "transfer_id", "ref_range_lower", "ref_range_upper", "anchor_year"}


def _norm_evidence(ev) -> tuple[str, str | None]:
    if isinstance(ev, dict):
        return ev["ref"], ev.get("quote")
    return ev, None


def _numbers(text: str) -> set[float]:
    return {float(x) for x in NUM_RE.findall(text)}


def _strip_dates_times(text: str) -> str:
    return TIME_RE.sub(" ", DATE_RE.sub(" ", text))


def _dates_in(text: str) -> list[str]:
    """문장 속 날짜를 '-MM-DD' 또는 'YYYY-MM-DD' 형태로."""
    out = []
    for full, mm, dd in DATE_RE.findall(text):
        out.append(full if full else f"-{int(mm):02d}-{int(dd):02d}")
    return out


def _row_value_numbers(table: str, row: dict) -> set[float]:
    nums = set()
    for k, v in row.items():
        if k in NON_VALUE_COLS or v is None:
            continue
        if k == "text":  # 노트 본문은 인용문으로만 대조한다
            continue
        nums |= _numbers(str(v))
    if table == "prescriptions" and row.get("doses_per_24_hrs"):
        nums.add(round(24 / float(row["doses_per_24_hrs"]), 2))  # '6시간 간격' 같은 표현 허용
    return nums


def _row_times(row: dict) -> list[str]:
    return [str(row[c]) for c in TIME_COLS if row.get(c)]


def verify_draft(draft: dict, emr: EMR, request: dict, profile: dict, template: dict,
                 physician_feedback: str = "", semantic_check=None) -> dict:
    issues, coverage_hits, n_sent, n_ok = [], [], 0, 0
    section_policy = {s["id"]: s["evidence_policy"] for s in template["sections"]}

    for sec in draft["sections"]:
        policy = section_policy.get(sec["id"], "emr")
        for s in sec["sentences"]:
            n_sent += 1
            before = len(issues)
            text, evs = s["text"], s.get("evidence", [])
            if not evs:
                issues.append({"sid": s["sid"], "type": "UNSUPPORTED", "detail": "근거가 없는 문장"})
                continue

            ev_numbers, ev_times, ev_texts = set(), [], []
            for ev in evs:
                ref, quote = _norm_evidence(ev)
                table, _, key = ref.partition(":")

                if table == "request":
                    if key not in request:
                        issues.append({"sid": s["sid"], "type": "NOT_FOUND", "detail": f"UI 입력에 {key} 없음"})
                        continue
                    ev_texts.append(str(request[key]))
                    ev_numbers |= _numbers(str(request[key]))
                    continue
                if table == "physician":
                    if policy != "request_or_physician" or not physician_feedback:
                        issues.append({"sid": s["sid"], "type": "UNSUPPORTED",
                                       "detail": "의사 피드백 근거는 의뢰 질문 섹션에서만, 피드백이 있을 때만 허용"})
                    else:
                        ev_texts.append(physician_feedback)
                        ev_numbers |= _numbers(physician_feedback)
                    continue
                if table not in TABLE_META:
                    issues.append({"sid": s["sid"], "type": "NOT_FOUND", "detail": f"알 수 없는 테이블 {table}"})
                    continue

                row = emr.raw(table, int(key) if key.isdigit() else key)
                if row is None:
                    issues.append({"sid": s["sid"], "type": "NOT_FOUND", "detail": f"{ref} 가 DB에 없음"})
                    continue
                if row.get("subject_id") not in (None, emr.sid):
                    issues.append({"sid": s["sid"], "type": "WRONG_PATIENT", "detail": ref})
                    continue

                avail_col = TABLE_META[table]["avail"]
                avail = row.get(avail_col) if avail_col else None
                if table == "discharge" and row["hadm_id"] == emr.hadm:
                    issues.append({"sid": s["sid"], "type": "TIME_LEAK",
                                   "detail": f"{ref}: 현재 입원의 퇴원요약지는 협진 시점에 존재하지 않음"})
                    continue
                if avail and parse(avail) > emr.ct_dt:
                    issues.append({"sid": s["sid"], "type": "TIME_LEAK",
                                   "detail": f"{ref}: {avail_col}={avail} > 협진시점 {emr.ct}"})
                    continue

                if quote is not None and quote not in (row.get("text") or ""):
                    issues.append({"sid": s["sid"], "type": "QUOTE_MISMATCH", "detail": f"{ref}: 인용문이 원문에 없음"})
                    continue

                coverage_hits.append({"table": table, "row": row, "quote": quote})
                ev_numbers |= _row_value_numbers(table, row) | (_numbers(quote) if quote else set())
                ev_times += _row_times(row)
                if quote:
                    ev_texts.append(quote)

            if len(issues) > before:
                continue

            # 날짜 대조
            for d in _dates_in(text):
                ok = any(d in t for t in ev_times) or any(d.lstrip("-") in t or d in t for t in ev_texts)
                if not ok:
                    issues.append({"sid": s["sid"], "type": "DATE_MISMATCH", "detail": f"'{d}' 가 근거 기록 날짜에 없음"})
            # 시각 대조
            for hh, mm in TIME_RE.findall(text):
                hm = f" {int(hh):02d}:{mm}"
                if not any(hm in t for t in ev_times):
                    issues.append({"sid": s["sid"], "type": "DATE_MISMATCH", "detail": f"'{hh}:{mm}' 가 근거 기록 시각에 없음"})
            # 숫자 대조
            for n in _numbers(_strip_dates_times(text)):
                if n not in ev_numbers:
                    issues.append({"sid": s["sid"], "type": "VALUE_MISMATCH",
                                   "detail": f"'{n:g}' 가 근거 기록 값에 없음 (근거 값: {sorted(ev_numbers)[:12]})"})
            if semantic_check:
                issues += semantic_check(s, ev_texts)

            if len(issues) == before:
                n_ok += 1

    # 템플릿 필수 섹션
    filled = {sec["id"] for sec in draft["sections"] if sec["sentences"]}
    for t in template["sections"]:
        if t["required"] and t["id"] not in filled:
            issues.append({"sid": t["id"], "type": "MISSING_SECTION", "detail": f"필수 섹션 '{t['title']}' 비어 있음"})

    # 감염내과 프로파일 필수 항목 커버리지
    coverage = {}
    for item in profile["required_items"]:
        rule = item.get("coverage_rule")
        if not item["mandatory"] or not rule:
            continue
        hits = [h for h in coverage_hits if h["table"] == rule["table"]]
        if "itemids" in rule:
            ids = {h["row"]["itemid"] for h in hits if h["row"].get("itemid") in rule["itemids"]}
            ok = len(ids) >= rule.get("min_distinct", 1)
        elif rule.get("drug_keywords_from_filter"):
            kws = item["filter"]["drug_keywords"]
            ok = any(any(k.lower() in h["row"]["drug"].lower() for k in kws) for h in hits)
        elif "quote_contains" in rule:
            ok = any(h["quote"] and rule["quote_contains"] in h["quote"] for h in hits)
        else:
            ok = bool(hits)
        coverage[item["key"]] = ok
        if not ok:
            issues.append({"sid": "-", "type": "MISSING_REQUIRED",
                           "detail": f"필수 항목 '{item['label']}'({item['key']})이 근거와 함께 들어가지 않음"})

    return {"draft_version": draft["version"], "passed": not issues, "n_sentences": n_sent,
            "n_supported": n_ok, "coverage": coverage, "issues": issues}
