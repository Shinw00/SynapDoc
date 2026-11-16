"""6. 검증: 초안의 문장을 근거 원문과 대조한다.

코드가 하는 일 (LLM 을 거치지 않음)
  ① 근거 ID 가 실제로 있고, 기준 시점 이전의 기록인가 (원본을 다시 조회해 확인)
  ② 문장의 수치가 인용한 근거에 있는가
  ③ 문장의 날짜가 인용한 근거의 날짜와 맞는가
  ④ '날짜 + 수치' 짝이 한 근거 안에 같이 있는가 (5/15 값을 5/16 값으로 쓰는 실수)
  ⑤ 약물명·균명·검사명이 인용한 근거에 있는가
LLM 이 하는 일
  ⑥ 위를 통과한 문장의 뜻이 근거와 맞는가 (판독문, 퇴원요약지처럼 글로 된 근거)
"""
import re

import config
import llm
import prompts
from logger import log
from nodes.common import all_sentences
from schemas import Judgements
from support import db

STEP = "6 검증"

NUM = r"\d+(?:,\d{3})*(?:\.\d+)?"
RE_DATE_FULL = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
RE_DATE_KR = re.compile(r"(\d{1,2})월\s*(\d{1,2})일")
RE_DATE_MD = re.compile(r"(?<![\d./])(\d{1,2})/(\d{1,2})(?![\d./])")
RE_TIME = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?")
RE_NUM_SENT = re.compile(rf"(?<![A-Za-z\d.]){NUM}")
RE_NUM_ANY = re.compile(NUM)
RE_PAIR_TAIL = re.compile(rf"\s*(?:[A-Za-z가-힣·\-]{{1,12}}\s+)?({NUM})(?![\d/:])")
RE_WORD = re.compile(r"[A-Za-z]{4,}")


def _num(token: str) -> float:
    return float(token.replace(",", ""))


def _valid_md(m: int, d: int) -> bool:
    return 1 <= m <= 12 and 1 <= d <= 31


def sentence_dates(text: str) -> list[tuple[int, int, int]]:
    """문장에 나온 날짜들. (월, 일, 문장 안에서 날짜가 끝나는 위치)"""
    out = []
    for m in RE_DATE_FULL.finditer(text):
        out.append((int(m.group(2)), int(m.group(3)), m.end()))
    for rx in (RE_DATE_KR, RE_DATE_MD):
        for m in rx.finditer(text):
            if _valid_md(int(m.group(1)), int(m.group(2))):
                out.append((int(m.group(1)), int(m.group(2)), m.end()))
    return out


def strip_dates(text: str) -> str:
    """날짜와 시각을 지운 문장 (수치 검사용)."""
    text = RE_DATE_FULL.sub(" ", text)
    text = RE_DATE_KR.sub(" ", text)
    text = RE_DATE_MD.sub(lambda m: " " if _valid_md(int(m.group(1)), int(m.group(2))) else m.group(0), text)
    return RE_TIME.sub(" ", text)


def checked_numbers(text: str) -> list[float]:
    """검사 대상 수치: 소수이거나 10 이상인 수. ('하루 4회', '두 세트' 같은 작은 정수는 건너뛴다)"""
    out = []
    for tok in RE_NUM_SENT.findall(strip_dates(text)):
        if "." in tok or _num(tok) >= 10:
            out.append(_num(tok))
    return out


def evidence_numbers(ev: dict) -> set[float]:
    return {_num(t) for t in RE_NUM_ANY.findall(ev["text"] + " " + " ".join(ev.get("dates", [])))}


def evidence_dates(ev: dict) -> set[tuple[int, int]]:
    found = set()
    for m in RE_DATE_FULL.finditer(" ".join(ev.get("dates", [])) + " " + ev["text"]):
        found.add((int(m.group(2)), int(m.group(3))))
    return found


def _has_term(key: str, text: str) -> bool:
    if key.isascii():
        return re.search(rf"(?<![A-Za-z]){re.escape(key)}(?![A-Za-z])", text) is not None
    return key in text


