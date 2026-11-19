import React, { useState } from 'react';
import { 
  FileText, 
  UserCheck, 
  RefreshCw, 
  Sparkles, 
  Edit3, 
  Check, 
  Send, 
  AlertCircle, 
  Stethoscope, 
  CheckCircle2,
  X,
  ClipboardList,
  Activity,
  ShieldCheck,
  Target,
  Building2
} from 'lucide-react';

// --- 감염내과 협진에 특화된 의뢰 목적 카테고리 ---
const CONSULT_PURPOSE_CATEGORIES = [
  '표적 항생제 변경 및 용량 조절',
  '수술 부위 감염(SSI) 및 균혈증 관리',
  '호중구감소성 발열 및 기회감염 평가',
  '불명열 및 감염원(Source) 감별',
  '항생제 치료 기간 및 경구 전환 자문'
] as const;

// --- 의뢰과별 소속 교수진 매핑 ---
const FROM_DEPT_PROFESSORS: Record<string, string[]> = {
  외과: ['박도윤', '김민수', '이준호'],
  정형외과: ['최강민', '서진우', '한승현'],
  혈액종양내과: ['강태호', '오수진', '정민재'],
  신경외과: ['송현우', '조은비'],
  소화기내과: ['임재현', '윤서연']
};

// --- 피의뢰과(감염내과 고정) 소속 교수진 ---
const INFECTIOUS_DISEASE_PROFESSORS = ['이서준', '정하윤', '김지현', '박성호'] as const;

// --- 타입 정의 ---
interface PatientScenario {
  id: string;
  name: string;
  genderAge: string;
  weight: string;
  ward: string;
  admissionDate: string;
  mainDiagnosis: string;
  consultPurpose: string;
  fromDept: string;
  fromProf: string;
  toDept: string;
  toProf: string;
  urgency: '긴급(STAT)' | '정규(Routine)';
  requestTime: string;
  surgeryHistory: string;
  rawNote: string;
  generatedDraft: {
    reason: string;
    history: string;
    specificRequests: string;
  };
}

