import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("OPENAI_MODEL", "gpt-test")

from support import settings  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def synthetic_db():
    if not (ROOT / "support" / "emr.sqlite").exists():
        import runpy
        runpy.run_path(str(ROOT / "support" / "build_synthetic.py"), run_name="__main__")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CONSULT_DIR", tmp_path / "consults")
    monkeypatch.setattr(settings, "CHECKPOINT_DB", tmp_path / "cp.sqlite")
    monkeypatch.setattr(settings, "MAIL_MODE", "outbox")
    return tmp_path


@pytest.fixture
def request_p1():
    """의사가 대강 적은 시나리오 → 디렉터리·EMR 로 빈 칸(입원, 의뢰과 등)을 채운 요청."""
    from support import data
    return data.normalize_request(json.loads((ROOT / "scenarios" / "patient1_request.json").read_text(encoding="utf-8")))
