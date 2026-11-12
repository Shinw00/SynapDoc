"""테스트·데모 전용 가짜 LLM. Graph·Middleware·Tool·검증·체크포인터는 실제 코드를 그대로 쓰고 LLM 출력만 고정한다."""
import json
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

FIX = Path(__file__).parent / "fixtures"


class ScriptedModel(BaseChatModel):
    script: list
    cursor: list = [0]

    @property
    def _llm_type(self):
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        msg = self.script[self.cursor[0]]
        self.cursor[0] += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])


class ScriptedWriter:
    def __init__(self, names=("patient1_draft_v1.json", "patient1_draft_v2.json", "patient1_draft_v3.json")):
        self.queue = [FIX / n for n in names]

    def write(self, consult, template, feedback, plan=""):
        d = json.loads(self.queue.pop(0).read_text(encoding="utf-8"))
        d.pop("_comment", None)
        return d


def call(name, args=None, cid=None):
    return {"name": name, "args": args or {}, "id": cid or f"call_{name}", "type": "tool_call"}


COVER = "외과 박도윤입니다. S상결장절제술 후 ESBL 대장균 균혈증 환자에 대해 협진을 의뢰드립니다."


PLAN = ("POD4 발열, 혈액배양 ESBL E. coli. 투여 중인 piperacillin-tazobactam 감수성 확인 필요. "
        "CT 문합부 옆 rim-enhancing collection → 배액 필요성. 질문: 항생제 변경, 치료 기간.")


def patient1_script():
    """실제 LLM 이 했을 법한 순서: 목차 확인 → 과 체크리스트 → 메모의 주장을 확인하는 조회 → 작성 → 검증 실패 → 보충 조회."""
    return [
        AIMessage(content="", tool_calls=[call("get_patient_overview", cid="c0")]),
        AIMessage(content="", tool_calls=[call("get_dept_profile", {"dept": "감염내과"}, "c1")]),
        AIMessage(content="", tool_calls=[
            call("search_microbiology", {"days": 14}, "c2a"),
            call("search_medications", {"keywords": ["tazobactam", "cef", "penem"], "include_administration": True}, "c2b"),
            call("search_labs", {"labels": ["White Blood Cells", "C-Reactive Protein", "Lactate"], "days": 7}, "c2c"),
            call("search_labs", {"labels": ["Creatinine"], "days": 7, "include_baseline": True}, "c2d"),
            call("search_imaging", {"keyword": "CT"}, "c2e")]),
        AIMessage(content="", tool_calls=[call("draft_consult", {"plan": PLAN}, "c3")]),
        AIMessage(content="", tool_calls=[call("verify_draft", {}, "c4")]),
        AIMessage(content="", tool_calls=[call("search_prior_notes", {"section": "Allergies:"}, "c5a"),
                                          call("search_prior_notes", {"section": "Past Medical History:"}, "c5b")]),
        AIMessage(content="", tool_calls=[call("draft_consult", {"plan": PLAN + " 알레르기 추가."}, "c6")]),
        AIMessage(content="", tool_calls=[call("verify_draft", {}, "c7")]),
        AIMessage(content="", tool_calls=[call("find_consultant", {}, "c8")]),
        AIMessage(content="", tool_calls=[call("send_email", {"to_doctor_id": "ID-01", "cover_message": COVER}, "c9")]),
        AIMessage(content="", tool_calls=[call("draft_consult", {"plan": PLAN,
                                                                 "feedback": "의뢰 질문에 농양 배액술 필요 여부도 추가해 주세요.",
                                                                 "from_physician": True}, "c10")]),
        AIMessage(content="", tool_calls=[call("verify_draft", {}, "c11")]),
        AIMessage(content="", tool_calls=[call("send_email", {"to_doctor_id": "ID-01", "cover_message": COVER}, "c12")]),
        AIMessage(content="감염내과 이서준 교수님께 협진 의뢰서를 발송했습니다."),
    ]
