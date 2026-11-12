"""협진 의뢰서 HTML 렌더링 (고정 템플릿 CONSULT_REQ_v1)."""
from __future__ import annotations

from jinja2 import Template

SERVICE_KO = {"SURG": "외과", "MED": "내과", "ORTHO": "정형외과", "OMED": "혈액종양내과", "CSURG": "흉부외과"}
UNIT_KO = {"Surgery": "외과 병동", "Medicine": "내과 병동", "PACU": "회복실"}

HTML = Template("""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>협진 의뢰서 {{ h.consult_id }}</title>
<style>
 body{font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",sans-serif;max-width:820px;margin:32px auto;color:#1d2433;line-height:1.6}
 h1{font-size:22px;margin:0 0 4px} .sub{color:#667085;font-size:13px;margin-bottom:18px}
 table.hdr{width:100%;border-collapse:collapse;font-size:14px;margin-bottom:22px}
 table.hdr th{background:#f2f4f7;text-align:left;width:150px;padding:7px 10px;border:1px solid #d0d5dd;font-weight:500}
 table.hdr td{padding:7px 10px;border:1px solid #d0d5dd}
 h2{font-size:16px;border-bottom:2px solid #1d2433;padding-bottom:4px;margin:22px 0 8px}
 p.s{margin:4px 0} ol{margin:4px 0 4px 20px;padding:0}
 .ev{font-size:11px;color:#98a2b3;margin-left:4px;white-space:nowrap}
 .urg{display:inline-block;padding:1px 8px;border-radius:4px;background:#fef3f2;color:#b42318;font-size:13px}
 .addendum{background:#fffaeb;border-left:3px solid #f79009;padding:8px 12px;margin-top:10px;font-size:14px}
 .reply{border:1px solid #1d2433;padding:12px 16px;margin-top:28px}
 .reply h2{margin-top:4px} .sign{text-align:right;margin-top:16px;font-size:14px}
 .badge{font-size:12px;color:#027a48;background:#ecfdf3;padding:1px 8px;border-radius:4px}
</style></head><body>
<h1>협진 의뢰서</h1>
<div class="sub">{{ h.consult_id }} · 초안 v{{ draft.version }} · SynapDoc 생성 후 의뢰의 승인
 {% if verification and verification.passed %}<span class="badge">근거 대조 통과 {{ verification.n_supported }}/{{ verification.n_sentences }}문장</span>{% endif %}</div>
<table class="hdr">
 <tr><th>의뢰일시</th><td>{{ h.consult_time }}</td><th>응급도</th><td><span class="urg">{{ h.urgency }}</span></td></tr>
 <tr><th>의뢰과 / 의뢰의</th><td>{{ h.requesting }}</td><th>피의뢰과 / 피의뢰의</th><td>{{ h.consulted }}</td></tr>
 <tr><th>환자</th><td>{{ h.patient }}</td><th>병동</th><td>{{ h.unit }}</td></tr>
 <tr><th>입원일</th><td>{{ h.admit }}</td><th>진료 서비스</th><td>{{ h.service }}</td></tr>
</table>
{% for sec in draft.sections %}
 <h2>{{ loop.index }}. {{ sec.title }}</h2>
 {% if sec.id == "S8" %}<ol>{% for s in sec.sentences %}<li>{{ s.text }}<span class="ev">[{{ s.evidence | map("evref") | join(", ") }}]</span></li>{% endfor %}</ol>
 {% else %}{% for s in sec.sentences %}<p class="s">{{ s.text }}<span class="ev">[{{ s.evidence | map("evref") | join(", ") }}]</span></p>{% endfor %}{% endif %}
{% endfor %}
{% if addendum %}<div class="addendum"><b>의뢰의 추가 메모</b> — {{ addendum }}</div>{% endif %}
<div class="sign">의뢰의: {{ h.requesting }} (전자서명)</div>
{% if reply %}
<div class="reply"><h2>회신</h2>
 <table class="hdr"><tr><th>회신일시</th><td>{{ reply.reply_time }}</td><th>회신의</th><td>{{ reply.replier }}</td></tr></table>
 <p><b>소견</b><br>{{ reply.impression }}</p>
 <p><b>권고</b></p><ol>{% for r in reply.recommendations %}<li>{{ r }}</li>{% endfor %}</ol>
 <p><b>추후 계획</b><br>{{ reply.follow_up }}</p>
 <p style="font-size:12px;color:#98a2b3">{{ reply.disclaimer }}</p>
</div>{% endif %}
</body></html>""", autoescape=True)


def _evref(ev):
    return ev["ref"] if isinstance(ev, dict) else ev


HTML.environment.filters["evref"] = _evref


def header(consult_id: str, request: dict, patient: dict, consultant: dict | None) -> dict:
    consulted = request["consulted_dept"]
    if consultant:
        consulted += f" / {consultant['name']} {consultant['title']}"
    patient_label = patient.get("display_name") or f"환자 {patient['subject_id']}"
    return {
        "consult_id": consult_id, "consult_time": request["consult_time"], "urgency": request["urgency"],
        "requesting": f"{request['requesting_dept']} / {request['requesting_doctor']} 교수",
        "consulted": consulted,
        "patient": f"{patient_label} / {patient['subject_id']} / {patient['gender']} / {patient['age']}세",
        "unit": UNIT_KO.get(patient["careunit"], patient["careunit"]),
        "admit": patient["admittime"][:10],
        "service": f"{SERVICE_KO.get(patient['service'], patient['service'])} ({patient['service']})",
    }


def render(h: dict, draft: dict, verification: dict | None = None, addendum: str = "", reply: dict | None = None) -> str:
    return HTML.render(h=h, draft=draft, verification=verification, addendum=addendum, reply=reply)
