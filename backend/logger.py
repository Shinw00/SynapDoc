"""단계별 진행 상황을 터미널에 찍는다. (LangSmith 를 쓰지 않으므로 이 로그로 흐름을 본다)"""
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
_log = logging.getLogger("synapdoc")


def log(step: str, message: str) -> None:
    _log.info("[%s] %s", step, message)
