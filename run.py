"""터미널에서 협진 1건을 끝까지 실행 (서버 없이, 실제 LLM).

  python run.py scenarios/patient1_request.json
  python run.py scenarios/patient1_request.json --reply scenarios/patient1_reply.json
"""
import argparse
import json
from pathlib import Path

from api import make_checkpointer
from graph import build_graph
from llm import make_model, make_prompt
from support import data, runner


def show(cid):
    v = runner.view(cid)
    print(f"\n── 상태: {v['status']}")
    for t in v["trace"]:
        print(f"  {t['step']:2d}. {t['tool']:16s} {json.dumps(t['args'], ensure_ascii=False)[:46]:48s} → {t['result']}")
    for r in v["verifications"]:
        print(f"  검증 v{r['draft_version']}: {'통과' if r['passed'] else '실패'} ({r['n_supported']}/{r['n_sentences']})")
        for i in r["issues"]:
            print(f"     - {i['type']:16s} {i['sid']:5s} {i['detail'][:90]}")
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("request_json")
    ap.add_argument("--reply", help="발송 후 붙일 회신 JSON (시연용)")
    a = ap.parse_args()

    graph = build_graph(make_model(), make_prompt(), checkpointer=make_checkpointer())
    cid = data.create_consult(json.loads(Path(a.request_json).read_text(encoding="utf-8")))
    print(f"의뢰 {cid} 시작 → support/consults/{cid}/")
    runner.start(graph, cid)
    v = show(cid)
    while v["status"] == "awaiting_approval":
        c = data.Consult(cid)
        (c.dir / "preview.html").write_text(data.document_html(c), encoding="utf-8")
        print(f"\n[승인 요청] {v['pending']['description']}\n  미리보기: {c.dir / 'preview.html'}")
        ans = input("  a=승인 / e=메모 추가 후 승인 / r=수정 요청 / c=취소 > ").strip().lower()
        d = ({"type": "approve"} if ans == "a" else
             {"type": "edit", "physician_addendum": input("  메모: ")} if ans == "e" else
             {"type": "reject", "message": input("  수정 요청 내용: ")} if ans == "r" else
             {"type": "cancel", "message": input("  취소 사유(선택): ")})
        runner.decide(graph, cid, d)
        v = show(cid)
    print(f"\n최종: {v['status']} — {v['final_message'] or v['error'] or ''}")
    if v["status"] == "sent" and a.reply:
        c = data.Consult(cid)
        c.set_reply(json.loads(Path(a.reply).read_text(encoding="utf-8")))
        c.set_status("replied")
        out = c.dir / "final_with_reply.html"
        out.write_text(data.document_html(c, with_reply=True), encoding="utf-8")
        print(f"회신 포함 의뢰서: {out}")


if __name__ == "__main__":
    main()
