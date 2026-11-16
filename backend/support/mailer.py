"""메일 발송. MAIL_DRY_RUN=true 면 실제로 보내지 않고 outbox/ 폴더에 저장만 한다."""
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent


def is_dry_run() -> bool:
    return os.getenv("MAIL_DRY_RUN", "true").strip().lower() != "false"


def send(to: str | None, subject: str, body: str, attachment_name: str, attachment_html: str) -> dict:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("MAIL_USER", "synapdoc@localhost")
    msg["To"] = to or "(수신 주소 미지정)"
    msg.set_content(body)
    msg.add_attachment(attachment_html.encode("utf-8"), maintype="text", subtype="html",
                       filename=attachment_name)

    if is_dry_run():
        out = ROOT / "outbox"
        out.mkdir(exist_ok=True)
        stem = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        (out / f"{stem}.eml").write_bytes(msg.as_bytes())
        (out / f"{stem}_{attachment_name}").write_text(attachment_html, encoding="utf-8")
        return {"sent": False, "dry_run": True, "to": to, "saved": str(out / f"{stem}.eml")}

    if not to:
        raise ValueError("수신 주소가 없습니다. config.RECIPIENTS 나 .env 의 MAIL_TO_DEFAULT 를 채워 주세요.")
    with smtplib.SMTP_SSL(os.getenv("MAIL_HOST", "smtp.gmail.com"), int(os.getenv("MAIL_PORT", "465")),
                          timeout=30) as smtp:
        smtp.login(os.environ["MAIL_USER"], os.environ["MAIL_PASSWORD"])
        smtp.send_message(msg)
    return {"sent": True, "dry_run": False, "to": to}
