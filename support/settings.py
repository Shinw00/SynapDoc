"""환경설정. 프로젝트 루트의 .env 를 읽는다 (.env.example 참고)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
SUPPORT = ROOT / "support"
load_dotenv(ROOT / ".env")


def env(key, default=None):
    v = os.getenv(key)
    return v if v not in (None, "") else default


def path_env(key, default: Path) -> Path:
    p = Path(env(key, str(default)))
    return p if p.is_absolute() else ROOT / p


# EMR: 가상 데이터 sqlite (기본) 또는 MIMIC-IV PostgreSQL
EMR_URL = env("EMR_URL", f"sqlite:///{SUPPORT / 'emr.sqlite'}")
if EMR_URL.startswith("sqlite:///") and not EMR_URL.startswith("sqlite:////"):
    _rel = EMR_URL[len("sqlite:///"):]
    if not Path(_rel).is_absolute():
        EMR_URL = f"sqlite:///{ROOT / _rel}"
EMR_TABLE_STYLE = env("EMR_TABLE_STYLE", "flat")          # flat | mimiciv
EMR_XLSX = path_env("EMR_XLSX", ROOT / "SynapDoc 가상 EMR 데이터 (환자 1).xlsx")

CONSULT_DIR = path_env("CONSULT_DIR", SUPPORT / "consults")  # 의뢰별 폴더
CHECKPOINT_DB = path_env("CHECKPOINT_DB", SUPPORT / "checkpoints.sqlite")  # FastAPI 경로의 승인 대기 상태

MAX_MODEL_CALLS = int(env("MAX_MODEL_CALLS", "30"))
MAX_DRAFTS = int(env("MAX_DRAFTS", "4"))

# 메일: outbox(파일만 저장, 기본) | smtp(실제 발송)
MAIL_MODE = env("MAIL_MODE", "outbox")
SMTP_HOST = env("SMTP_HOST")
SMTP_PORT = int(env("SMTP_PORT", "587"))
SMTP_USER = env("SMTP_USER")
SMTP_PASSWORD = env("SMTP_PASSWORD")
MAIL_FROM = env("MAIL_FROM") or SMTP_USER
MAIL_REDIRECT_TO = env("MAIL_REDIRECT_TO")   # 설정하면 모든 메일을 이 주소로만 보낸다 (시연용 안전장치)