// --- 3가지 가상 환자 시나리오 (모두 타과 -> 감염내과 협진 케이스) ---
const MOCK_SCENARIOS: PatientScenario[] = [
  {
    // 케이스 1: 외과 -> 감염내과 (S상결장암 복강경 수술 후 발열 및 혈액배양 ESBL 대장균 검출)
    id: '#1234567',
    name: '박민우',
    genderAge: 'M/68',
    weight: '68kg',
    ward: '51병동',
    admissionDate: '2026-11-10',
    mainDiagnosis: 'C18.7 S상 결장암 (Malignant neoplasm of sigmoid colon)',
    consultPurpose: '표적 항생제 변경 및 용량 조절',
    fromDept: '외과',
    fromProf: '박도윤',
    toDept: '감염내과',
    toProf: '이서준',
    urgency: '긴급(STAT)',
    requestTime: '2026-11-17 17:00',
    surgeryHistory: '복강경 하 S상결장절제술(Laparoscopic anterior resection) 시행 (2026-11-10)',
    rawNote: 'S상 결장암 수술 후 POD 4일째(11/14)부터 38.5℃ 이상 발열 지속됨. 말초 혈액배양 2쌍에서 ESBL(+) E. coli 동정됨. 현재 Cefotaxime 투여 중이나 발열 및 CRP 악화 추세로 카바페넴계 변경 및 치료 기간 자문 구함.',
    generatedDraft: {
      reason: '[표적 항생제 변경 및 용량 조절] S상결장절제술 후 발생한 ESBL(+) E. coli 균혈증의 항생제 변경 및 치료 기간 자문 의뢰드립니다.',
      history: `[임상 경과 요약]
상기 68세 남환(68kg)은 S상 결장암 진단 하에 2026-11-10 복강경 하 S상결장절제술 시행 후 POD 4일차(11/14)부터 38.5℃ 이상의 고열이 지속되고 있습니다.

• 최근 활력징후(Vital Signs) 및 혈역학적 상태:
  - BP 108/66 mmHg, HR 104 bpm, RR 20/min, BT 38.6℃, SpO2 97%(Room air) — 승압제 미사용, 혈역학적 안정
• 배양 및 항생제 감수성 (최근 14일):
  - 말초 혈액배양 (11/14, 2쌍 모두 양성): ESBL(+) Escherichia coli 동정
    (내성: Ampicillin, Cefotaxime, Ceftriaxone, Ciprofloxacin / 감수성: Ertapenem, Meropenem, Amikacin)
  - 소변배양 (11/14) 및 중심정맥관 끝 배양 (11/15): 음성(No growth)
  - 추적 혈액배양 (11/16 시행, 2쌍): 현재 배양 진행 중(결과 대기)
• 현재·최근 항생제 (최근 14일):
  - Cefotaxime 2g IV q8h (11/14 ~ 현재, 4일차) / Metronidazole 500mg IV q8h (11/14 ~ 현재, 4일차)
  - [eMAR 투여 기록] 투여 시작(11/14) 이후 처방 용량 100% 정시 투여 완료 (누락 및 지연 이력 없음)
• 염증 수치 추이 (최근 7일):
  - WBC (/μL): 8,400 (11/12) → 13,900 (11/15) → 16,800 (11/17, Neutrophil 89%)
  - CRP (mg/dL): 5.2 (11/12) → 14.8 (11/15) → 18.4 (11/17, 지속 상승)
  - Lactate (mmol/L): 1.1 (11/14) → 1.9 (11/16) → 2.4 (11/17)
• 신기능 (최근 7일 + 기저치):
  - Baseline (입원 시): Cr 0.92 mg/dL, eGFR 84 mL/min/1.73m²
  - 현재 (11/17): Cr 1.38 mg/dL, eGFR 51 mL/min/1.73m² (기저치 대비 Cr 1.5배 상승, AKI Stage 1 소견)
• 카테터 및 배액관(Drain/Line) 유지 현황:
  - 중심정맥관 11/15 제거 완료, 도뇨관 11/13 제거 완료, 복강 내 JP drain 유지 중(장액혈성 배액 40mL/day, 탁한 양상 없음)
• 약물 알레르기 (퇴원요약지 기준):
  - Sulfa 계열(TMP-SMX) 복용 시 전신 두드러기 병력 있음 (베타락탐/카바페넴 알레르기 없음)
• 감염 부위 영상 판독 (최근 14일):
  - Abdomen-Pelvis CT (11/16): 문합부 주위 소량 액체 저류(2.3×1.8cm) 및 주변 지방층 침윤 소견, 명확한 천공이나 대량 농양은 없음
• 기저질환 및 과거력:
  - 제2형 당뇨병(10년, HbA1c 7.6%), 고혈압`,
      specificRequests: '- ESBL(+) E. coli 균혈증 환자의 체중(68kg) 및 AKI Stage 1(eGFR 51) 상태를 고려한 카바페넴계(Ertapenem vs Meropenem) 선택 및 신기능 맞춤형 용량·투여 간격 권고 부탁드립니다.\n- 문합부 주위 소량 액체 저류(2.3cm) 및 현재 유지 중인 JP drain 관리와 관련하여 항생제 단독 치료 가능 여부 및 경피적 배액술(PCD) 적응증 평가 부탁드립니다.\n- 추적 혈액배양(11/16) 음전 확인 시 권장되는 총 정주 항생제 투여 기간 및 경구 전환 가능 여부에 대해 자문 구합니다.'
    }
  },
  {
    // 케이스 2: 정형외과 -> 감염내과 (인공슬관절 치환술 후 수술 부위 화농성 삼출물 및 MRSA 의심)
    id: '#8901234',
    name: '김영희',
    genderAge: 'F/74',
    weight: '56kg',
    ward: '72병동',
    admissionDate: '2026-11-05',
    mainDiagnosis: 'T84.5 인공관절 삽입물 감염 의심 / M17.1 우측 무릎 골관절염',
    consultPurpose: '수술 부위 감염(SSI) 및 균혈증 관리',
    fromDept: '정형외과',
    fromProf: '최강민',
    toDept: '감염내과',
    toProf: '김지현',
    urgency: '긴급(STAT)',
    requestTime: '2026-11-17 17:15',
    surgeryHistory: '우측 인공슬관절 전치환술(Right TKR) 시행 (2026-11-06)',
    rawNote: '우측 TKR 수술 후 POD 9일차(11/15)부터 수술 창상 발적, 열감 및 화농성 삼출물 발생. 창상 배양 그람염색에서 GPC in clusters 확인되어 MRSA 인공관절 감염 강력 의심됨. 경험적 Vancomycin 시작 여부 및 수술적 변연절제술(DAIR) 병행 시 항생제 전략 문의.',
    generatedDraft: {
      reason: '[수술 부위 감염(SSI) 및 균혈증 관리] 우측 인공슬관절 전치환술 후 발생한 MRSA 인공관절 감염(PJI) 의심 소견에 대한 항생제 선택 및 DAIR 병행 치료 전략 자문 의뢰드립니다.',
      history: `[임상 경과 요약]
상기 74세 여환(56kg)은 우측 무릎 골관절염으로 2026-11-06 우측 인공슬관절 전치환술(TKR) 시행 후 POD 9일차(11/15)부터 수술 부위 종창, 열감 및 화농성 삼출물이 동반되며 미열(37.9℃)이 발생하였습니다.

• 최근 활력징후(Vital Signs) 및 혈역학적 상태:
  - BP 126/74 mmHg, HR 88 bpm, RR 18/min, BT 37.9℃, SpO2 98%(Room air) — 승압제 미사용, 혈역학적 안정
• 배양 및 항생제 감수성 (최근 14일):
  - 우측 슬관절 천자액 배양 (11/15, 중간 보고): Methicillin-resistant Staphylococcus aureus (MRSA) 동정
    (내성: Oxacillin, Cefazolin, Clindamycin / 감수성: Vancomycin MIC 1.0, Teicoplanin, Linezolid, Rifampin)
  - 말초 혈액배양 (11/15, 2쌍): 현재까지 48시간 배양 음성(No growth)
  - 추적 혈액배양 (11/17 시행, 2쌍): 현재 배양 진행 중(결과 대기) / 금일 DAIR 수술 중 심부 조직배양 시행 예정
• 현재·최근 항생제 (최근 14일):
  - 예방적 Cefazolin 1g IV q8h (11/06 ~ 11/08, 48시간 투여 후 종료)
  - Cefazolin 2g IV q8h 재투여 (11/15 ~ 현재, 3일차 — MRSA 확인되어 변경 필요)
  - [eMAR 투여 기록] 투여 시작(11/06) 이후 11/16 야간 1회 투여가 정맥로 확보 지연으로 2시간 지연 투여됨, 그 외 정상 투여 완료
• 염증 수치 추이 (최근 7일):
  - WBC (/μL): 7,800 (11/11) → 11,400 (11/15) → 13,200 (11/17)
  - CRP (mg/dL): 3.1 (11/11) → 9.6 (11/15) → 15.2 (11/17, 지속 상승)
  - Lactate (mmol/L): 0.9 (11/15) → 1.2 (11/17)
• 신기능 (최근 7일 + 기저치):
  - Baseline (입원 시): Cr 1.15 mg/dL, eGFR 47 mL/min/1.73m² (기저 CKD Stage 3a)
  - 현재 (11/17): Cr 1.22 mg/dL, eGFR 44 mL/min/1.73m² (기저치 대비 안정적 유지)
• 카테터 및 배액관(Drain/Line) 유지 현황:
  - 수술 부위 Hemovac 11/08 제거 완료, 중심정맥관·도뇨관 없음, 말초 정맥로(20G) 유지 중
• 약물 알레르기 (퇴원요약지 기준):
  - 특이 약물 알레르기 없음 (NKDA)
• 감염 부위 영상 판독 (최근 14일):
  - Right Knee X-ray & Ultrasound (11/16): 인공관절 치환물 해리(Loosening) 소견은 없으나, 슬개상부 윤활낭(Suprapatellar pouch) 내 중등도 관절 삼출액 및 활막 비후 소견 관찰됨
• 기저질환 및 과거력:
  - 만성신질환(CKD Stage 3a), 류마티스 관절염(저용량 Prednisolone 5mg qd 장기 복용 중), 당뇨병`,
      specificRequests: '- 급성기 MRSA 인공슬관절 감염(PJI)에 대해 환자 체중(56kg) 및 기저 CKD(eGFR 44)를 반영한 Vancomycin 부하/유지용량(AUC/MIC 또는 Trough TDM 목표치 포함) 또는 Teicoplanin/Daptomycin 대체 선택 권고 부탁드립니다.\n- 금일 예정된 수술적 세척 및 변연절제술(DAIR) 이후 Rifampin 병합 시작 시점 및 용량, 경구 전환 시 권장 조합과 총 항생제 유지 기간에 대한 고견 구합니다.\n- 장기 정주 항생제 투여 및 지연 투여 방지를 위한 PICC 삽입 필요 여부 함께 확인 부탁드립니다.'
    }
  },
  {
    // 케이스 3: 혈액종양내과 -> 감염내과 (항암치료 후 호중구감소성 발열 및 폐렴 의심)
    id: '#4567890',
    name: '이철수',
    genderAge: 'M/63',
    weight: '64kg',
    ward: '81병동(무균실)',
    admissionDate: '2026-11-04',
    mainDiagnosis: 'D70.0 항암치료 후 호중구감소성 발열 / C92.0 급성 골수성 백혈병(AML)',
    consultPurpose: '호중구감소성 발열 및 기회감염 평가',
    fromDept: '혈액종양내과',
    fromProf: '강태호',
    toDept: '감염내과',
    toProf: '박성호',
    urgency: '긴급(STAT)',
    requestTime: '2026-11-17 17:30',
    surgeryHistory: '수술력 없음 — 관해유도 항암화학요법(Cytarabine + Idarubicin, 7+3) 시행 완료 (2026-11-05 ~ 11/11)',
    rawNote: 'AML 관해유도 항암 후 ANC 80 상태. 11/14부터 38.8℃ 발열로 Cefepime 시작했으나 72시간 이상 발열 지속되고 기침 및 산소요구량 증가함. Chest CT상 우하엽 폐침윤 및 Halo sign 의심 소견 있어 항생제 확장 및 항진균제 추가 자문 요청.',
    generatedDraft: {
      reason: '[호중구감소성 발열 및 기회감염 평가] AML 관해유도 항암 후 지속되는 호중구감소성 발열 및 침습성 폐 진균감염(IPA) 의심 병변에 대한 항생제·항진균제 조절 자문 의뢰드립니다.',
      history: `[임상 경과 요약]
상기 63세 남환(64kg)은 급성 골수성 백혈병(AML)으로 11/05~11/11 관해유도 항암화학요법(7+3) 시행 후 심한 호중구감소증(ANC 80/μL)이 지속 중이며, 11/14부터 발생한 38.8℃ 고열이 경험적 항생제 투여 4일차에도 호전되지 않고 경미한 저산소증(Nasal O2 2L/min)이 동반되었습니다.

• 최근 활력징후(Vital Signs) 및 혈역학적 상태:
  - BP 98/60 mmHg, HR 116 bpm, RR 24/min, BT 38.9℃, SpO2 93%(Nasal O2 2L/min) — 승압제 미사용(수액 소생술 유지 중, 혈압 경계선 모니터링 필요)
• 배양 및 항생제 감수성 (최근 14일):
  - 말초 및 히크만 카테터 혈액배양 (11/14, 11/16 각 2쌍): 세균 배양 모두 음성(No growth)
  - 객담 일반세균 배양 (11/15): 상재균 외 병원균 미동정 / 호흡기 바이러스 PCR 패널: 전 항목 음성
  - 혈청 Galactomannan 항원 검사 (11/16): 1.42 ODI 양성 (기준치 ≥ 0.5)
  - 추적 혈액배양 (11/17 시행, 2쌍): 현재 배양 진행 중(결과 대기) / 기관지폐포세척술(BAL) 진균·세균 배양 의뢰 예정
• 현재·최근 항생제 (최근 14일):
  - Cefepime 2g IV q8h (11/14 ~ 현재, 4일차)
  - 예방적 Levofloxacin 500mg PO qd (11/08 ~ 11/14 발열 시 중단), Acyclovir 400mg PO bid 유지 중
  - [eMAR 투여 기록] 투여 시작(11/08) 이후 모든 정주 및 경구 항균제 누락·지연 없이 100% 투여 완료
• 염증 수치 추이 (최근 7일):
  - WBC / ANC (/μL): 1,200 / 420 (11/12) → 400 / 110 (11/15) → 280 / 80 (11/17, Profound neutropenia)
  - CRP (mg/dL): 2.8 (11/12) → 11.5 (11/15) → 21.6 (11/17, 급격 상승)
  - Lactate (mmol/L): 1.3 (11/14) → 2.1 (11/16) → 2.8 (11/17)
• 신기능 (최근 7일 + 기저치):
  - Baseline (입원 시): Cr 0.85 mg/dL, eGFR 92 mL/min/1.73m²
  - 현재 (11/17): Cr 1.04 mg/dL, eGFR 74 mL/min/1.73m² (경미한 상승 추세이나 정상 범위 유지)
• 카테터 및 배액관(Drain/Line) 유지 현황:
  - 우측 쇄골하 Hickman catheter 유지 중(삽입부 발적·압통·삼출물 없음), 도뇨관 없음
• 약물 알레르기 (퇴원요약지 기준):
  - Penicillin 계열(Piperacillin/Tazobactam) 과거 투여 시 전신 홍반성 발진 병력 있음
• 감염 부위 영상 판독 (최근 14일):
  - Chest CT (11/17): 우하엽(RLL) 및 좌상엽(LUL)에 다발성 결절성 폐침윤 및 주변부 간유리음영(Halo sign) 관찰 — 침습성 폐 아스페르길루스증(Invasive pulmonary aspergillosis) 강력 의심
• 기저질환 및 과거력:
  - 급성 골수성 백혈병(면역저하, 중심정맥관 Hickman catheter 거치 중), 과거 결핵력 없음`,
      specificRequests: '- 지속되는 호중구감소성 발열 및 Chest CT Halo sign·혈청 Galactomannan 양성 소견에 대해 체중(64kg) 기준 Voriconazole(부하/유지용량 및 TDM 계획) 또는 Liposomal Amphotericin B 선택 권고 부탁드립니다.\n- 페니실린 알레르기 병력 및 경계선 혈압(BP 98/60)을 고려하여 현재 Cefepime을 Meropenem으로 에스컬레이션할 필요성 및 경험적 Vancomycin 추가 여부 자문 구합니다.\n- 현재 거치 중인 Hickman catheter 유지 가능 여부와 향후 추적 혈액배양·BAL 결과에 따른 항균제 조정 방향 고견 부탁드립니다.'
    }
  }
];

