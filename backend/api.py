"""React 화면이 호출하는 API.

    uvicorn api:app --reload --port 8000        (문서: http://localhost:8000/docs)

흐름
  POST /consults                  의뢰 입력 → 1~7단계 실행 → 승인 대기 상태의 초안 반환
  GET  /consults/{thread_id}      현재 상태 (승인 대기 중이면 초안, 끝났으면 결과)
  POST /consults/{thread_id}/approve   승인·수정 내용을 받아 8~9단계 실행
  POST /consults/{thread_id}/reply     감염내과 회신 저장
  GET  /patients                  환자 목록
  GET  /patients/{subject_id}/consults  환자의 협진 이력
"""
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from graph import build_graph
from nodes.common import build_review
from support import consults, db

load_dotenv()
ROOT = Path(__file__).resolve().parent

app = FastAPI(title="SynapDoc 협진 의뢰서 에이전트")
app.add_middleware(CORSMiddleware,
                   allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
                   allow_methods=["*"], allow_headers=["*"])

# 승인 대기 중인 건이 서버를 껐다 켜도 남도록 파일에 저장한다
_cp = Path(os.getenv("CHECKPOINT_DB_PATH", "support/checkpoints.sqlite"))
_cp = _cp if _cp.is_absolute() else ROOT / _cp
graph = build_graph(SqliteSaver(sqlite3.connect(_cp, check_same_thread=False)))


class ConsultRequest(BaseModel):
    subject_id: int
    requesting_dept: str = Field(examples=["외과"])
    requester: str = Field(examples=["박도윤"])
    request_text: str
    urgency: str = "일반"
    recipient: str = ""
    as_of: str | None = Field(default=None, description="기준 시점. 비우면 현재 시각. 가상 데이터는 2181년이므로 꼭 넣는다.")


class Approval(BaseModel):
    approved: bool
    edits: dict[str, str] = Field(default_factory=dict, description="{문장 ID: 고친 문장}")
    deleted: list[str] = Field(default_factory=list, description="지울 문장 ID")
    rejected_questions: list[int] = Field(default_factory=list, description="뺄 질문의 순번 (0부터)")
    added_questions: list[str] = Field(default_factory=list)
    memo: str = ""
    recipient: str = ""


class Reply(BaseModel):
    replier: str
    text: str
    replied_at: str | None = None


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _view(thread_id: str) -> dict:
    snap = graph.get_state(_cfg(thread_id))
    if not snap.values:
        raise HTTPException(404, "해당 의뢰를 찾을 수 없습니다.")
    v = snap.values
    if snap.next:                                   # 8단계에서 멈춰 있음
        return {"thread_id": thread_id, "status": "awaiting_approval", "review": build_review(v)}
    return {"thread_id": thread_id, "status": v.get("status"), "consult_id": v.get("consult_id"),
            "mail": v.get("mail"), "document": v.get("document"), "review": build_review(v)}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/patients")
def patients():
    return db.list_patients()


@app.get("/patients/{subject_id}/consults")
def patient_consults(subject_id: int):
    return consults.list_for_patient(subject_id)


@app.post("/consults")
def create_consult(body: ConsultRequest):
    thread_id = str(uuid.uuid4())
    request = body.model_dump()
    try:
        request["as_of"] = db.normalize_time(request["as_of"] or datetime.now().strftime(db.FMT))
        graph.invoke({"request": request, "thread_id": thread_id}, _cfg(thread_id))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _view(thread_id)


@app.get("/consults/{thread_id}")
def get_consult(thread_id: str):
    return _view(thread_id)


@app.post("/consults/{thread_id}/approve")
def approve_consult(thread_id: str, body: Approval):
    snap = graph.get_state(_cfg(thread_id))
    if not snap.values:
        raise HTTPException(404, "해당 의뢰를 찾을 수 없습니다.")
    if not snap.next:
        raise HTTPException(409, "이미 처리된 의뢰입니다.")     # 같은 의뢰를 두 번 보내지 않는다
    graph.invoke(Command(resume=body.model_dump()), _cfg(thread_id))
    return _view(thread_id)


@app.post("/consults/{thread_id}/reply")
def reply_consult(thread_id: str, body: Reply):
    c = consults.get_by_thread(thread_id)
    if not c:
        raise HTTPException(404, "발송된 의뢰서가 없습니다.")
    replied_at = db.normalize_time(body.replied_at or datetime.now().strftime(db.FMT))
    reply_id = consults.add_reply(c["consult_id"], body.replier, body.text, replied_at)
    return {"reply_id": reply_id, "consult_id": c["consult_id"]}
