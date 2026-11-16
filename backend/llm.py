"""LLM 연결. 학교 HAI 게이트웨이는 OpenAI 호환이라 ChatOpenAI 에 주소와 키만 바꿔 넣는다."""
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

load_dotenv()


def get_llm() -> ChatOpenAI:
    kwargs = dict(
        model=os.environ["HAI_MODEL"],
        api_key=os.environ["HAI_API_KEY"],
        base_url=os.getenv("HAI_BASE_URL", "https://factchat-cloud.mindlogic.ai/v1/gateway"),
        timeout=120,
        max_retries=2,
    )
    if os.getenv("HAI_TEMPERATURE"):
        kwargs["temperature"] = float(os.environ["HAI_TEMPERATURE"])
    return ChatOpenAI(**kwargs)


def structured(schema, system: str, user: str):
    """정해진 형식(schema)으로 답을 받는다. 게이트웨이 호환성을 위해 도구 호출 방식을 쓴다."""
    model = get_llm().with_structured_output(schema, method="function_calling")
    return model.invoke([SystemMessage(system), HumanMessage(user)])
