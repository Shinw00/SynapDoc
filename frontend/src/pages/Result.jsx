import { useState } from "react";
import { api } from "../api.js";

export default function Result({ consult, onNew, onReconsult }) {
  const { status, mail, document, thread_id } = consult;
  const [reply, setReply] = useState({ replier: "", text: "", replied_at: "" });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  async function saveReply(e) {
    e.preventDefault();
    setError("");
    try {
      await api.reply(thread_id, { ...reply, replied_at: reply.replied_at || null });
      setSaved(true);
    } catch (err) {
      setError(err.message);
    }
  }

  if (status === "cancelled") {
    return (
      <section className="result">
        <h1>의뢰서를 보내지 않았습니다</h1>
        <p className="muted">초안은 저장되지 않았습니다.</p>
        <div className="actions"><button className="btn btn-primary" onClick={onNew}>새 의뢰 작성</button></div>
      </section>
    );
  }

  const dry = mail?.result?.dry_run;
  const failed = status === "mail_failed";

  return (
    <section className="result">
      <h1>{failed ? "메일을 보내지 못했습니다" : dry ? "시험 모드로 저장했습니다" : "의뢰서를 보냈습니다"}</h1>
      {failed && <p className="banner banner-error" role="alert">{mail?.result?.error} 의뢰서는 협진 이력에 저장되어 있습니다.</p>}
      {dry && (
        <p className="banner">
          실제 메일은 나가지 않았습니다. 백엔드의 outbox 폴더에 메일과 첨부가 저장되었습니다. 실제로 보내려면
          백엔드 .env 에서 MAIL_DRY_RUN 을 false 로 바꾸세요.
        </p>
      )}

      <div className="mail">
        <dl>
          <dt>제목</dt><dd>{mail.subject}</dd>
          <dt>받는 사람</dt><dd>{mail.to || "수신 주소가 지정되지 않음"}</dd>
        </dl>
        <pre className="mail-body">{mail.body}</pre>
      </div>

      <article className="sheet sheet-plain">
        <pre>{document.text}</pre>
      </article>

      <form className="reply" onSubmit={saveReply}>
        <h2>감염내과 회신 기록</h2>
        <p className="muted">회신을 기록해 두면 같은 환자를 다시 의뢰할 때 이전 협진으로 요약됩니다.</p>
        {error && <p className="banner banner-error" role="alert">{error}</p>}
        {saved ? (
          <p className="banner">회신을 저장했습니다.</p>
        ) : (
          <>
            <div className="field-row">
              <label className="field">
                <span>회신의</span>
                <input value={reply.replier} onChange={(e) => setReply({ ...reply, replier: e.target.value })} required />
              </label>
              <label className="field">
                <span>회신 시각</span>
                <input type="datetime-local" value={reply.replied_at}
                       onChange={(e) => setReply({ ...reply, replied_at: e.target.value })} />
                <small>비우면 지금 시각으로 저장합니다. 가상 환자는 2181년 시각을 넣어야 합니다.</small>
              </label>
            </div>
            <label className="field">
              <span>회신 내용</span>
              <textarea rows={4} value={reply.text} onChange={(e) => setReply({ ...reply, text: e.target.value })} required />
            </label>
            <div className="actions"><button className="btn">회신 저장</button></div>
          </>
        )}
      </form>

      <div className="actions">
        <button className="btn" onClick={onReconsult}>이 환자 재협진 작성</button>
        <button className="btn btn-primary" onClick={onNew}>새 의뢰 작성</button>
      </div>
    </section>
  );
}
