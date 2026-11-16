"""터미널에서 시나리오를 돌려 본다.

    python run.py 1            # support/test/scenarios.json 의 1번 시나리오
    python run.py 1 --yes      # 승인 단계에서 묻지 않고 그대로 승인

단계별 로그가 출력되고, 8단계에서 멈춰 승인 여부를 묻는다.
"""
import json
import sys
import uuid
from pathlib import Path

from langgraph.types import Command

from graph import build_graph

SCENARIOS = Path(__file__).parent / "support" / "test" / "scenarios.json"


def show_review(review: dict) -> None:
    print("\n" + "=" * 78 + "\n초안 (승인 대기)\n" + "=" * 78)
    for sec in review["sections"]:
        print(f"\n■ {sec['title']}")
        for s in sec["sentences"]:
            mark = {"일치": "✓", "의뢰의 기재": "△"}.get(s["verdict"], "✗")
            print(f"  {mark} [{s['sid']}] {s['text']}")
            print(f"       근거: {', '.join(s['evidence_ids']) or '-'}" + (f" | {s['reason']}" if s["reason"] else ""))
    print("\n■ 의뢰 질문")
    for i, q in enumerate(review["questions"]):
        tag = "제안" if q["origin"] == "agent" else "의뢰의"
        print(f"  {i}. ({tag}) {q['text']}" + (f"  ← {q['reason']}" if q.get("reason") else ""))
    print("\n■ 의뢰의 진술 교차 확인")
    for c in review["crosscheck"]:
        print(f"  [{c['verdict']}] {c['fact']}" + (f" — {c['note']}" if c.get("note") else ""))
    missing = [c["item"] for c in review["checklist"] if c["status"] == "none"]
    if missing:
        print("\n■ 기록에서 찾지 못한 항목: " + ", ".join(missing))
    if review["warnings"]:
        print(f"\n■ 검증 경고 {len(review['warnings'])}건 (재생성 {review['retry_count']}회 후에도 남음)")


def ask_decision(review: dict) -> dict:
    if input("\n승인할까요? (y/n) ").strip().lower() != "y":
        return {"approved": False}
    decision = {"approved": True, "rejected_questions": [], "added_questions": []}
    for i, q in enumerate(review["questions"]):
        if q["origin"] == "agent" and input(f"제안 질문 {i} 을 넣을까요? (y/n) ").strip().lower() != "y":
            decision["rejected_questions"].append(i)
    while (q := input("추가할 질문 (없으면 Enter): ").strip()):
        decision["added_questions"].append(q)
    decision["memo"] = input("추가 메모 (없으면 Enter): ").strip()
    decision["recipient"] = input("받는 교수 (없으면 Enter): ").strip()
    return decision


def main() -> None:
    key = sys.argv[1] if len(sys.argv) > 1 else "1"
    request = json.loads(SCENARIOS.read_text(encoding="utf-8"))[key]
    graph = build_graph()
    thread_id = str(uuid.uuid4())
    cfg = {"configurable": {"thread_id": thread_id}}

    result = graph.invoke({"request": request, "thread_id": thread_id}, cfg)
    if "__interrupt__" in result:
        review = result["__interrupt__"][0].value
        show_review(review)
        decision = {"approved": True} if "--yes" in sys.argv else ask_decision(review)
        result = graph.invoke(Command(resume=decision), cfg)

    print("\n" + "=" * 78 + f"\n결과: {result.get('status')}\n" + "=" * 78)
    if result.get("mail"):
        print(f"제목: {result['mail']['subject']}\n받는 사람: {result['mail']['to']}\n\n{result['mail']['body']}")
        print("\n" + "-" * 78 + "\n" + result["document"]["text"])
        print("\n발송 결과:", result["mail"]["result"])


if __name__ == "__main__":
    main()
