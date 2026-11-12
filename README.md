# SynapDoc

3차 병동 의사가 환자 ID와 짧은 협진 요청을 입력하면, 에이전트가 협진 시점 이전의 EMR 데이터와 피의뢰과 체크리스트를 조회해 의뢰서 초안을 만듭니다. 초안은 근거 검증을 거친 뒤 의뢰의가 승인·수정·반려할 수 있고, 승인된 문서만 피의뢰 교수에게 발송됩니다.

현재 프로토타입 범위는 환자 1명과 특정 피의뢰과 1개입니다. 데이터와 의사·과 정보는 JSON/SQLite 합성 데이터로 대체되어 있으며, 실제 MIMIC-IV 연결은 이후 단계입니다.

## 실행

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python support/build_synthetic.py
uvicorn api:app --reload
```

`support/build_synthetic.py`는 프로젝트 루트의 `SynapDoc 가상 EMR 데이터 (환자 1).xlsx`를 읽어 `support/emr.sqlite`와 `support/synthetic/*.csv`를 다시 만듭니다.

브라우저에서 `http://localhost:8000`을 열어 의뢰과, 의뢰의, 피의뢰과, 피의뢰의, 환자 검색·선택, 응급도, 협진 기준 시점, 현재 진단, 간단한 의뢰 내용을 입력합니다. 기본 메일 모드는 실제 발송 없이 `support/consults/<consult_id>/sent.eml`로 저장하는 `outbox`입니다.

## 핵심 흐름

1. `POST /api/consults`가 입력을 검증하고 협진 작업을 시작합니다.
2. 에이전트가 환자 기본 정보, 입원 기록, 과거 노트, 검사·배양·약물·영상 자료를 조회합니다.
3. `support/resources/dept_profile_ID.json`의 피의뢰과 요구 데이터와 `consult_template.json`을 기준으로 초안을 작성합니다.
4. 초안의 문장별 근거, 협진 시점 이후 데이터 유입, 수치 불일치, 필수 항목 누락을 검증합니다.
5. 의뢰의 승인 후에만 `doctors.json`의 피의뢰 교수에게 메일을 만듭니다.

## 주요 파일

- `api.py`, `static/index.html`: 웹 API와 프로토타입 UI
- `graph.py`, `middleware.py`, `tools.py`: 단일 협진 에이전트와 안전장치
- `support/emr.py`, `support/data.py`: EMR 조회와 협진 상태 저장
- `support/writer.py`, `support/verify.py`, `support/render.py`: 초안 작성·검증·HTML 문서화
- `support/mailer.py`: outbox 저장 또는 SMTP 발송
- `support/resources/*.json`: 피의뢰과 체크리스트, 의사 디렉터리, 문서 템플릿
- `scenarios/patient1_request.json`: 현재 시연용 환자 1명 입력 예시

## 데이터 범위 주의

협진 시점 이후의 기록은 초안에 사용하지 않도록 조회 함수가 기준 시각으로 필터링합니다. 현재 합성 데이터는 시연용이므로, 실제 MIMIC-HOPE/MIMIC-IV를 연결할 때는 데이터 사용 권한과 비식별화 상태를 별도로 확인해야 합니다.

`W05_Middleware.zip`은 영화 예매를 소재로 한 수업용 Middleware 예제입니다. 구조와 승인·검증 개념만 참고하고, 예매 도메인 코드는 SynapDoc에 포함하지 않습니다.
