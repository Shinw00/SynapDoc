"""초안 작성기: draft_consult 툴 안에서 호출되는 두 번째 LLM.

오케스트레이터(가운데 agent)는 '무엇을 할지'만 판단하고, 문서 작성은 근거 풀 전체를 보는 이 작성기가 맡는다.
출력은 구조화(JSON)로 강제하고 모든 문장에 근거 ref 를 달게 한다.
수정 시에는 이전 초안과 검증 이슈를 자동으로 함께 넣는다.
"""
import json
from pathlib import Path

from pydantic import BaseModel, Field

PROMPT = (Path(__file__).parent / "writer_prompt.txt").read_text(encoding="utf-8")


class Evidence(BaseModel):
    ref: str = Field(description="근거 풀 ref 그대로(예: labevents:1110) 또는 request:<필드명> 또는 physician:review_feedback")
    quote: str | None = Field(default=None, description="radiology/discharge 근거일 때 원문 그대로의 인용. 그 외 null")


class Sentence(BaseModel):
    sid: str = Field(description="섹션ID-번호. 예: S5-2")
    text: str
    evidence: list[Evidence]


class Section(BaseModel):
    id: str = Field(description="템플릿 섹션 ID (S1~S8)")
    title: str
    sentences: list[Sentence]


class Draft(BaseModel):
    sections: list[Section]


USER = """[템플릿 섹션]
{sections}

[피의뢰과 작성 지침 — {dept}]
{guidance}

[의뢰의 입력 — 메모처럼 대강 적은 것일 수 있다]
{request}

[오케스트레이터 Agent 의 작성 계획 — EMR 을 조회한 뒤 정리한 것]
{plan}

[근거 풀 — 협진 시점 {consult_time} 이전 기록만 포함]
{evidence}

{revision}"""

REVISION = """[수정 지시]
아래는 이전 초안(v{version})과 그에 대한 문제점이다. 문제가 지적된 문장만 고치고 나머지는 유지하라.
누락 항목은 근거 풀에서 찾아 해당 섹션에 추가하라.

이전 초안:
{previous}

자동 검증에서 나온 문제:
{issues}

추가 피드백:
{feedback}"""


class LLMWriter:
    def __init__(self, model):
        self.model = model

    def write(self, consult, template: dict, feedback: str, plan: str = "") -> dict:
        req, prev = consult.request, consult.draft()
        revision = ""
        if prev:
            rep = consult.verification(prev["version"])
            revision = REVISION.format(version=prev["version"], previous=json.dumps(prev["sections"], ensure_ascii=False),
                                       issues=json.dumps(rep["issues"] if rep else [], ensure_ascii=False),
                                       feedback=feedback or "(없음)")
        elif feedback:
            revision = f"[추가 피드백]\n{feedback}"
        evidence = [{k: v for k, v in e.items() if k != "item_key"} for e in consult.evidence().values()]
        msg = USER.format(
            sections=json.dumps(template["sections"], ensure_ascii=False, indent=1),
            dept=consult.profile["dept_name"], guidance="\n".join(f"- {g}" for g in consult.profile["draft_guidance"]),
            request=json.dumps({k: v for k, v in req.items() if k != "consult_time"}, ensure_ascii=False, indent=1),
            plan=plan or "(없음)",
            consult_time=req["consult_time"], evidence=json.dumps(evidence, ensure_ascii=False, default=str),
            revision=revision)
        messages = [("system", PROMPT), ("user", msg)]
        try:
            out = self.model.with_structured_output(Draft).invoke(messages)
        except Exception:  # noqa: BLE001 — json_schema 방식을 거부하는 모델/게이트웨이 → 툴 호출 방식으로 재시도
            out = self.model.with_structured_output(Draft, method="function_calling").invoke(messages)
        if isinstance(out, dict):
            out = Draft.model_validate(out)
        return out.model_dump()


_writer = None


def get_writer():
    """기본은 llm.make_writer_model() 로 만든 LLM 작성기. 테스트에서는 set_writer 로 교체한다."""
    global _writer
    if _writer is None:
        from llm import make_writer_model
        _writer = LLMWriter(make_writer_model())
    return _writer


def set_writer(writer):
    global _writer
    _writer = writer
