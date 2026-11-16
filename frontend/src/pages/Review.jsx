import { useMemo, useState } from "react";
import { api, subjectLine } from "../api.js";

const TABLES = {
  microbiologyevents: "미생물 검사", labevents: "검사 결과", prescriptions: "처방", emar: "투여 기록",
  radiology: "영상 판독문", discharge: "퇴원요약지", diagnoses_icd: "과거 진단", admissions: "입원 정보",
  consults: "이전 의뢰서", replies: "이전 회신",
};

// 문장의 상태를 한 가지로 정리한다: ok(원문 일치) / stated(의뢰의 기재) / bad(확인 필요)
function stateOf(s, edited) {
  if (edited) return "stated";
  if (s.verdict === "일치") return "ok";
  if (s.verdict === "의뢰의 기재") return "stated";
  return "bad";
}
const STATE_LABEL = { ok: "원문과 일치", stated: "의뢰의 기재", bad: "확인 필요" };

export default function Review({ consult, onDone }) {
  const { review, thread_id } = consult;
  const all = useMemo(() => review.sections.flatMap((sec) => sec.sentences), [review]);

  const [selected, setSelected] = useState(all.find((s) => stateOf(s) === "bad")?.sid || all[0]?.sid);
  const [edits, setEdits] = useState({});
  const [deleted, setDeleted] = useState([]);
  // 의뢰의의 질문은 기본 포함, 에이전트가 제안한 질문은 직접 골라야 포함된다
  const [included, setIncluded] = useState(review.questions.map((q) => q.origin === "requester"));
  const [added, setAdded] = useState([]);
  const [newQuestion, setNewQuestion] = useState("");
  const [memo, setMemo] = useState("");
  const [recipient, setRecipient] = useState(review.request.recipient || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const current = all.find((s) => s.sid === selected);
  const mismatched = review.crosscheck.filter((c) => c.verdict !== "일치");
  const missing = review.checklist.filter((c) => c.status === "none");
  const counts = all.reduce((acc, s) => {
    const k = stateOf(s, s.sid in edits);
    return { ...acc, [k]: (acc[k] || 0) + 1 };
  }, {});

  function addQuestion() {
    if (!newQuestion.trim()) return;
    setAdded([...added, newQuestion.trim()]);
    setNewQuestion("");
  }

  async function decide(approved) {
    setBusy(true);
    setError("");
    try {
      const body = approved
        ? { approved: true, edits, deleted, added_questions: added, memo, recipient,
            rejected_questions: included.map((on, i) => (on ? null : i)).filter((i) => i !== null) }
        : { approved: false };
      onDone(await api.approve(thread_id, body));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="review">
      <div className="review-head">
        <h1>{subjectLine(review.request, review.is_reconsult)}</h1>
        <p className="muted">
          의뢰의 {review.request.requesting_dept} {review.request.requester}, 기준 시점 {review.request.as_of.slice(0, 16)}
        </p>
        <ul className="tally" aria-label="문장 검증 결과">
          <li className="tally-ok">원문과 일치 {counts.ok || 0}</li>
          <li className="tally-stated">의뢰의 기재 {counts.stated || 0}</li>
          <li className="tally-bad">확인 필요 {counts.bad || 0}</li>
        </ul>
      </div>

      {(mismatched.length > 0 || missing.length > 0) && (
        <aside className="notice">
          <h2>보내기 전에 확인할 것</h2>
          <ul>
            {mismatched.map((c, i) => (
              <li key={"c" + i}>
                <strong>{c.verdict === "불일치" ? "기록과 다름" : "기록으로 확인 못 함"}</strong>
                입력하신 “{c.fact}” {c.note && <span className="muted">({c.note})</span>}
              </li>
            ))}
            {missing.map((c) => (
              <li key={c.key}>
                <strong>기록 없음</strong>
                {c.item}
              </li>
            ))}
          </ul>
        </aside>
      )}

      {error && <p className="banner banner-error" role="alert">{error}</p>}

      <div className="review-body">
        <article className="sheet">
          {review.sections.map((sec) => (
            <section key={sec.key} className="sheet-section">
              <h2>{sec.title}</h2>
              <p>
                {sec.sentences.map((s) => {
                  const isDeleted = deleted.includes(s.sid);
                  const st = stateOf(s, s.sid in edits);
                  return (
                    <span key={s.sid}>
                      <span role="button" tabIndex={0}
                            className={`sent sent-${st}${selected === s.sid ? " is-selected" : ""}${isDeleted ? " is-deleted" : ""}`}
                            aria-pressed={selected === s.sid}
                            onClick={() => setSelected(s.sid)}
                            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(s.sid); } }}>
                        {edits[s.sid] ?? s.text}
                      </span>{" "}
                    </span>
                  );
                })}
              </p>
            </section>
          ))}

          <section className="sheet-section">
            <h2>의뢰 질문</h2>
            <ul className="questions">
              {review.questions.map((q, i) => (
                <li key={i} className={q.origin === "agent" ? "question is-proposed" : "question"}>
                  <label>
                    <input type="checkbox" checked={included[i]}
                           onChange={() => setIncluded(included.map((on, j) => (j === i ? !on : on)))} />
                    <span>
                      {q.text}
                      {q.origin === "agent" && (
                        <small className="proposal">
                          제안된 질문입니다. {q.reason && `이유: ${q.reason}.`} 넣으려면 선택하세요.
                        </small>
                      )}
                    </span>
                  </label>
                </li>
              ))}
              {added.map((q, i) => (
                <li key={"a" + i} className="question">
                  <label>
                    <input type="checkbox" checked onChange={() => setAdded(added.filter((_, j) => j !== i))} />
                    <span>{q} <small className="proposal">직접 추가한 질문</small></span>
                  </label>
                </li>
              ))}
            </ul>
            <div className="add-question">
              <input value={newQuestion} onChange={(e) => setNewQuestion(e.target.value)}
                     onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addQuestion(); } }}
                     placeholder="질문 추가" aria-label="추가할 질문" />
              <button type="button" className="btn" onClick={addQuestion}>추가</button>
            </div>
          </section>

          <section className="sheet-section">
            <h2>의뢰의 추가 메모</h2>
            <textarea rows={2} value={memo} onChange={(e) => setMemo(e.target.value)}
                      placeholder="기록에 없지만 전하고 싶은 내용 (예: 보호자가 시술 설명을 원함)" aria-label="추가 메모" />
          </section>
        </article>

        <aside className="source" aria-live="polite">
          {current ? (
            <SourcePanel sentence={current} evidence={review.evidence}
                         edit={edits[current.sid]} isDeleted={deleted.includes(current.sid)}
                         onEdit={(text) => {
                           const next = { ...edits };
                           if (text === null || text === current.text) delete next[current.sid];
                           else next[current.sid] = text;
                           setEdits(next);
                         }}
                         onToggleDelete={() =>
                           setDeleted(deleted.includes(current.sid) ? deleted.filter((x) => x !== current.sid) : [...deleted, current.sid])} />
          ) : (
            <p className="muted">문장을 누르면 근거가 된 기록을 보여 줍니다.</p>
          )}
        </aside>
      </div>

      <footer className="approve-bar">
        <label className="field field-inline">
          <span>받는 교수</span>
          <input value={recipient} onChange={(e) => setRecipient(e.target.value)} placeholder="감염내과 앞" />
        </label>
        <div className="approve-actions">
          <button className="btn" disabled={busy} onClick={() => decide(false)}>보내지 않고 닫기</button>
          <button className="btn btn-primary" disabled={busy} onClick={() => decide(true)}>
            {busy ? "보내는 중" : "승인하고 보내기"}
          </button>
        </div>
      </footer>
    </div>
  );
}

