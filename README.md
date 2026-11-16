# SynapDoc

협진 의뢰서 초안을 만들고, 원문과 대조해 검증한 뒤, 의사의 승인을 받아 보내는 에이전트.

협진 요청을 보내는 곳 : 여러과 
협진 요청을 받는 곳 : 감염내과 


```
SynapDoc/
├── backend/    에이전트(LangGraph) + API(FastAPI) + 메일 + 테스트 데이터   → backend/README.md # 진교님, 서희님꺼
└── frontend/   화면(React + Vite) # 신우님꺼로 교체하면 됨
```

## 실행

터미널 두 개 열어서 해야됨 

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

