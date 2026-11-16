"""API 키 없이 흐름을 확인하기 위한 가짜 LLM.

실제 모델 대신 미리 정해 둔 답을 돌려준다. 그래프의 연결, 시점 필터, 보충 조회, 검증,
재생성, 승인, 발송이 제대로 이어지는지 보는 용도이며 글의 품질을 보는 용도가 아니다.
초안에는 일부러 틀린 문장을 넣어 검증과 재생성이 동작하는지 확인한다.
"""
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

import schemas as S


class FakeToolModel(BaseChatModel):
    """3단계 에이전트 역할. 두 번 도구를 부르고 끝낸다. 일부 항목은 일부러 조회하지 않는다."""
    step: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.step += 1
        if self.step == 1:
            calls = [
                {"name": "get_microbiology", "args": {"days": 14, "subject_id": 12345}, "id": "c1"},  # 금지 인자
                {"name": "get_prescriptions", "args": {"days": 14}, "id": "c2"},
                {"name": "get_labs", "args": {"names": ["White Blood Cells", "C-Reactive Protein", "Lactate",
                                                        "Creatinine"], "days": 7}, "id": "c3"},
            ]
            msg = AIMessage(content="", tool_calls=calls)
        elif self.step == 2:
            calls = [  # 기저치가 없어서 과거 입원을 다시 조회
                {"name": "get_labs", "args": {"names": ["Creatinine"], "admission_scope": "past"}, "id": "c4"},
                {"name": "get_past_records", "args": {}, "id": "c5"},
            ]
            msg = AIMessage(content="", tool_calls=calls)
        else:
            msg = AIMessage(content="수집 완료")
        return ChatResult(generations=[ChatGeneration(message=msg)])


class FakeLLM:
    def __init__(self):
        self.calls = []

    def get_llm(self):
        return FakeToolModel()

    def structured(self, schema, system, user):
        self.calls.append(schema.__name__)
        return getattr(self, f"_{schema.__name__}")(user)

    def _ParsedRequest(self, user):
        return S.ParsedRequest(
            facts=["수술 후 4일째부터 발열이 있다", "혈액배양에서 ESBL 대장균이 나왔다",
                   "현재 피페라실린-타조박탐을 투여 중이다", "CT에서 문합부 옆 액체 저류가 있다"],
            questions=["항생제 변경 여부", "치료 기간"])

    def _PlanAdjust(self, user):
        return S.PlanAdjust(promote=["imaging"], extras=[])

    def _CrossCheck(self, user):
        return S.CrossCheck(results=[
            S.FactCheck(fact="수술 후 4일째부터 발열이 있다", verdict="확인 불가", note="체온 기록이 없음"),
            S.FactCheck(fact="혈액배양에서 ESBL 대장균이 나왔다", verdict="일치", evidence_ids=["micro:8002"]),
            S.FactCheck(fact="현재 피페라실린-타조박탐을 투여 중이다", verdict="일치",
                        evidence_ids=["rx:5005", "emar:90000001-E010", "없는:ID"]),
            S.FactCheck(fact="CT에서 문합부 옆 액체 저류가 있다", verdict="일치", evidence_ids=["rad:90000001-RR-12"]),
        ])

    def _Draft(self, user):
        sen = S.Sentence
        return S.Draft(sections=[
            S.Section(key="reason", sentences=[
                sen(text="수술 후 발열과 함께 혈액배양에서 ESBL 생성 대장균이 확인되어, 항생제 변경 여부와 치료 기간에 대한 감염내과 의견을 요청드립니다.",
                    evidence_ids=["micro:8002"])]),
            S.Section(key="course", sentences=[
                sen(text="수술 후 4일째부터 발열이 있었습니다.", source="requester"),
                sen(text="5/14 피페라실린-타조박탐 4.5 g 정맥주사를 하루 4회로 시작하여 현재까지 투여 중이며, 마지막 투여는 5/16 10:00입니다.",
                    evidence_ids=["rx:5005", "emar:90000001-E010"])]),
            S.Section(key="micro", sentences=[
                sen(text="5/14 채취한 혈액배양 한 세트에서 5/16 ESCHERICHIA COLI(ESBL 생성균)가 최종 동정되었습니다.",
                    evidence_ids=["micro:8002"]),
                sen(text="PIPERACILLIN/TAZO(MIC ≥128)에 내성(R)이며, MEROPENEM(MIC ≤0.25), ERTAPENEM에는 감수성(S)입니다.",
                    evidence_ids=["micro:8008", "micro:8009", "micro:8010"]),
                sen(text="혈액배양에서 반코마이신 내성 장알균도 함께 동정되었습니다.", evidence_ids=["micro:8002"])]),   # 지어낸 문장
            S.Section(key="labs", sentences=[
                sen(text="CRP는 5/14 182 → 5/16 215 mg/L로 상승하였습니다.", evidence_ids=["lab:1106", "lab:1110"]),  # 날짜 오류
                sen(text="Creatinine은 이전 입원 시 기저치 0.8 mg/dL에서 5/14 1.3 → 5/15 1.6 → 5/16 1.5 mg/dL로 상승한 상태입니다.",
                    evidence_ids=["lab:1001", "lab:1107", "lab:1111", "lab:1113"])]),
            S.Section(key="imaging", sentences=[
                sen(text="5/14 복부·골반 CT에서 문합부 인접 3.2 x 2.8 cm 크기의 액체 저류가 확인되어 농양이 의심됩니다.",
                    evidence_ids=["rad:90000001-RR-12"])]),
            S.Section(key="meds", sentences=[
                sen(text="약물 알레르기: Sulfa (Sulfonamide Antibiotics).", evidence_ids=["ds:90000001-DS-3"]),
                sen(text="5/17 메로페넴으로 변경되었습니다.", evidence_ids=["rx:9999"])]),                       # 없는 근거
        ], questions=[
            S.Question(text="피페라실린-타조박탐에 내성인 ESBL 대장균 균혈증에 대해 항생제 변경이 필요한지 의견 부탁드립니다.", origin="requester"),
            S.Question(text="권장 치료 기간에 대해 의견 부탁드립니다.", origin="requester"),
            S.Question(text="현재 신기능을 고려한 항생제 용량 조절에 대해 의견 부탁드립니다.", origin="agent",
                       reason="크레아티닌이 기저치 0.8 에서 1.5 로 상승"),
        ])

    def _Judgements(self, user):
        # 코드 검사를 통과한 문장은 뜻도 맞다고 답한다
        import re
        return S.Judgements(results=[S.Judgement(sid=sid, supported=True) for sid in re.findall(r"문장 (s\d+):", user)])

    def _Revision(self, user):
        import re
        fixes = []
        for sid, text in re.findall(r"- (s\d+) \| 문장: (.*?) \| 인용", user):
            if "CRP" in text:
                fixes.append(S.Fix(sid=sid, action="replace", text="CRP는 5/14 182 → 5/15 215 mg/L로 상승하였습니다.",
                                   evidence_ids=["lab:1106", "lab:1110"]))
            else:
                fixes.append(S.Fix(sid=sid, action="delete"))
        return S.Revision(fixes=fixes)
