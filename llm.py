import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


def _env():
    load_dotenv(Path(__file__).with_name(".env"))
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("OPENAI_MODEL"):
        raise ValueError(".env 수정!!! (OPENAI_API_KEY, OPENAI_MODEL)")


def _chat(model_name: str, timeout: int):
    kw = {}
    if os.getenv("OPENAI_TEMPERATURE"):
        kw["temperature"] = float(os.environ["OPENAI_TEMPERATURE"])
    if os.getenv("OPENAI_MAX_TOKENS"):
        kw["max_tokens"] = int(os.environ["OPENAI_MAX_TOKENS"])
    return ChatOpenAI(
        model=model_name,
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.getenv("API_GATEWAY"),
        timeout=timeout,
        max_retries=2,
        **kw,
    )


def make_model():
    """오케스트레이터(가운데 agent) 모델."""
    _env()
    return _chat(os.environ["OPENAI_MODEL"], timeout=60)


def make_writer_model():
    """초안 작성기 모델. WRITER_MODEL 을 비우면 OPENAI_MODEL 과 같다. 출력이 길어 timeout 을 넉넉히 둔다."""
    _env()
    return _chat(os.getenv("WRITER_MODEL") or os.environ["OPENAI_MODEL"], timeout=180)


def make_prompt() -> str:
    return (Path(__file__).parent / "support/prompt.txt").read_text(encoding="utf-8")
