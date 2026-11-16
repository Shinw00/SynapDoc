import { useEffect, useState } from "react";
import { api } from "../api.js";

const EXAMPLE = {
  subject_id: 90000001,
  requesting_dept: "외과",
  requester: "박도윤",
  urgency: "긴급",
  recipient: "",
  as_of: "2181-05-16T11:30",
  request_text:
    "수술 후 4일째부터 발열. 혈액배양에서 ESBL 대장균 나왔고 지금 피페라실린-타조박탐 쓰는 중. 항생제 변경 여부랑 치료 기간 문의드림. CT에서 문합부 옆 액체 저류 있음.",
};
const EMPTY = { subject_id: "", requesting_dept: "", requester: "", urgency: "일반", recipient: "", as_of: "", request_text: "" };
const URGENCY = ["일반", "긴급", "응급"];

export default function Compose({ patients, prefill, onCreated }) {
  const [form, setForm] = useState({ ...EMPTY, ...(prefill || {}) });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!busy) return;
    setSeconds(0);
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [busy]);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const ready = form.subject_id && form.requesting_dept && form.requester && form.as_of && form.request_text.trim();

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onCreated(await api.createConsult({ ...form, subject_id: Number(form.subject_id) }));
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  if (busy) {
    return (
      <section className="waiting" aria-live="polite">
        <div className="pulse" aria-hidden="true" />
        <h1>초안을 만들고 있습니다</h1>
        <p>
          기록을 조회해 초안을 쓰고, 문장마다 원문과 대조합니다. 보통 30초에서 1분 정도 걸립니다.
        </p>
        <p className="waiting-time">{seconds}초 지남</p>
      </section>
    );
  }

  return (
    <form className="compose" onSubmit={submit}>
      <div className="compose-head">
        <h1>감염내과에 협진을 의뢰합니다</h1>
        <button type="button" className="link" onClick={() => setForm(EXAMPLE)}>
          환자 1 예시로 채우기
        </button>
      </div>

      {error && <p className="banner banner-error" role="alert">{error}</p>}

      <div className="field-row">
        <label className="field">
          <span>환자</span>
          <select value={form.subject_id} onChange={set("subject_id")} required>
            <option value="">환자를 선택하세요</option>
            {patients.map((p) => (
              <option key={p.subject_id} value={p.subject_id}>
                {p.subject_id} ({p.gender === "M" ? "남" : "여"}, {p.anchor_age}세)
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>기준 시점</span>
          <input type="datetime-local" value={form.as_of} onChange={set("as_of")} required />
          <small>이 시각 이후의 기록은 의뢰서에 쓰이지 않습니다.</small>
        </label>
      </div>

      <div className="field-row">
        <label className="field">
          <span>의뢰과</span>
          <input value={form.requesting_dept} onChange={set("requesting_dept")} placeholder="외과" required />
        </label>
        <label className="field">
          <span>의뢰의</span>
          <input value={form.requester} onChange={set("requester")} placeholder="이름" required />
        </label>
        <label className="field">
          <span>받는 교수 (선택)</span>
          <input value={form.recipient} onChange={set("recipient")} placeholder="비워 두면 감염내과 앞" />
        </label>
      </div>

      <fieldset className="field urgency">
        <legend>응급도</legend>
        {URGENCY.map((u) => (
          <label key={u} className={form.urgency === u ? "chip is-on" : "chip"}>
            <input type="radio" name="urgency" value={u} checked={form.urgency === u} onChange={set("urgency")} />
            {u}
          </label>
        ))}
      </fieldset>

      <label className="field">
        <span>요청 내용</span>
        <textarea rows={6} value={form.request_text} onChange={set("request_text")} required
                  placeholder="환자 상태와 묻고 싶은 내용을 평소 쓰던 대로 적어 주세요. 예: 수술 후 4일째부터 발열, 혈액배양에서 ESBL 대장균. 항생제 변경 여부 문의." />
        <small>사실과 질문을 나누지 않아도 됩니다. 초안을 만들 때 기록과 대조해 확인합니다.</small>
      </label>

      <div className="actions">
        <button className="btn btn-primary" disabled={!ready}>초안 만들기</button>
      </div>
    </form>
  );
}