def check_sentence(sentence: dict, cited: list[dict], request_text: str = "") -> list[str]:
    """코드 검사 ②~⑤. 문제를 글로 돌려준다. 빈 목록이면 통과."""
    text = sentence["text"]
    problems = []

    if sentence.get("source") == "requester":
        # 의뢰의 기재 문장: 수치가 의뢰의의 입력에 실제로 있어야 한다
        allowed = {_num(t) for t in RE_NUM_ANY.findall(request_text)}
        for n in checked_numbers(text):
            if n not in allowed:
                problems.append(f"의뢰의 입력에 없는 수치 {n:g}")
        return problems

    numbers = set().union(*[evidence_numbers(e) for e in cited]) if cited else set()
    dates = set().union(*[evidence_dates(e) for e in cited]) if cited else set()
    body = " ".join(e["text"] for e in cited).lower()

    for n in checked_numbers(text):                                   # ② 수치
        if n not in numbers:
            problems.append(f"수치 불일치: {n:g} 가 인용한 근거에 없음")

    s_dates = sentence_dates(text)
    for m, d, _ in s_dates:                                           # ③ 날짜
        if (m, d) not in dates:
            problems.append(f"날짜 불일치: {m}/{d} 가 인용한 근거의 날짜가 아님")

    for m, d, end in s_dates:                                         # ④ 날짜 + 수치 짝
        tail = RE_PAIR_TAIL.match(text, end)
        if not tail or (m, d) not in dates:
            continue
        tok = tail.group(1)
        if not ("." in tok or _num(tok) >= 10) or _num(tok) not in numbers:
            continue
        if not any((m, d) in evidence_dates(e) and _num(tok) in evidence_numbers(e) for e in cited):
            problems.append(f"날짜-수치 불일치: {m}/{d} 에 {tok} 인 기록이 인용한 근거에 없음")

    for key, aliases in config.TERM_ALIASES.items():                  # ⑤ 이름 (대응표)
        if _has_term(key, text) and not any(a in body for a in aliases):
            problems.append(f"용어 불일치: '{key}' 가 인용한 근거에 없음")
    for word in set(RE_WORD.findall(text)):                           # ⑤ 이름 (영문 낱말)
        w = word.lower()
        if w in config.IGNORE_WORDS or word in config.TERM_ALIASES:
            continue
        if w[:4] not in body:
            problems.append(f"용어 불일치: '{word}' 가 인용한 근거에 없음")
    return problems


def verify(state: dict) -> dict:
    req = state["request"]
    subject_id, as_of = int(req["subject_id"]), req["as_of"]
    stored = state["evidence"]
    results, to_judge = [], []

    for s in all_sentences(state["draft"]):
        if s.get("source") == "requester_edit":
            results.append({"sid": s["sid"], "verdict": "의뢰의 기재", "reason": "의뢰의가 직접 수정"})
            continue
        if s.get("source") == "requester":
            problems = check_sentence(s, [], req.get("request_text", ""))
            results.append({"sid": s["sid"], "verdict": "불일치" if problems else "의뢰의 기재",
                            "reason": "; ".join(problems) or "기록에는 없고 의뢰의가 말한 내용"})
            continue

        # ① 근거가 실제로 있고 기준 시점 이전인가 — 원본을 다시 조회한다
        cited, missing = [], []
        for eid in s.get("evidence_ids", []):
            if eid.split(":")[0] in ("consult", "reply"):
                ev = stored.get(eid)
                ev = ev if ev and ev["time"] <= as_of else None
            else:
                ev = db.refetch(eid, subject_id, as_of)
            (cited if ev else missing).append(ev or eid)
        if not s.get("evidence_ids"):
            results.append({"sid": s["sid"], "verdict": "근거 없음", "reason": "근거 ID 가 지정되지 않음"})
            continue
        if missing:
            results.append({"sid": s["sid"], "verdict": "근거 없음",
                            "reason": f"기준 시점 이전 기록에서 찾을 수 없는 근거: {missing}"})
            continue

        problems = check_sentence(s, cited)
        if problems:
            results.append({"sid": s["sid"], "verdict": "불일치", "reason": "; ".join(problems)})
        else:
            results.append({"sid": s["sid"], "verdict": "일치", "reason": ""})
            to_judge.append((s, cited))

    # ⑥ 뜻이 맞는지는 LLM 이 본다
    if to_judge:
        blocks = []
        for s, cited in to_judge:
            src = "\n".join(f"  [{e['id']}] {e['text']}" for e in cited)
            blocks.append(f"문장 {s['sid']}: {s['text']}\n인용한 근거:\n{src}")
        try:
            res = llm.structured(Judgements, prompts.JUDGE, "\n\n".join(blocks))
            verdicts = {j.sid: j for j in res.results}
            for r in results:
                j = verdicts.get(r["sid"])
                if r["verdict"] == "일치" and j is not None and not j.supported:
                    r["verdict"], r["reason"] = "불일치", f"의미 불일치: {j.reason}"
        except Exception as e:
            log(STEP, f"LLM 판정 실패, 코드 검사 결과만 사용: {e}")

    bad = [r for r in results if r["verdict"] in ("불일치", "근거 없음")]
    log(STEP, f"문장 {len(results)}개 중 문제 {len(bad)}개 (재생성 {state.get('retry_count', 0)}회차)")
    for r in bad:
        log(STEP, f"  {r['sid']} {r['verdict']}: {r['reason']}")
    return {"verification": results}


def has_issues(state: dict) -> bool:
    return any(v["verdict"] in ("불일치", "근거 없음") for v in state.get("verification", []))
