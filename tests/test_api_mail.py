import email
import time
from email import policy

from aiosmtpd.controller import Controller
from fakes import ScriptedModel, ScriptedWriter, patient1_script
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

import api
from graph import build_graph
from llm import make_prompt
from support import data, settings
from support.writer import set_writer


def _client():
    set_writer(ScriptedWriter())
    g = build_graph(ScriptedModel(script=patient1_script(), cursor=[0]), make_prompt(), 4, InMemorySaver())
    return TestClient(api.create_app(g))


def _run_to_sent(c, req):
    cid = c.post("/api/consults", json=req).json()["consult_id"]
    assert c.get(f"/api/consults/{cid}").json()["status"] == "awaiting_approval"
    assert c.post(f"/api/consults/{cid}/decision", json={"type": "reject"}).status_code == 400
    c.post(f"/api/consults/{cid}/decision", json={"type": "reject", "message": "배액술 질문 추가"})
    c.post(f"/api/consults/{cid}/decision", json={"type": "approve"})
    return cid


def test_api_flow(request_p1):
    c = _client()
    assert "감염내과" in c.get("/api/meta").json()["departments"]
    assert c.post("/api/consults", json={**request_p1, "hadm_id": 1}).status_code == 400
    cid = _run_to_sent(c, request_p1)
    assert c.get(f"/api/consults/{cid}").json()["status"] == "sent"
    r = c.post(f"/api/consults/{cid}/reply", json={"replier": "이서준", "impression": "x", "recommendations": ["메로페넴"]})
    assert r.json()["status"] == "replied" and "메로페넴" in c.get(f"/api/consults/{cid}/document").text


class _Inbox:
    def __init__(self):
        self.msgs = []

    async def handle_DATA(self, server, session, envelope):
        self.msgs.append((envelope.rcpt_tos, envelope.content))
        return "250 OK"


def test_smtp_sends_with_redirect(request_p1, monkeypatch):
    inbox = _Inbox()
    ctl = Controller(inbox, hostname="127.0.0.1", port=8025, auth_require_tls=False)
    ctl.start()
    try:
        import smtplib
        monkeypatch.setattr(smtplib.SMTP, "starttls", lambda self, *a, **k: None)     # 로컬 테스트 서버는 TLS 없음
        monkeypatch.setattr(smtplib.SMTP, "login", lambda self, *a, **k: None)
        for k, v in {"MAIL_MODE": "smtp", "SMTP_HOST": "127.0.0.1", "SMTP_PORT": 8025, "SMTP_USER": "team@example.com",
                     "SMTP_PASSWORD": "pw", "MAIL_FROM": "team@example.com", "MAIL_REDIRECT_TO": "demo@example.com"}.items():
            monkeypatch.setattr(settings, k, v)
        cid = _run_to_sent(_client(), request_p1)
        time.sleep(0.3)
        assert len(inbox.msgs) == 1
        rcpt, raw = inbox.msgs[0]
        m = email.message_from_bytes(raw, policy=policy.default)
        assert rcpt == ["demo@example.com"] and "seojun.lee@synapdoc-hospital.test" in m["Subject"]
        assert m["Reply-To"] == "doyoon.park@synapdoc-hospital.test"
        assert data.Consult(cid).sent()["delivered"].startswith("smtp:")
    finally:
        ctl.stop()


def test_smtp_refuses_fake_domain_without_redirect(request_p1, monkeypatch):
    for k, v in {"MAIL_MODE": "smtp", "SMTP_HOST": "127.0.0.1", "SMTP_PORT": 8026, "SMTP_USER": "u",
                 "SMTP_PASSWORD": "p", "MAIL_REDIRECT_TO": None}.items():
        monkeypatch.setattr(settings, k, v)
    c = _client()
    cid = c.post("/api/consults", json=request_p1).json()["consult_id"]
    c.post(f"/api/consults/{cid}/decision", json={"type": "reject", "message": "배액술 질문 추가"})
    c.post(f"/api/consults/{cid}/decision", json={"type": "approve"})
    tr = c.get(f"/api/consults/{cid}").json()["trace"]
    assert "발송 실패" in tr[-1]["result"] and not data.Consult(cid).sent()
