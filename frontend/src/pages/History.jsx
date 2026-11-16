import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function History({ patients }) {
  const [subjectId, setSubjectId] = useState("");
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!subjectId && patients.length) setSubjectId(String(patients[0].subject_id));
  }, [patients, subjectId]);

  useEffect(() => {
    if (!subjectId) return;
    setItems(null);
    setError("");
    api.history(subjectId).then(setItems).catch((e) => setError(e.message));
  }, [subjectId]);

  return (
    <section className="history">
      <div className="compose-head">
        <h1>협진 이력</h1>
        <label className="field field-inline">
          <span>환자</span>
          <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
            {patients.map((p) => <option key={p.subject_id} value={p.subject_id}>{p.subject_id}</option>)}
          </select>
        </label>
      </div>

      {error && <p className="banner banner-error" role="alert">{error}</p>}
      {items && items.length === 0 && <p className="muted">이 환자로 보낸 의뢰서가 아직 없습니다.</p>}

      <ol className="timeline">
        {(items || []).map((c) => (
          <li key={c.consult_id} className="timeline-item">
            <p className="timeline-when">{c.as_of.slice(0, 16)}</p>
            <h2>{c.requesting_dept} {c.requester} → {c.target_dept} ({c.urgency})</h2>
            <details>
              <summary>의뢰서 보기</summary>
              <pre className="sheet sheet-plain">{c.document_text}</pre>
            </details>
            {c.replies.length === 0 && <p className="muted">기록된 회신이 없습니다.</p>}
            {c.replies.map((r) => (
              <div key={r.reply_id} className="timeline-reply">
                <p className="timeline-when">{r.replied_at.slice(0, 16)} 회신, {r.replier}</p>
                <p>{r.text}</p>
              </div>
            ))}
          </li>
        ))}
      </ol>
    </section>
  );
}
