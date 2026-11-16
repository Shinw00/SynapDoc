"""에이전트가 3단계(수집)에서 고르는 EMR 조회 도구.

쿼리는 support/db.py 에 있고, 여기서는 그 함수를 도구로 감싸기만 한다.
환자 ID 와 기준 시점은 도구를 만들 때 고정되므로 LLM 이 바꿀 수 없다.
"""
from dataclasses import dataclass, field
from typing import Literal

from langchain_core.tools import tool

from support import db


@dataclass
class Scope:
    """이번 의뢰에서 조회가 허용된 범위."""
    subject_id: int
    as_of: str


@dataclass
class EvidenceStore:
    """수집 중 모인 근거와 호출 기록."""
    evidence: dict[str, dict] = field(default_factory=dict)
    calls: list[dict] = field(default_factory=list)

    def add(self, tool_name: str, args: dict, rows: list[dict]) -> str:
        for ev in rows:
            self.evidence[ev["id"]] = ev
        self.calls.append({"tool": tool_name, "args": args, "ids": [ev["id"] for ev in rows]})
        if not rows:
            return "기록 없음 (기준 시점 이전에 해당하는 기록이 없습니다)."
        return "\n".join(f"[{ev['id']}] {ev['text']}" for ev in rows)


def run_tool(name: str, args: dict, scope: Scope, store: EvidenceStore) -> str:
    """도구 이름으로 조회를 실행한다. 에이전트의 호출과 코드의 보충 조회가 같은 길을 쓴다."""
    s, t = scope.subject_id, scope.as_of
    if name == "get_microbiology":
        rows = db.microbiology(s, t, args.get("days", 14))
    elif name == "get_prescriptions":
        rows = db.prescriptions(s, t, args.get("days", 14))
    elif name == "get_administrations":
        rows = db.administrations(s, t, args.get("days", 14), args.get("medication"))
    elif name == "get_labs":
        rows = db.labs(s, t, args.get("names") or [], args.get("days", 7), args.get("scope", "current"))
    elif name == "get_radiology":
        rows = db.radiology(s, t, args.get("days", 14))
    elif name == "get_past_records":
        rows = db.past_records(s, t)
    elif name == "get_admission_info":
        rows = db.admission_info(s, t)
    else:
        raise ValueError(f"알 수 없는 도구: {name}")
    return store.add(name, args, rows)


def make_tools(scope: Scope, store: EvidenceStore) -> list:
    @tool
    def get_microbiology(days: int = 14) -> str:
        """배양 결과와 항생제 감수성을 조회한다. 기준 시점까지 보고된 결과만 나온다 (중간 보고, 최종 보고, 무성장 포함)."""
        return run_tool("get_microbiology", {"days": days}, scope, store)

    @tool
    def get_prescriptions(days: int = 14) -> str:
        """현재 입원의 처방 내역(약물, 용량, 경로, 횟수, 시작·종료)을 조회한다."""
        return run_tool("get_prescriptions", {"days": days}, scope, store)

    @tool
    def get_administrations(days: int = 14, medication: str | None = None) -> str:
        """실제 투여 기록을 조회한다. 처방대로 투여됐는지, 마지막 투여가 언제인지 확인할 때 쓴다. medication 은 약물 영문명의 일부."""
        return run_tool("get_administrations", {"days": days, "medication": medication}, scope, store)

    @tool
    def get_labs(names: list[str], days: int = 7,
                 admission_scope: Literal["current", "past", "all"] = "current") -> str:
        """검사 수치를 조회한다. names 는 검사 영문 이름의 일부 (예: ["Creatinine"], ["White Blood Cells", "C-Reactive Protein", "Lactate"]).
        admission_scope: current=현재 입원(최근 days 일), past=과거 입원 전체(기저치 확인용), all=전부."""
        return run_tool("get_labs", {"names": names, "days": days, "scope": admission_scope}, scope, store)

    @tool
    def list_lab_items() -> str:
        """조회할 수 있는 검사 이름 목록을 본다. 검사 이름을 모를 때 먼저 쓴다."""
        return ", ".join(db.lab_items())

    @tool
    def get_radiology(days: int = 14) -> str:
        """영상 판독문 원문을 조회한다."""
        return run_tool("get_radiology", {"days": days}, scope, store)

    @tool
    def get_past_records() -> str:
        """과거 입원의 퇴원요약지와 진단을 조회한다. 약물 알레르기, 기저질환, 과거력의 출처다."""
        return run_tool("get_past_records", {}, scope, store)

    @tool
    def get_admission_info() -> str:
        """현재 입원 정보(입원일, 진료과, 나이, 성별)를 조회한다."""
        return run_tool("get_admission_info", {}, scope, store)

    return [get_microbiology, get_prescriptions, get_administrations, get_labs, list_lab_items,
            get_radiology, get_past_records, get_admission_info]
