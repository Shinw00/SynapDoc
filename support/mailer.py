"""피의뢰 교수에게 보내는 메일.

MAIL_MODE=outbox (기본)  실제 발송 없이 의뢰 폴더에 .eml 저장
MAIL_MODE=smtp           SMTP 로 실제 발송 (+ .eml 사본 저장)
  - MAIL_REDIRECT_TO 를 설정하면 디렉터리상의 수신자 대신 그 주소로만 보낸다(시연용 안전장치).
    제목 앞에 원래 수신자를 붙여 누구에게 갈 메일이었는지 보이게 한다.
  - .test 도메인(가상 의사 주소)으로는 리다이렉트 없이 보내지 않는다.
  - Gmail/네이버 SMTP 는 From 이 로그인 계정과 같아야 하므로, From 은 MAIL_FROM(=SMTP_USER),
    의뢰의 이름은 표시 이름으로, 의뢰의 주소는 Reply-To 로 넣는다.
"""
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from support import settings


def build_message(consult_id, request, sender, to, cover_message, html, summary_lines) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = (f"[협진의뢰][{request['urgency']}] {request['requesting_dept']} → {request['consulted_dept']} | "
                      f"환자 {request['subject_id']} | {consult_id}")
    msg["From"] = formataddr((f"{sender['name']} ({request['requesting_dept']}) via SynapDoc",
                              settings.MAIL_FROM or sender["email"]))
    msg["Reply-To"] = sender["email"]
    msg["To"] = formataddr((f"{to['name']} {to['title']}", to["email"]))
    body = (f"{to['name']} {to['title']}님,\n\n{cover_message}\n\n[요약]\n" + "\n".join(f"- {l}" for l in summary_lines) +
            "\n\n협진 의뢰서 전문은 첨부 파일을 확인해 주십시오.\n회신은 SynapDoc 협진 회신 화면 또는 이 메일 답장으로 부탁드립니다.\n\n"
            f"{request['requesting_dept']} {sender['name']} 드림\n(SynapDoc으로 초안 작성, 의뢰의 검토·승인 후 발송)")
    msg.set_content(body)
    msg.add_alternative(html, subtype="html")
    msg.add_attachment(html.encode("utf-8"), maintype="text", subtype="html", filename=f"{consult_id}.html")
    return msg


def deliver(msg: EmailMessage, consult_dir) -> str:
    """발송하고 '어디로 갔는지' 문자열을 돌려준다."""
    if settings.MAIL_MODE == "smtp":
        if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
            raise RuntimeError("SMTP_HOST / SMTP_USER / SMTP_PASSWORD 를 .env 에 설정하세요.")
        original_to = msg["To"]
        if settings.MAIL_REDIRECT_TO:
            del msg["To"]
            msg["To"] = settings.MAIL_REDIRECT_TO
            subj = msg["Subject"]
            del msg["Subject"]
            msg["Subject"] = f"[원 수신: {original_to}] {subj}"
        elif msg["To"].addresses[0].domain.endswith(".test"):
            raise RuntimeError("가상 주소(.test)로는 보낼 수 없습니다. MAIL_REDIRECT_TO 를 설정하거나 doctors.json 의 이메일을 실제 테스트 주소로 바꾸세요.")
    (consult_dir / "sent.eml").write_bytes(bytes(msg))
    if settings.MAIL_MODE != "smtp":
        return f"outbox:{consult_dir.name}/sent.eml"
    if settings.SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, 465, timeout=30)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
        server.starttls()
    with server:
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
    return f"smtp:{msg['To']}"