function SourcePanel({ sentence, evidence, edit, isDeleted, onEdit, onToggleDelete }) {
  const st = stateOf(sentence, edit !== undefined);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(edit ?? sentence.text);
  const records = sentence.evidence_ids.map((id) => evidence[id]).filter(Boolean);

  // 다른 문장을 고르면 편집 상태를 초기화한다
  const [shown, setShown] = useState(sentence.sid);
  if (shown !== sentence.sid) {
    setShown(sentence.sid);
    setEditing(false);
    setDraft(edit ?? sentence.text);
  }

  return (
    <>
      <p className={`source-state source-${st}`}>{STATE_LABEL[st]}</p>
      <blockquote className="source-quote">{edit ?? sentence.text}</blockquote>

      {edit !== undefined && <p className="source-note">직접 고친 문장입니다. 의뢰서에 “의뢰의 수정”으로 표시됩니다.</p>}
      {edit === undefined && sentence.source === "requester" && (
        <p className="source-note">기록에는 없고 입력하신 내용에서 온 문장입니다. 의뢰서에 “의뢰의 기재”로 표시됩니다.</p>
      )}
      {st === "bad" && sentence.reason && <p className="source-note source-note-bad">{sentence.reason}</p>}

      {editing ? (
        <div className="source-edit">
          <textarea rows={4} value={draft} onChange={(e) => setDraft(e.target.value)} aria-label="문장 고치기" />
          <div className="source-buttons">
            <button className="btn btn-primary" onClick={() => { onEdit(draft.trim()); setEditing(false); }}>고친 문장 쓰기</button>
            <button className="btn" onClick={() => { setDraft(edit ?? sentence.text); setEditing(false); }}>취소</button>
          </div>
        </div>
      ) : (
        <div className="source-buttons">
          <button className="btn" onClick={() => setEditing(true)}>문장 고치기</button>
          {edit !== undefined && <button className="btn" onClick={() => { onEdit(null); setDraft(sentence.text); }}>원래대로</button>}
          <button className="btn" onClick={onToggleDelete}>{isDeleted ? "지우기 취소" : "문장 지우기"}</button>
        </div>
      )}

      <h3 className="source-title">근거가 된 기록 {records.length}건</h3>
      {records.length === 0 && <p className="muted">연결된 기록이 없습니다.</p>}
      <ol className="records">
        {records.map((r) => (
          <li key={r.id} className="record">
            <div className="record-head">
              <span className="record-table">{TABLES[r.table] || r.table}</span>
              <span className="record-id">{r.id}</span>
            </div>
            <pre className="record-text">{r.text}</pre>
          </li>
        ))}
      </ol>
    </>
  );
}
