"""입력 스키마: 협진 요청, 의뢰의 결정, 회신."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ConsultRequest(BaseModel):
    """의사가 반드시 줘야 하는 것은 '누가(의뢰의) / 어떤 환자 / 무엇을 묻는지(자유 서술)' 뿐이다.
    나머지는 비워 두면 EMR(입원·진료과)이나 Agent(피의뢰과·진단 요약)가 채운다."""
    requesting_doctor_id: str = Field(examples=["SUR-01"])
    subject_id: int = Field(examples=[90000001])
    request_text: str = Field(min_length=5, description="의뢰 내용. 메모처럼 대강 적어도 된다")
    requesting_dept: str = Field("", description="비우면 의사 디렉터리에서 채움")
    requesting_doctor: str = Field("", description="비우면 의사 디렉터리에서 채움")
    consulted_dept: str = Field("", description="비우면 Agent가 의뢰 내용을 보고 정함")
    consulted_doctor_id: str = Field("", description="비우면 에이전트가 세부전공으로 추천")
    hadm_id: int | None = Field(None, description="비우면 협진 시점에 입원 중인 건")
    urgency: Literal["응급", "긴급", "일반"] = "일반"
    diagnosis: str = Field("", description="현재 진단/수술 (선택. 비우면 EMR 근거로 작성)")
    consult_time: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                              description="협진 기준 시점. MIMIC 은 날짜가 이동되어 있으므로 시나리오 시각을 지정")

    @field_validator("consult_time")
    @classmethod
    def _ts(cls, v):
        datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
        return v


class Decision(BaseModel):
    type: Literal["approve", "edit", "reject", "cancel"]
    message: str = Field("", description="reject: 수정 요청 내용 / cancel: 사유")
    to_doctor_id: str | None = None
    cover_message: str | None = None
    physician_addendum: str | None = None


class Reply(BaseModel):
    replier: str
    impression: str
    recommendations: list[str]
    follow_up: str = ""
    reply_time: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    disclaimer: str = ""
