# SynapDoc

감염내과 협진 의뢰서 초안을 만들고, 원문과 대조해 검증한 뒤, 의사의 승인을 받아 보내는 에이전트.

```
SynapDoc/
├── backend/    에이전트(LangGraph) + API(FastAPI) + 메일 + 테스트 데이터   → backend/README.md
└── frontend/   화면(React + Vite)
```

## 실행

터미널 두 개를 쓴다.

```bash
# 1) 백엔드
cd backend
pip install -r requirements.txt
cp .env.example .env            # HAI_API_KEY, HAI_MODEL 을 채운다
uvicorn api:app --reload --port 8000

# 2) 화면
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

화면에서 "환자 1 예시로 채우기"를 누르고 "초안 만들기"를 누르면 된다.

## 화면

- **의뢰 작성**: 환자, 기준 시점, 의뢰과, 의뢰의, 응급도, 요청 내용
- **초안 검토**: 왼쪽은 의뢰서, 오른쪽은 고른 문장의 근거 기록.
  밑줄 색이 검증 상태다 (초록 실선 = 원문과 일치, 호박 점선 = 의뢰의 기재, 빨강 = 확인 필요).
  문장을 고치거나 지우고, 제안된 질문을 고르고, 질문과 메모를 더한 뒤 승인한다.
- **발송 결과**: 보낸 메일과 의뢰서, 감염내과 회신 기록, 재협진 작성
- **협진 이력**: 환자별로 보낸 의뢰서와 회신

백엔드 주소가 `http://localhost:8000` 이 아니면 `frontend/.env` 에 `VITE_API_URL` 을 적는다.
화면을 다른 포트에서 띄우면 `backend/.env` 의 `CORS_ORIGINS` 에 그 주소를 더한다.