// 폼 데이터를 기반으로 의학적 일관성이 반영된 초안을 구성하는 헬퍼 함수
const buildConsistentDraft = (data: PatientScenario) => {
  const matchedScenario = MOCK_SCENARIOS.find((s) => s.id === data.id);
  if (
    matchedScenario &&
    matchedScenario.consultPurpose === data.consultPurpose &&
    matchedScenario.mainDiagnosis === data.mainDiagnosis &&
    matchedScenario.surgeryHistory === data.surgeryHistory &&
    matchedScenario.rawNote === data.rawNote &&
    matchedScenario.weight === data.weight
  ) {
    return matchedScenario.generatedDraft;
  }

  return {
    reason: `[${data.consultPurpose}] ${data.mainDiagnosis} 환자의 감염 평가 및 표적 항생제 조절 자문 의뢰드립니다.`,
    history: `[임상 경과 요약]
상기 환자(${data.genderAge}, ${data.weight})는 ${data.admissionDate} 입원 후 '${data.mainDiagnosis}' 진단 하에 '${data.surgeryHistory || '보존적 치료'}' 적용 중이며, 다음과 같은 임상 소견이 확인되었습니다: ${data.rawNote}

${matchedScenario ? matchedScenario.generatedDraft.history.split('\n\n').slice(1).join('\n\n') : '• 활력징후·배양·항생제·염증수치(WBC/CRP/Lactate)·신기능(Cr/eGFR)·카테터·알레르기 정보: EMR 최신 데이터 연동 확인 필요'}`,
    specificRequests: `- '${data.consultPurpose}' 관련하여 환자 체중(${data.weight}) 및 신기능을 고려한 최적의 항생제 선택 및 용량·투여 간격 권고 부탁드립니다.\n- 주진단(${data.mainDiagnosis}) 및 영상·배양·카테터 상태를 종합한 감염원 조절 여부와 권장 총 치료 기간에 대해 고견 구합니다.`
  };
};

