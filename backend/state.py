"""그래프의 노드들이 주고받는 데이터의 틀."""
from typing import Any, TypedDict


class ConsultInput(TypedDict, total=False):
    """의사가 화면에서 입력하는 값."""
    subject_id: int
    requesting_dept: str      # 의뢰과 (예: 외과)
    requester: str            # 의뢰의 (예: 박도윤)
    urgency: str              # 일반 | 긴급 | 응급
    request_text: str         # 자유 텍스트 요청
    recipient: str            # 받는 교수 (비워도 됨)
    as_of: str                # 기준 시점 "YYYY-MM-DD HH:MM:SS"


class State(TypedDict, total=False):
    request: ConsultInput
    thread_id: str

    # 1. 요청 해석
    hadm_id: int | None
    is_reconsult: bool
    prior_consults: list[dict]
    parsed: dict                      # {"facts": [...], "questions": [...]}

    # 2~3. 체크리스트와 수집한 근거
    checklist: list[dict]             # {key, item, required, tool, status, evidence_ids, ...}
    evidence: dict[str, dict]         # 근거 ID → {id, table, kind, time, text, dates}
    tool_log: list[dict]

    # 4. 의사 진술과 기록의 교차 확인
    crosscheck: list[dict]            # {fact, verdict, evidence_ids, note}

    # 5~7. 초안, 검증, 재생성
    draft: dict                       # {"sections": [...], "questions": [...]}
    verification: list[dict]          # {sid, verdict, reason}
    retry_count: int

    # 8~9. 승인과 발송
    approval: dict
    document: dict                    # {"text": ..., "html": ...}
    mail: dict
    consult_id: int | None
    status: str                       # awaiting_approval | sent | cancelled
    extra: dict[str, Any]
