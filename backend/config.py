"""바뀌지 않는 설정. 다른 진료과를 추가할 때는 이 파일을 늘린다."""

TARGET_DEPT = "감염내과"

MAX_TOOL_CALLS = 12      # 3단계(수집)에서 에이전트가 도구를 부를 수 있는 횟수
MAX_MODEL_CALLS = 8      # 3단계에서 LLM 을 부를 수 있는 횟수
MAX_REVISE = 2           # 7단계(재생성) 최대 횟수

# 감염내과 협진 의뢰에 들어가야 할 항목표 (11/10 기획안의 표를 옮긴 것).
#   tool   : 이 항목을 채우는 도구
#   days   : 기준 시점에서 며칠 전까지 볼지
#   labs   : get_labs 일 때 조회할 검사 이름 (d_labitems.label 에 포함되는 글자)
#   scope  : get_labs 일 때 current(현재 입원) | past(과거 입원)
CHECKLIST = [
    {"key": "microbiology", "item": "배양 및 항생제 감수성", "required": True,
     "tool": "get_microbiology", "days": 14},
    {"key": "antibiotics", "item": "현재·최근 처방 (항생제 포함)", "required": True,
     "tool": "get_prescriptions", "days": 14},
    {"key": "inflammation", "item": "염증 수치 추이 (WBC, CRP, Lactate)", "required": True,
     "tool": "get_labs", "days": 7,
     "labs": ["White Blood Cells", "C-Reactive Protein", "Lactate"], "scope": "current"},
    {"key": "renal", "item": "신기능 (크레아티닌)", "required": True,
     "tool": "get_labs", "days": 7, "labs": ["Creatinine"], "scope": "current"},
    {"key": "renal_baseline", "item": "신기능 기저치 (과거 입원)", "required": True,
     "tool": "get_labs", "days": 0, "labs": ["Creatinine"], "scope": "past"},
    {"key": "allergy", "item": "약물 알레르기", "required": True,
     "tool": "get_past_records"},
    {"key": "administration", "item": "실제 투여 기록", "required": False,
     "tool": "get_administrations", "days": 14},
    {"key": "imaging", "item": "감염 부위 영상 판독", "required": False,
     "tool": "get_radiology", "days": 14},
    {"key": "history", "item": "기저질환·과거력", "required": False,
     "tool": "get_past_records"},
    {"key": "admission", "item": "현재 입원 정보 (입원일, 진료과, 나이, 성별)", "required": True,
     "tool": "get_admission_info"},
]

TOOL_NAMES = ["get_microbiology", "get_prescriptions", "get_administrations", "get_labs",
              "get_radiology", "get_past_records", "get_admission_info"]

# 의뢰서 섹션 (기획안 환자 1 예시의 구성). 재협진이면 맨 앞에 prior 가 붙는다.
SECTIONS = [
    ("reason", "의뢰 사유"),
    ("history", "진단 및 주요 병력"),
    ("course", "현 입원 경과"),
    ("micro", "미생물 검사"),
    ("labs", "혈액 검사 추이"),
    ("imaging", "영상 검사"),
    ("meds", "현재 투약 및 알레르기"),
    ("other", "기타"),
]
PRIOR_SECTION = ("prior", "이전 협진 요약 및 신규 경과")

SERVICE_NAMES = {"SURG": "외과", "MED": "내과", "ORTHO": "정형외과", "NSURG": "신경외과",
                 "OMED": "혈액종양내과", "CMED": "순환기내과", "NMED": "신경과"}

# 검증에서 쓰는 이름 대응표.
# 문장에 왼쪽 글자가 나오면, 인용한 근거 원문에 오른쪽 글자 중 하나가 있어야 한다.
TERM_ALIASES = {
    # 한글 약물명
    "피페라실린": ["piperacillin"], "타조박탐": ["tazo"], "메로페넴": ["meropenem"],
    "에르타페넴": ["ertapenem"], "세프트리악손": ["ceftriaxone"], "세페핌": ["cefepime"],
    "세파졸린": ["cefazolin"], "반코마이신": ["vancomycin"], "리네졸리드": ["linezolid"],
    "아미카신": ["amikacin"], "겐타마이신": ["gentamicin"], "시프로플록사신": ["ciprofloxacin"],
    "레보플록사신": ["levofloxacin"], "콜리스틴": ["colistin"], "티게사이클린": ["tigecycline"],
    "암피실린": ["ampicillin"], "리팜핀": ["rifampin"], "메트포르민": ["metformin"],
    "노르에피네프린": ["norepinephrine"],
    # 한글 균명
    "대장균": ["escherichia coli", "e. coli"], "녹농균": ["pseudomonas"],
    "황색포도상구균": ["staphylococcus aureus"], "표피포도상구균": ["staphylococcus epidermidis"],
    "폐렴막대균": ["klebsiella"], "그람음성막대균": ["gram negative rod"],
    "그람양성알균": ["gram positive cocc"],
    # 검사 약어
    "WBC": ["white blood"], "CRP": ["c-reactive"], "Cr": ["creatinine"], "ANC": ["neutrophil"],
    "ESBL": ["esbl"], "MRSA": ["staphylococcus aureus", "mrsa"], "CRE": ["carbapenem", "cre"],
}

# 영문 단어 검사에서 건너뛰는 낱말 (단위, 일반 용어)
IGNORE_WORDS = {"with", "that", "from", "this", "level", "dose", "daily", "none"}

# 수신 교수 이름 → 메일 주소. 시나리오의 교수는 가상 인물이므로 팀원 주소를 넣는다.
# 여기에 없으면 .env 의 MAIL_TO_DEFAULT 로 보낸다.
RECIPIENTS: dict[str, str] = {
    # "이서준": "teammate1@example.com",
    # "강성욱": "teammate2@example.com",
}