// 핵심 이상 소견 및 알레르기 텍스트를 강조 색상으로 하이라이트하는 헬퍼 함수
const highlightClinicalFindings = (text: string) => {
  const alertRegex =
    /(ESBL\(\+\)\s*Escherichia coli|ESBL\(\+\)|ESBL\s*양성|Methicillin-resistant Staphylococcus aureus \(MRSA\)|MRSA|AKI Stage \d[^)]*|AKI|지속 상승|급격 상승|Profound neutropenia|1\.42 ODI 양성|Halo sign|침습성 폐 아스페르길루스증\(Invasive pulmonary aspergillosis\) 강력 의심|BT 38\.\d℃|SpO2 93%\([^)]*\)|혈압 경계선 모니터링 필요|Sulfa 계열\(TMP-SMX\) 복용 시 전신 두드러기 병력 있음|Penicillin 계열\(Piperacillin\/Tazobactam\) 과거 투여 시 전신 홍반성 발진 병력 있음|2시간 지연 투여됨|내성:\s*[^/\n)]+)/g;

  const parts = text.split(alertRegex);
  return parts.map((part, idx) => {
    if (!part) return null;
    // 알레르기·지연 투여·내성 항목은 주황/앰버 톤으로 강조
    if (
      part.includes('두드러기') ||
      part.includes('발진') ||
      part.includes('지연 투여') ||
      part.startsWith('내성:')
    ) {
      return (
        <span
          key={idx}
          className="font-semibold text-amber-700 bg-amber-50 px-1 py-0.5 rounded"
        >
          {part}
        </span>
      );
    }
    // ESBL, MRSA, AKI, 염증 수치 급상승 등 핵심 이상 소견은 레드 톤으로 강조
    if (alertRegex.test(part)) {
      alertRegex.lastIndex = 0;
      return (
        <span
          key={idx}
          className="font-semibold text-red-600 bg-red-50 px-1 py-0.5 rounded"
        >
          {part}
        </span>
      );
    }
    return <React.Fragment key={idx}>{part}</React.Fragment>;
  });
};

// '2. 진단 및 주요 병력 요약' 본문의 항목 제목을 굵게(font-semibold) 렌더링하는 헬퍼 함수
const renderFormattedHistory = (historyText: string) => {
  return historyText.split('\n').map((line, index) => {
    const trimmed = line.trim();

    if (!trimmed) {
      return <div key={index} className="h-1.5" />;
    }

    // 대괄호 소제목 (예: [임상 경과 요약])
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      return (
        <div key={index} className="font-semibold text-slate-900">
          {trimmed}
        </div>
      );
    }

    // 불릿 항목 제목 (예: • 배양 및 항생제 감수성 (최근 14일):)
    if (trimmed.startsWith('•')) {
      const colonIdx = line.indexOf(':');
      if (colonIdx !== -1) {
        const heading = line.slice(0, colonIdx + 1);
        const rest = line.slice(colonIdx + 1);
        return (
          <div key={index} className="pt-1">
            <span className="font-semibold text-slate-900">{heading}</span>
            {rest && <span className="text-slate-700">{highlightClinicalFindings(rest)}</span>}
          </div>
        );
      }
      return (
        <div key={index} className="pt-1 font-semibold text-slate-900">
          {line}
        </div>
      );
    }

    // 일반 본문 및 하위 상세 항목
    return (
      <div key={index} className={line.startsWith('  ') ? 'pl-3 text-slate-700' : 'text-slate-700'}>
        {highlightClinicalFindings(trimmed)}
      </div>
    );
  });
};

