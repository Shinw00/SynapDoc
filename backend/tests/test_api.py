"""API 를 가짜 LLM 으로 확인한다.   python -m tests.test_api"""
import os
import tempfile

tmp = tempfile.mkdtemp()
os.environ["CONSULT_DB_PATH"] = os.path.join(tmp, "consults.sqlite")
os.environ["CHECKPOINT_DB_PATH"] = os.path.join(tmp, "checkpoints.sqlite")
os.environ["MAIL_DRY_RUN"] = "true"

import json
from pathlib import Path

import llm
from tests.fake_llm import FakeLLM

fake = FakeLLM()
llm.get_llm, llm.structured = fake.get_llm, fake.structured

from fastapi.testclient import TestClient

import api

client = TestClient(api.app)
request = json.loads((Path(__file__).parent.parent / "support/test/scenarios.json").read_text(encoding="utf-8"))["1"]


def main():
    assert client.get("/patients").json()[0]["subject_id"] == 90000001

    r = client.post("/consults", json=request)
    assert r.status_code == 200, r.text
    body = r.json()
    tid = body["thread_id"]
    assert body["status"] == "awaiting_approval" and body["review"]["sections"]

    assert client.get(f"/consults/{tid}").json()["status"] == "awaiting_approval"

    r = client.post(f"/consults/{tid}/approve", json={"approved": True, "rejected_questions": [2],
                                                      "memo": "보호자 설명 요청", "recipient": "이서준"})
    done = r.json()
    assert done["status"] == "sent", done
    assert "이서준 교수님" in done["mail"]["body"] and "용량 조절" not in done["document"]["text"]

    assert client.post(f"/consults/{tid}/approve", json={"approved": True}).status_code == 409   # 두 번 발송 방지
    assert client.post(f"/consults/{tid}/reply", json={"replier": "이서준", "text": "메로페넴으로 변경",
                                                       "replied_at": "2181-05-16 13:40:00"}).status_code == 200
    hist = client.get("/patients/90000001/consults").json()
    assert len(hist) == 1 and hist[0]["replies"][0]["replier"] == "이서준"
    assert client.post("/consults", json={**request, "as_of": "2170-01-01 00:00:00"}).status_code == 400  # 입원 기록 없음
    assert client.get("/consults/없는아이디").status_code == 404
    print("[통과] API: 생성 → 조회 → 승인 → 중복 승인 차단 → 회신 → 이력")
    print("\n" + done["mail"]["subject"] + "\n" + done["mail"]["body"] + "\n\n" + done["document"]["text"])


if __name__ == "__main__":
    main()
