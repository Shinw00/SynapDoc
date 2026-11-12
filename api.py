"""FastAPI 서버 — 웹페이지가 붙는 지점. Studio 와 같은 단일 협진 그래프를 쓰고,
SQLite 체크포인터를 붙여 서버를 재시작해도 승인 대기 중인 의뢰를 이어서 처리한다.

  uvicorn api:app --reload      → http://localhost:8000   (API 문서: /docs)
"""
import sqlite3
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from langgraph.checkpoint.sqlite import SqliteSaver

from support import data, runner, settings
from support.schemas import ConsultRequest, Decision, Reply

STATIC = Path(__file__).parent / "static"


def make_checkpointer():
    settings.CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    saver = SqliteSaver(sqlite3.connect(str(settings.CHECKPOINT_DB), check_same_thread=False))
    saver.setup()
    return saver


def create_app(graph=None) -> FastAPI:
    app = FastAPI(title="SynapDoc 협진 의뢰서 Agent API", version="1.0.0")
    holder = {"graph": graph}

    def g():
        if holder["graph"] is None:
            from graph import build_graph
            from llm import make_model, make_prompt
            holder["graph"] = build_graph(make_model(), make_prompt(), checkpointer=make_checkpointer())
        return holder["graph"]

    def _view(cid):
        try:
            return runner.view(cid)
        except FileNotFoundError:
            raise HTTPException(404, "의뢰를 찾을 수 없습니다.")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/meta")
    def meta():
        return {"departments": data.departments(), "doctors": data.doctors(),
                "template_sections": [{"id": s["id"], "title": s["title"]} for s in data.template()["sections"]]}

    @app.get("/api/patients/{subject_id}/admissions")
    def admissions(subject_id: int):
        return data.emr_db().admissions(subject_id)

    @app.get("/api/patients")
    def patients(q: str = ""):
        return data.emr_db().search_patients(q)

    @app.post("/api/consults", status_code=202)
    def create_consult(req: ConsultRequest, bg: BackgroundTasks):
        try:
            cid = data.create_consult(req.model_dump())
        except ValueError as e:
            raise HTTPException(400, str(e))
        bg.add_task(runner.start, g(), cid)
        return {"consult_id": cid, "status": "running"}

    @app.get("/api/consults")
    def list_consults():
        return data.list_consults()

    @app.get("/api/consults/{cid}")
    def get_consult(cid: str):
        return _view(cid)

    @app.get("/api/consults/{cid}/preview", response_class=HTMLResponse)
    def preview(cid: str, version: int | None = None):
        _view(cid)
        return data.document_html(data.Consult(cid), version)

    @app.get("/api/consults/{cid}/document", response_class=HTMLResponse)
    def document(cid: str):
        _view(cid)
        return data.document_html(data.Consult(cid), with_reply=True)

    @app.post("/api/consults/{cid}/decision", status_code=202)
    def decision(cid: str, d: Decision, bg: BackgroundTasks):
        _view(cid)
        try:
            hitl, cancelled = runner.submit_decision(cid, d)
        except ValueError as e:
            raise HTTPException(409 if "상태" in str(e) else 400, str(e))
        bg.add_task(runner.resume, g(), cid, hitl, cancelled)
        return {"consult_id": cid, "accepted": d.type, "status": "running"}

    @app.post("/api/consults/{cid}/reply")
    def reply(cid: str, r: Reply):
        v = _view(cid)
        if v["status"] not in ("sent", "replied"):
            raise HTTPException(409, "발송된 의뢰에만 회신할 수 있습니다.")
        c = data.Consult(cid)
        c.set_reply(r.model_dump())
        c.set_status("replied")
        (c.dir / "final_with_reply.html").write_text(data.document_html(c, with_reply=True), encoding="utf-8")
        return _view(cid)

    return app


app = create_app()