export default function App() {
  // 현재 선택된 시나리오 인덱스 (0, 1, 2 순환)
  const [scenarioIndex, setScenarioIndex] = useState<number>(0);

  // 좌측 입력 폼 상태
  const [formData, setFormData] = useState<PatientScenario>(MOCK_SCENARIOS[0]);

  // UI 동작 상태 관리
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isDraftGenerated, setIsDraftGenerated] = useState<boolean>(true);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isSentSuccess, setIsSentSuccess] = useState<boolean>(false);

  // 우측 편집 가능한 초안 텍스트 상태
  const [draftContent, setDraftContent] = useState({
    reason: MOCK_SCENARIOS[0].generatedDraft.reason,
    history: MOCK_SCENARIOS[0].generatedDraft.history,
    specificRequests: MOCK_SCENARIOS[0].generatedDraft.specificRequests,
  });

  // 환자 이름 드롭다운 직접 변경 시 자동으로 ID와 기본정보 연동
  const handlePatientSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedName = e.target.value;
    const foundIndex = MOCK_SCENARIOS.findIndex((p) => p.name === selectedName);
    if (foundIndex !== -1) {
      const selectedScenario = MOCK_SCENARIOS[foundIndex];
      setScenarioIndex(foundIndex);
      setFormData(selectedScenario);
      setDraftContent(buildConsistentDraft(selectedScenario));
      setIsEditing(false);
    }
  };

  // 의뢰과 변경 시 해당 진료과 소속 교수진으로 자동 연동
  const handleFromDeptChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nextDept = e.target.value;
    const profList = FROM_DEPT_PROFESSORS[nextDept] || ['담당 교수'];
    setFormData({
      ...formData,
      fromDept: nextDept,
      fromProf: profList[0]
    });
  };

  // 1. [환자 시나리오 채우기] 버튼 클릭 시 3가지 케이스 순환(Rotate)
  const handleRotateScenario = () => {
    const nextIndex = (scenarioIndex + 1) % MOCK_SCENARIOS.length;
    const nextScenario = MOCK_SCENARIOS[nextIndex];
    setScenarioIndex(nextIndex);
    setFormData(nextScenario);
    setDraftContent(buildConsistentDraft(nextScenario));
    setIsEditing(false);
    setIsSentSuccess(false);
  };

  // 2. [초안 만들기] 버튼 클릭 시 스피너 회전 후 우측에 결과 렌더링
  const handleGenerateDraft = () => {
    setIsLoading(true);
    setIsEditing(false);
    setIsSentSuccess(false);

    setTimeout(() => {
      const consistentDraft = buildConsistentDraft(formData);
      setDraftContent(consistentDraft);
      setIsLoading(false);
      setIsDraftGenerated(true);
    }, 1100);
  };

  // 3. [내용 직접 수정] <-> [수정 완료] 토글
  const handleToggleEdit = () => {
    setIsEditing((prev) => !prev);
  };

  // 4. 모달에서 [YES] 클릭 시 전송 완료 처리
  const handleConfirmSend = () => {
    setIsModalOpen(false);
    setIsEditing(false);
    setIsSentSuccess(true);
    setTimeout(() => {
      setIsSentSuccess(false);
    }, 3500);
  };

  return (
    <div className="min-h-screen bg-[#f4f6f9] text-slate-800 flex flex-col font-sans">
      {/* 상단 타이틀 헤더 */}
      <header className="bg-white border-b border-slate-200 px-6 py-3.5 flex items-center justify-between shadow-xs sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 text-white p-2 rounded-lg shadow-xs">
            <Stethoscope className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-lg font-extrabold tracking-tight text-slate-900">
                SynapDoc 협진 의뢰 시스템
              </h1>
              <span className="text-xs font-bold px-2.5 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-full">
                EMR 연동 시뮬레이터
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              환자 기본 정보 자동 연동 및 AI 기반 타과 협진 의뢰서(Consultation Note) 생성 UI
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            현재 시나리오: 케이스 {scenarioIndex + 1} ({formData.fromDept} → {formData.toDept})
          </div>
        </div>
      </header>

      {/* 전송 성공 알림 배너 */}
      {isSentSuccess && (
        <div className="fixed top-16 right-6 z-50 bg-emerald-600 text-white px-5 py-3.5 rounded-xl shadow-xl flex items-center gap-3 animate-bounce">
          <CheckCircle2 className="w-5 h-5 shrink-0" />
          <div className="text-sm font-bold">
            [{formData.toDept} {formData.toProf} 교수]님께 협진 의뢰서 전송이 완료되었습니다!
          </div>
        </div>
      )}

      {/* 메인 좌우 1:1 Split-View 레이아웃 */}
      <main className="flex-1 max-w-[1560px] w-full mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
        
        {/* =========================================================
            좌측: 협진 요청 (입력 영역)
        ========================================================= */}
        <section className="bg-white rounded-xl border-2 border-slate-300 shadow-xs flex flex-col justify-between overflow-hidden">
          <div>
            {/* 좌측 상단 타이틀 바 */}
            <div className="bg-slate-50 border-b border-slate-200 px-5 py-3.5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ClipboardList className="w-5 h-5 text-blue-600" />
                <h2 className="text-base font-extrabold text-slate-900">
                  협진 요청 <span className="text-blue-600">(입력 영역)</span>
                </h2>
              </div>
              <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2.5 py-1 rounded-md border border-blue-100">
                환자 선택 시 ID 자동 입력
              </span>
            </div>

            {/* 폼 입력 본문 */}
            <div className="p-5 space-y-5">
              
              {/* 1. 환자 기본 정보 */}
              <div>
                <h3 className="text-xs font-extrabold text-slate-800 mb-2.5 flex items-center gap-1.5">
                  <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[11px]">1</span>
                  환자 기본 정보
                </h3>
                <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-200 space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    {/* 환자 이름 드롭다운 (순수 환자 성명만 표시) */}
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1">환자 이름</label>
                      <select
                        value={formData.name}
                        onChange={handlePatientSelect}
                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        {MOCK_SCENARIOS.map((p) => (
                          <option key={p.id} value={p.name}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* 환자 ID */}
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1">환자 ID</label>
                      <input
                        type="text"
                        value={formData.id}
                        readOnly
                        className="w-full px-3 py-2 bg-slate-200/80 border border-slate-300 rounded-md text-sm font-mono font-semibold text-slate-600 cursor-not-allowed"
                      />
                    </div>
                  </div>

                  {/* 성별/나이, 체중, 병동, 입원일자 */}
                  <div className="grid grid-cols-12 gap-2.5">
                    <div className="col-span-3">
                      <label className="block text-xs font-bold text-slate-600 mb-1">성별/나이</label>
                      <input
                        type="text"
                        value={formData.genderAge}
                        onChange={(e) => setFormData({ ...formData, genderAge: e.target.value })}
                        className="w-full px-2.5 py-1.5 bg-white border border-slate-300 rounded-md text-sm font-semibold text-slate-800 text-center"
                      />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-xs font-bold text-slate-600 mb-1">체중</label>
                      <input
                        type="text"
                        value={formData.weight}
                        onChange={(e) => setFormData({ ...formData, weight: e.target.value })}
                        className="w-full px-2 py-1.5 bg-white border border-slate-300 rounded-md text-sm font-semibold text-slate-800 text-center"
                      />
                    </div>
                    <div className="col-span-3">
                      <label className="block text-xs font-bold text-slate-600 mb-1">병동</label>
                      <input
                        type="text"
                        value={formData.ward}
                        onChange={(e) => setFormData({ ...formData, ward: e.target.value })}
                        className="w-full px-2.5 py-1.5 bg-white border border-slate-300 rounded-md text-sm font-semibold text-slate-800 text-center"
                      />
                    </div>
                    <div className="col-span-4">
                      <label className="block text-xs font-bold text-slate-600 mb-1">입원일자</label>
                      <input
                        type="text"
                        value={formData.admissionDate}
                        onChange={(e) => setFormData({ ...formData, admissionDate: e.target.value })}
                        className="w-full px-2.5 py-1.5 bg-white border border-slate-300 rounded-md text-sm font-semibold text-slate-800 text-center"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* 2. 주진단 및 현재 경과/수술력 */}
              <div className="space-y-3">
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <h3 className="text-xs font-extrabold text-slate-800 flex items-center gap-1.5">
                      <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[11px]">2</span>
                      주진단 및 수술/치료 이력
                    </h3>
                    <span className="text-[11px] font-bold text-blue-600 flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" /> 수술/치료와 질병 간 의학적 일관성 연동
                    </span>
                  </div>
                  <div className="space-y-2.5 bg-slate-50 p-3.5 rounded-lg border border-slate-200">
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1">주진단명 (ICD-10)</label>
                      <input
                        type="text"
                        value={formData.mainDiagnosis}
                        onChange={(e) => setFormData({ ...formData, mainDiagnosis: e.target.value })}
                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm font-bold text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                      />
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="block text-xs font-bold text-slate-600">현재 경과 / 수술력 (선택 입력)</label>
                        <span className="text-[11px] text-slate-500">수술 예정일 또는 시행된 수술명/치료 요약</span>
                      </div>
                      <input
                        type="text"
                        value={formData.surgeryHistory}
                        onChange={(e) => setFormData({ ...formData, surgeryHistory: e.target.value })}
                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm font-semibold text-slate-800 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* 3. 협진 의뢰 목적 (사유) - 입력 피로도 감소를 위해 별도 분리 */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-extrabold text-slate-800 flex items-center gap-1.5">
                    <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[11px]">3</span>
                    협진 의뢰 목적 (사유)
                  </h3>
                  <span className="text-[11px] font-bold text-blue-600 flex items-center gap-1">
                    <Target className="w-3.5 h-3.5" /> 원클릭 카테고리 선택 지원
                  </span>
                </div>
                <div className="bg-blue-50/50 p-3.5 rounded-lg border border-blue-200 space-y-2.5">
                  <div className="flex flex-wrap gap-1.5">
                    {CONSULT_PURPOSE_CATEGORIES.map((category) => {
                      const isSelected = formData.consultPurpose === category;
                      return (
                        <button
                          key={category}
                          type="button"
                          onClick={() => setFormData({ ...formData, consultPurpose: category })}
                          className={`px-2.5 py-1.5 rounded-md text-xs font-bold transition-all cursor-pointer border ${
                            isSelected
                              ? 'bg-blue-600 text-white border-blue-700 shadow-xs'
                              : 'bg-white text-slate-700 border-slate-300 hover:bg-blue-50 hover:border-blue-300'
                          }`}
                        >
                          {category}
                        </button>
                      );
                    })}
                  </div>
                  <div>
                    <input
                      type="text"
                      value={formData.consultPurpose}
                      onChange={(e) => setFormData({ ...formData, consultPurpose: e.target.value })}
                      placeholder="상단 카테고리를 선택하거나 협진 목적을 간단히 입력하세요"
                      className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-md text-sm font-bold text-blue-900 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              {/* 4. 협진 의뢰 대상 진료과 및 일정 */}
              <div>
                <h3 className="text-xs font-extrabold text-slate-800 mb-2 flex items-center gap-1.5">
                  <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[11px]">4</span>
                  협진 의뢰 대상 진료과 및 일정
                </h3>
                <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-200 space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1">의뢰과 (요청 진료과)</label>
                      <select
                        value={formData.fromDept}
                        onChange={handleFromDeptChange}
                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm font-semibold text-slate-800 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                      >
                        {Object.keys(FROM_DEPT_PROFESSORS).map((dept) => (
                          <option key={dept} value={dept}>
                            {dept}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 mb-1">의뢰 교수</label>
                      <select
                        value={formData.fromProf}
                        onChange={(e) => setFormData({ ...formData, fromProf: e.target.value })}
                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm font-semibold text-slate-800 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                      >
                        {(FROM_DEPT_PROFESSORS[formData.fromDept] || [formData.fromProf]).map((prof) => (
                          <option key={prof} value={prof}>
                            {prof} 교수
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-bold text-blue-800 mb-1 flex items-center gap-1">
                        <Building2 className="w-3.5 h-3.5" /> 피의뢰과 (감염내과 고정)
                      </label>
                      <input
                        type="text"
                        value="감염내과"
                        readOnly
                        aria-label="피의뢰과"
                        className="w-full px-3 py-2 bg-blue-50 border-2 border-blue-400 rounded-md text-sm font-extrabold text-blue-900 cursor-not-allowed focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-blue-800 mb-1">피의뢰 교수 (감염내과 전문의)</label>
                      <select
                        value={formData.toProf}
                        onChange={(e) => setFormData({ ...formData, toDept: '감염내과', toProf: e.target.value })}
                        className="w-full px-3 py-2 bg-white border-2 border-blue-400 rounded-md text-sm font-bold text-blue-900 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                      >
                        {INFECTIOUS_DISEASE_PROFESSORS.map((prof) => (
                          <option key={prof} value={prof}>
                            {prof} 교수
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-12 gap-3 pt-1">
                    {/* 응급도 */}
                    <div className="col-span-6">
                      <label className="block text-xs font-bold text-slate-600 mb-1">응급도</label>
                      <div className="grid grid-cols-2 gap-1.5">
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, urgency: '긴급(STAT)' })}
                          className={`py-2 px-2 rounded-md text-xs font-extrabold border transition-all ${
                            formData.urgency === '긴급(STAT)'
                              ? 'bg-blue-600 text-white border-blue-700 shadow-xs'
                              : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-100'
                          }`}
                        >
                          긴급(STAT)
                        </button>
                        <button
                          type="button"
                          onClick={() => setFormData({ ...formData, urgency: '정규(Routine)' })}
                          className={`py-2 px-2 rounded-md text-xs font-extrabold border transition-all ${
                            formData.urgency === '정규(Routine)'
                              ? 'bg-blue-600 text-white border-blue-700 shadow-xs'
                              : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-100'
                          }`}
                        >
                          정규(Routine)
                        </button>
                      </div>
                    </div>

                    {/* 협진 요청 시점 */}
                    <div className="col-span-6">
                      <label className="block text-xs font-bold text-slate-600 mb-1">협진 요청 시점</label>
                      <input
                        type="text"
                        value={formData.requestTime}
                        onChange={(e) => setFormData({ ...formData, requestTime: e.target.value })}
                        className="w-full px-3 py-2 bg-white border border-slate-300 rounded-md text-sm font-semibold text-slate-800"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* 5. 비정형 임상 경과 메모 (자유 기술) */}
              <div>
                <h3 className="text-xs font-extrabold text-slate-800 mb-2 flex items-center gap-1.5">
                  <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[11px]">5</span>
                  비정형 임상 경과 및 상세 메모 (자유 기술)
                </h3>
                <textarea
                  rows={3}
                  value={formData.rawNote}
                  onChange={(e) => setFormData({ ...formData, rawNote: e.target.value })}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-md text-sm font-medium text-slate-800 leading-relaxed focus:bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none"
                />
              </div>
            </div>
          </div>

          {/* 좌측 하단 버튼 바 */}
          <div className="bg-slate-100 border-t border-slate-200 p-4 grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={handleRotateScenario}
              className="py-3 px-4 bg-slate-200 hover:bg-slate-300 active:scale-[0.99] text-slate-800 font-extrabold text-sm rounded-lg border border-slate-400 shadow-xs flex items-center justify-center gap-2 transition-all cursor-pointer"
            >
              <RefreshCw className="w-4 h-4 text-slate-700" />
              <span>[환자 시나리오 채우기]</span>
            </button>

            <button
              type="button"
              onClick={handleGenerateDraft}
              disabled={isLoading}
              className="py-3 px-4 bg-[#3b5998] hover:bg-blue-700 active:scale-[0.99] disabled:bg-blue-400 text-white font-extrabold text-sm rounded-lg shadow-xs flex items-center justify-center gap-2 transition-all cursor-pointer"
            >
              <Sparkles className="w-4 h-4" />
              <span>{isLoading ? '초안 생성 중...' : '[초안 만들기]'}</span>
            </button>
          </div>
        </section>

        {/* =========================================================
            우측: 의뢰서 미리보기 (결과 영역)
        ========================================================= */}
        <section className="bg-white rounded-xl border-2 border-slate-300 shadow-xs flex flex-col justify-between overflow-hidden relative">
          <div>
            {/* 우측 상단 타이틀 바 */}
            <div className="bg-slate-50 border-b border-slate-200 px-5 py-3.5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-blue-600" />
                <h2 className="text-base font-extrabold text-slate-900">
                  의뢰서 미리보기 <span className="text-slate-600">(결과 영역)</span>
                </h2>
              </div>
              {isEditing && (
                <span className="text-xs font-extrabold px-2.5 py-1 bg-amber-100 text-amber-800 border border-amber-300 rounded-md flex items-center gap-1">
                  <Edit3 className="w-3.5 h-3.5" /> 편집 모드 활성화 중
                </span>
              )}
            </div>

            {/* 우측 본문 영역 */}
            {isLoading ? (
              <div className="p-16 flex flex-col items-center justify-center text-center min-h-[540px]">
                <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mb-4"></div>
                <h3 className="text-base font-extrabold text-slate-800 mb-1">
                  협진 의뢰서(초안)를 생성하고 있습니다...
                </h3>
                <p className="text-xs text-slate-500">
                  환자 요약 테이블 매핑 및 3단 의뢰 본문 구조화 진행 중
                </p>
              </div>
            ) : !isDraftGenerated ? (
              <div className="p-16 flex flex-col items-center justify-center text-center min-h-[540px] text-slate-400">
                <Activity className="w-12 h-12 mb-3 stroke-1" />
                <p className="text-sm font-bold text-slate-600">생성된 의뢰서 초안이 없습니다.</p>
                <p className="text-xs mt-1">좌측 하단의 [초안 만들기] 버튼을 눌러주세요.</p>
              </div>
            ) : (
              <div className="p-5 space-y-5">
                <div>
                  <h3 className="text-lg font-extrabold text-slate-900 mb-3">협진 의뢰서 (초안)</h3>
                  <p className="text-xs font-extrabold text-slate-700 mb-2">
                    협진 의뢰서 상단 요약 정보
                  </p>

                  {/* 상단 요약 정보 테이블 (순수 환자 성명 및 협진 의뢰 목적 반영) */}
                  <div className="border-2 border-slate-400 rounded-lg overflow-hidden text-xs bg-white">
                    <table className="w-full border-collapse">
                      <tbody>
                        {/* 1행 */}
                        <tr className="border-b border-slate-300 bg-slate-50">
                          <td className="px-3 py-2.5 font-bold text-slate-800 border-r border-slate-300 w-[55%]">
                            의뢰 일시: <span className="font-semibold">{formData.requestTime}</span>
                          </td>
                          <td className="px-3 py-2.5 font-bold text-slate-800">
                            응급도:{' '}
                            <span className={formData.urgency === '긴급(STAT)' ? 'text-red-600 font-extrabold' : 'text-blue-600 font-extrabold'}>
                              {formData.urgency}
                            </span>
                          </td>
                        </tr>
                        {/* 2행: 환자 이름에 불필요한 진료과 이동 경로 없이 순수 성명 및 체중 표시 */}
                        <tr className="border-b border-slate-300">
                          <td className="px-3 py-2.5 font-bold text-slate-800 border-r border-slate-300">
                            환자 이름: <span className="text-slate-900 font-extrabold">{formData.name}</span> ({formData.id}) / {formData.genderAge}세 / {formData.weight}
                          </td>
                          <td className="p-0">
                            <div className="grid grid-cols-12 divide-x divide-slate-300">
                              <div className="col-span-5 px-2.5 py-2.5 font-bold text-slate-800">
                                병동: {formData.ward}
                              </div>
                              <div className="col-span-7 px-2.5 py-2.5 font-bold text-slate-800">
                                입원일: {formData.admissionDate}
                              </div>
                            </div>
                          </td>
                        </tr>
                        {/* 3행 */}
                        <tr className="border-b border-slate-300">
                          <td className="px-3 py-2.5 font-bold text-slate-800 border-r border-slate-300">
                            의뢰과/의뢰교수: {formData.fromDept} / {formData.fromProf} 교수
                          </td>
                          <td className="px-3 py-2.5 font-bold text-blue-900 bg-blue-50/50">
                            피의뢰과/피의뢰교수: 감염내과 / {formData.toProf} 교수
                          </td>
                        </tr>
                        {/* 4행 */}
                        <tr className="border-b border-slate-300">
                          <td colSpan={2} className="px-3 py-2.5 font-bold text-slate-800">
                            주진단: {formData.mainDiagnosis}
                          </td>
                        </tr>
                        {/* 5행 */}
                        <tr className="border-b border-slate-300 bg-slate-50/60">
                          <td colSpan={2} className="px-3 py-2.5 font-bold text-slate-800">
                            현재 경과/수술력: {formData.surgeryHistory}
                          </td>
                        </tr>
                        {/* 6행: 분리된 협진 의뢰 목적 명시 */}
                        <tr className="bg-blue-50/30">
                          <td colSpan={2} className="px-3 py-2.5 font-bold text-blue-900">
                            협진 의뢰 목적: {formData.consultPurpose}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* 하단 3단 카드 영역 */}
                <div className="border-2 border-slate-400 rounded-xl p-4 bg-slate-50/50 space-y-4">
                  {/* 1. 의뢰 사유 */}
                  <div>
                    <h4 className="text-sm font-extrabold text-slate-900 mb-1.5 flex items-center justify-between">
                      <span>1. 의뢰 사유</span>
                      {isEditing && <span className="text-[11px] text-amber-700 font-bold">수정 중</span>}
                    </h4>
                    {isEditing ? (
                      <textarea
                        rows={3}
                        value={draftContent.reason}
                        onChange={(e) => setDraftContent({ ...draftContent, reason: e.target.value })}
                        className="w-full p-2.5 text-sm font-medium text-slate-900 bg-amber-50/60 border-2 border-amber-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    ) : (
                      <p className="text-sm font-medium text-slate-800 bg-white p-3 rounded-lg border border-slate-200 leading-relaxed whitespace-pre-line">
                        {draftContent.reason}
                      </p>
                    )}
                  </div>

                  {/* 2. 진단 및 주요 병력 요약 */}
                  <div>
                    <h4 className="text-sm font-extrabold text-slate-900 mb-1.5 flex items-center justify-between">
                      <span>2. 진단 및 주요 병력 요약</span>
                      {isEditing && <span className="text-[11px] text-amber-700 font-bold">수정 중</span>}
                    </h4>
                    {isEditing ? (
                      <textarea
                        rows={12}
                        value={draftContent.history}
                        onChange={(e) => setDraftContent({ ...draftContent, history: e.target.value })}
                        className="w-full p-2.5 text-sm font-medium text-slate-900 bg-amber-50/60 border-2 border-amber-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 leading-relaxed"
                      />
                    ) : (
                      <div className="text-sm text-slate-700 bg-white p-3.5 rounded-lg border border-slate-200 leading-relaxed space-y-1">
                        {renderFormattedHistory(draftContent.history)}
                      </div>
                    )}
                  </div>

                  {/* 3. 구체적 요청 사항 */}
                  <div>
                    <h4 className="text-sm font-extrabold text-slate-900 mb-1.5 flex items-center justify-between">
                      <span>3. 구체적 요청 사항</span>
                      {isEditing && <span className="text-[11px] text-amber-700 font-bold">수정 중</span>}
                    </h4>
                    {isEditing ? (
                      <textarea
                        rows={3}
                        value={draftContent.specificRequests}
                        onChange={(e) => setDraftContent({ ...draftContent, specificRequests: e.target.value })}
                        className="w-full p-2.5 text-sm font-medium text-slate-900 bg-amber-50/60 border-2 border-amber-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    ) : (
                      <p className="text-sm font-medium text-slate-800 bg-white p-3 rounded-lg border border-slate-200 leading-relaxed whitespace-pre-line">
                        {draftContent.specificRequests}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 우측 하단 버튼 바 */}
          <div className="bg-slate-100 border-t border-slate-200 p-4 grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={handleToggleEdit}
              disabled={isLoading || !isDraftGenerated}
              className={`py-3 px-4 font-extrabold text-sm rounded-lg border shadow-xs flex items-center justify-center gap-2 transition-all cursor-pointer ${
                isEditing
                  ? 'bg-amber-500 hover:bg-amber-600 text-white border-amber-600'
                  : 'bg-slate-200 hover:bg-slate-300 text-slate-800 border-slate-400'
              } disabled:opacity-50`}
            >
              {isEditing ? (
                <>
                  <Check className="w-4 h-4" />
                  <span>[수정 완료]</span>
                </>
              ) : (
                <>
                  <Edit3 className="w-4 h-4 text-slate-700" />
                  <span>[내용 직접 수정]</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => setIsModalOpen(true)}
              disabled={isLoading || !isDraftGenerated}
              className="py-3 px-4 bg-[#3b5998] hover:bg-blue-700 active:scale-[0.99] disabled:bg-slate-300 text-white font-extrabold text-sm rounded-lg shadow-xs flex items-center justify-center gap-2 transition-all cursor-pointer"
            >
              <Send className="w-4 h-4" />
              <span>[의뢰서 확정 및 전송]</span>
            </button>
          </div>

          {/* =========================================================
              와이어프레임 우측 하단 말풍선/모달 팝업: "이대로 진행하시겠습니까? [YES] or [NO]"
          ========================================================= */}
          {isModalOpen && (
            <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-[1px] flex items-center justify-center p-4">
              <div className="bg-white border-2 border-slate-800 rounded-2xl max-w-sm w-full p-6 shadow-2xl text-center animate-in fade-in zoom-in-95 duration-150">
                <div className="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mx-auto mb-3">
                  <AlertCircle className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-extrabold text-slate-900 mb-2">
                  이대로 진행하시겠습니까?
                </h3>
                <p className="text-xs text-slate-500 mb-5">
                  대상: {formData.name} ({formData.id}) → {formData.toDept} {formData.toProf} 교수
                </p>

                <div className="flex items-center justify-center gap-3 font-extrabold text-base">
                  <button
                    type="button"
                    onClick={handleConfirmSend}
                    className="flex-1 py-2.5 px-4 bg-blue-50 hover:bg-blue-600 text-blue-700 hover:text-white border-2 border-blue-600 rounded-xl transition-colors cursor-pointer"
                  >
                    [ YES ]
                  </button>
                  <span className="text-slate-400 font-bold text-sm">or</span>
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="flex-1 py-2.5 px-4 bg-red-50 hover:bg-red-600 text-red-600 hover:text-white border-2 border-red-500 rounded-xl transition-colors cursor-pointer"
                  >
                    [ NO ]
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}