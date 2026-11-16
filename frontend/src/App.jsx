import { useEffect, useState } from "react";
import { api } from "./api.js";
import Compose from "./pages/Compose.jsx";
import Review from "./pages/Review.jsx";
import Result from "./pages/Result.jsx";
import History from "./pages/History.jsx";

// 화면은 네 가지: 의뢰 작성 → 초안 검토 → 발송 결과, 그리고 협진 이력.
export default function App() {
  const [view, setView] = useState("compose");
  const [patients, setPatients] = useState([]);
  const [consult, setConsult] = useState(null); // 백엔드가 돌려준 의뢰 상태
  const [prefill, setPrefill] = useState(null); // 재협진 작성 시 미리 채울 값
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    api.patients().then(setPatients).catch((e) => setLoadError(e.message));
  }, []);

  function onCreated(result) {
    setConsult(result);
    setView(result.status === "awaiting_approval" ? "review" : "result");
  }

  function startReconsult(request) {
    setPrefill({ ...request, request_text: "", as_of: "" });
    setConsult(null);
    setView("compose");
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-name">SynapDoc</span>
          <span className="brand-sub">감염내과 협진 의뢰서</span>
        </div>
        <nav className="nav" aria-label="화면 이동">
          <button className={view !== "history" ? "nav-item is-active" : "nav-item"}
                  onClick={() => setView(consult ? (consult.status === "awaiting_approval" ? "review" : "result") : "compose")}>
            의뢰서
          </button>
          <button className={view === "history" ? "nav-item is-active" : "nav-item"} onClick={() => setView("history")}>
            협진 이력
          </button>
        </nav>
      </header>

      {loadError && <p className="banner banner-error" role="alert">{loadError}</p>}

      <main className="main">
        {view === "compose" && <Compose patients={patients} prefill={prefill} onCreated={onCreated} />}
        {view === "review" && consult && (
          <Review consult={consult} onDone={(r) => { setConsult(r); setView("result"); }} />
        )}
        {view === "result" && consult && (
          <Result consult={consult}
                  onNew={() => { setConsult(null); setPrefill(null); setView("compose"); }}
                  onReconsult={() => startReconsult(consult.review.request)} />
        )}
        {view === "history" && <History patients={patients} />}
      </main>
    </div>
  );
}
