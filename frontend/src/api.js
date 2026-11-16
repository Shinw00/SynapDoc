// 백엔드(FastAPI) 호출. 주소는 .env 의 VITE_API_URL 로 바꾼다.
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function call(path, options = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new Error(`서버에 연결할 수 없습니다. 백엔드가 ${BASE} 에서 실행 중인지 확인해 주세요.`);
  }
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json()).detail;
    } catch {
      /* 본문이 없는 오류 */
    }
    throw new Error(typeof detail === "string" && detail ? detail : `요청을 처리하지 못했습니다 (${res.status}).`);
  }
  return res.json();
}

export const api = {
  patients: () => call("/patients"),
  history: (subjectId) => call(`/patients/${subjectId}/consults`),
  createConsult: (body) => call("/consults", { method: "POST", body }),
  getConsult: (threadId) => call(`/consults/${threadId}`),
  approve: (threadId, body) => call(`/consults/${threadId}/approve`, { method: "POST", body }),
  reply: (threadId, body) => call(`/consults/${threadId}/reply`, { method: "POST", body }),
};

export function subjectLine(request, isReconsult) {
  const head = isReconsult ? "재협진의뢰" : "협진의뢰";
  return `[${head}][${request.urgency || "일반"}] ${request.requesting_dept} → 감염내과 | 환자 ${request.subject_id}`;
}
