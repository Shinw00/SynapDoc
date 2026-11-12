"""API 키 없이 웹 UI 를 시연하는 서버 (LLM 출력만 고정, 나머지는 실제 코드).
UI 에서 '환자 1 시나리오 채우기' → 시작 → 1차 승인 화면 '수정 요청' → 2차 '승인·발송' 순서로 진행.

  python tests/demo_server_fake_llm.py      → http://localhost:8000
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.setdefault("OPENAI_API_KEY", "demo")
os.environ.setdefault("OPENAI_MODEL", "demo")

import uvicorn  # noqa: E402
from fakes import ScriptedModel, ScriptedWriter, patient1_script  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

import api  # noqa: E402
from graph import build_graph  # noqa: E402
from llm import make_prompt  # noqa: E402
from support.writer import set_writer  # noqa: E402

if __name__ == "__main__":
    set_writer(ScriptedWriter())
    g = build_graph(ScriptedModel(script=patient1_script(), cursor=[0]), make_prompt(), 4, InMemorySaver())
    uvicorn.run(api.create_app(g), host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
