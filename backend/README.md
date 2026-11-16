# SynapDoc 백엔드 — 감염내과 협진 의뢰서 초안 에이전트

의뢰의의 요청을 받아 EMR 을 조회하고, 근거가 붙은 협진 의뢰서 초안을 만들어 검증한 뒤,
의사의 승인을 받아 메일로 보낸다. 수신과는 감염내과로 고정이고 의뢰과는 제한이 없다.

## 시작하기

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # HAI_API_KEY 를 채운다

python -m tests.test_offline  # API 키 없이 흐름 확인 (가짜 LLM)
python run.py 1               # 실제 LLM 으로 환자 1 시나리오 실행 (터미널에서 승인)
uvicorn api:app --reload --port 8000   # React 와 연결할 서버. 문서: http://localhost:8000/docs
```

## 동작 과정

| 단계 | 파일 | 하는 일 | 누가 판단 |
|---|---|---|---|
| 1 요청 해석 | `nodes/parse.py` | 입력을 사실 진술과 질문으로 나눔. 이전 협진이 있으면 재협진 | LLM |
| 2 체크리스트 | `nodes/plan.py` | `config.CHECKLIST` 를 깔고 환자별 항목만 추가 | 고정 + LLM |
| 3 수집 | `nodes/collect.py` | 에이전트가 도구를 골라 조회. 빠뜨린 항목은 코드가 보충 | LLM (자율) + 코드 |
| 4 교차 확인 | `nodes/crosscheck.py` | 의사가 말한 사실이 기록과 맞는지 | LLM |
| 5 초안 | `nodes/draft.py` | 문장마다 근거 ID 를 붙여 작성 | LLM |
| 6 검증 | `nodes/verify.py` | 수치·날짜·이름은 코드로, 뜻은 LLM 으로 대조 | 코드 + LLM |
| 7 재생성 | `nodes/revise.py` | 걸린 문장만 수정 (최대 2회) | LLM |
| 8 승인 | `nodes/approve.py` | 초안을 보여주고 멈춤 | 의사 |
| 9 발송·저장 | `nodes/send.py` | 메일 발송, 협진 이력 저장 | 코드 |

순서는 `graph.py` 에 고정돼 있다. LLM 이 경로를 정하는 곳은 3단계 안쪽뿐이다.

## 파일 구성

```
backend/
├── llm.py            HAI 게이트웨이 연결
├── state.py          노드 사이를 오가는 데이터의 틀
├── schemas.py        LLM 이 답할 때 지키는 형식
├── config.py         감염내과 항목표, 횟수 상한, 이름 대응표, 수신 주소
├── prompts.py        노드별 지시문
├── tools.py          EMR 조회 도구 (3단계에서 에이전트가 고름)
├── middleware.py     도구 호출 상한, 로그, 금지 인자 차단
├── nodes/            9단계
├── graph.py          노드 연결
├── render.py         의뢰서 글과 메일 본문 만들기 (LLM 없음)
├── api.py            FastAPI
├── run.py            터미널 실행
├── logger.py
├── tests/            가짜 LLM 으로 흐름 확인
└── support/
    ├── db.py         EMR 조회 (읽기 전용, 시점 필터)
    ├── consults.py   협진 이력 저장소
    ├── mailer.py     메일 발송
    └── test/
        ├── test.xlsx       테스트 데이터 (가상 환자 1)
        ├── load_test.py    xlsx → test.sqlite 변환
        └── scenarios.json  시나리오별 의뢰 입력
```

## 데이터 바꾸기

지금은 `support/test/test.xlsx` 를 SQLite 로 바꿔 쓴다. `test.sqlite` 가 없으면 처음 실행할 때 자동으로 만든다.

- 엑셀을 고쳤으면: `python -m support.test.load_test`
- 환자 2~5 추가: 같은 엑셀의 각 탭에 행을 이어 붙이고, `scenarios.json` 에 입력을 추가
- 실제 SQL DB 가 준비되면: `.env` 의 `EMR_DB_PATH` 만 바꾼다 (SQLite 파일, MIMIC-IV 컬럼 이름 기준)

## React 연결

| 주소 | 설명 |
|---|---|
| `POST /consults` | 의뢰 생성. 1~7단계를 돌리고 승인 대기 상태의 초안을 돌려준다 (수십 초 걸림) |
| `GET /consults/{thread_id}` | 현재 상태 |
| `POST /consults/{thread_id}/approve` | 승인·수정 → 발송 |
| `POST /consults/{thread_id}/reply` | 감염내과 회신 저장 |
| `GET /patients` | 환자 목록 |
| `GET /patients/{subject_id}/consults` | 협진 이력 |

`POST /consults` 요청

```json
{"subject_id": 90000001, "requesting_dept": "외과", "requester": "박도윤", "urgency": "긴급",
 "recipient": "", "as_of": "2181-05-16 11:30:00", "request_text": "수술 후 4일째부터 발열. ..."}
```

응답의 `review` (초안 검토 화면에 그대로 쓰는 값)

- `sections[].sentences[]` : `sid`, `text`, `evidence_ids`, `source`, `verdict`, `reason`
  - `source` : `emr`(기록 근거) / `requester`(의뢰의 기재) / `requester_edit`(의뢰의 수정)
  - `verdict` : `일치` / `의뢰의 기재` / `불일치` / `근거 없음`
- `evidence` : `{근거 ID: {text, table, time}}` — 문장을 누르면 보여줄 원문
- `questions[]` : `text`, `origin`(`requester` / `agent` 제안), `reason`
- `crosscheck[]` : 의뢰의 진술별 `일치` / `불일치` / `확인 불가`
- `checklist[]` : 항목별 `found` / `none`(기록 없음)
- `warnings[]` : 재생성 후에도 남은 검증 문제

`POST /consults/{thread_id}/approve` 요청

```json
{"approved": true, "edits": {"s3": "고친 문장"}, "deleted": ["s9"],
 "rejected_questions": [2], "added_questions": ["추가 질문"], "memo": "추가 메모", "recipient": "이서준"}
```

## 메일

처음에는 `MAIL_DRY_RUN=true` 로 둔다. 실제로 보내지 않고 `outbox/` 에 메일(.eml)과 첨부(html)를 저장한다.

실제로 보내려면
1. 발신용 지메일에서 2단계 인증을 켜고 앱 비밀번호를 발급받는다.
2. `.env` 에 `MAIL_USER`, `MAIL_PASSWORD`, `MAIL_TO_DEFAULT` 를 채우고 `MAIL_DRY_RUN=false` 로 바꾼다.
3. 교수별로 다른 주소로 보내려면 `config.RECIPIENTS` 에 이름과 주소를 넣는다.

발송은 8단계에서 승인된 경우에만 실행된다. 메일 기능은 가상 환자 데이터에만 쓴다.

## 알아둘 점

- **지금 데이터에 없는 것**: 활력징후(체온, 혈압), 체중, 현재 입원의 진단명과 수술명.
  의뢰의가 입력한 내용이면 `(의뢰의 기재)` 로 표시돼 들어가고, 입력에도 없으면 의뢰서에 쓰이지 않는다.
- **검증의 한계**: 수치, 날짜, 약물명, 균명은 코드가 대조한다. 내성(R)과 감수성(S)을 뒤바꿔 쓴 것처럼
  낱말과 숫자는 맞고 뜻만 틀린 경우는 LLM 판정에 맡긴다.
- **한글 약물명·균명**: `config.TERM_ALIASES` 의 대응표로 확인한다. 새 약물이 나오면 여기에 추가한다.
