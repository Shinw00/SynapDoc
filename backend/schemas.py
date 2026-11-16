"""LLM 이 답할 때 지켜야 하는 형식."""
from typing import Literal

from pydantic import BaseModel, Field

ToolName = Literal["get_microbiology", "get_prescriptions", "get_administrations", "get_labs",
                   "get_radiology", "get_past_records", "get_admission_info"]


# 1. 요청 해석
class ParsedRequest(BaseModel):
    facts: list[str] = Field(description="의사가 사실로 말한 내용. 한 문장에 하나씩.")
    questions: list[str] = Field(description="의사가 감염내과에 묻는 질문. 한 문장에 하나씩.")


# 2. 체크리스트 구성
class ExtraItem(BaseModel):
    item: str = Field(description="추가로 확인할 항목 이름 (예: 호중구 수)")
    tool: ToolName
    keyword: str = Field(description="조회·판정에 쓸 영문 검색어 (예: Neutrophil). 검사면 검사 이름.")
    reason: str


class PlanAdjust(BaseModel):
    promote: list[str] = Field(default_factory=list, description="이 환자에서 필수로 올릴 선택 항목의 key")
    extras: list[ExtraItem] = Field(default_factory=list, description="항목표에 없지만 이 환자에게 필요한 항목. 없으면 빈 목록.")


# 4. 교차 확인
class FactCheck(BaseModel):
    fact: str
    verdict: Literal["일치", "불일치", "확인 불가"]
    evidence_ids: list[str] = Field(default_factory=list)
    note: str = Field(default="", description="불일치나 확인 불가의 이유를 한 문장으로")


class CrossCheck(BaseModel):
    results: list[FactCheck]


# 5. 초안
class Sentence(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list, description="이 문장을 뒷받침하는 근거 ID")
    source: Literal["emr", "requester"] = Field(
        default="emr", description="emr: 기록에 근거 / requester: 기록에는 없고 의뢰의가 말한 내용")


class Section(BaseModel):
    key: str
    sentences: list[Sentence]


class Question(BaseModel):
    text: str
    origin: Literal["requester", "agent"] = Field(description="requester: 의사가 물은 것 / agent: 에이전트가 제안")
    reason: str = Field(default="", description="agent 제안일 때 그 이유")


class Draft(BaseModel):
    sections: list[Section]
    questions: list[Question]


# 6. 검증 (LLM 판정 부분)
class Judgement(BaseModel):
    sid: str
    supported: bool
    reason: str = ""


class Judgements(BaseModel):
    results: list[Judgement]


# 7. 재생성
class Fix(BaseModel):
    sid: str
    action: Literal["replace", "delete"]
    text: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    source: Literal["emr", "requester"] = "emr"


class Revision(BaseModel):
    fixes: list[Fix]
