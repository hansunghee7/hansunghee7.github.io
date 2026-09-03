"""
"심플리파이어에게 질문하기" 접수함(Supabase questions)에서 '대기' 질문을 꺼내
저장소로 옮긴다(잡기: 상태를 '처리중'으로). 초안은 여기서 쓰지 않는다 --
클로드 API 종량 과금 경로를 드랍했으므로(2026-09-04), 초안은 Max 세션
(대화형 클로드 코드)이 _data/ink_queue/*.json을 읽고 직접 쓴다.
정본 설계: docs/질문하기_파이프라인.md.

이 스크립트는 LLM을 호출하지 않는다 -- Supabase 읽기/쓰기(service_role)만
쓰는 순수 데이터 이동이라 별도 API 키가 필요 없다. 이메일은 절대 옮기지
않는다(공개 저장소 원칙 1).

필요한 Secrets: SUPABASE_URL, SUPABASE_SERVICE_KEY (기존, 새로 등록할 것 없음).
"""
import functools
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
print = functools.partial(print, flush=True)

ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "_data" / "ink_queue"
MAX_ATTEMPTS = 3
MAX_CLAIM = int(os.environ.get("MAX_CLAIM", "5"))


def main() -> None:
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    rows = (
        sb.table("questions").select("id, question, page, attempts, source")
        .eq("status", "대기").lt("attempts", MAX_ATTEMPTS)
        .order("created_at").limit(MAX_CLAIM).execute().data
    )
    if not rows:
        print("대기 중인 질문 없음")
        return

    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    claimed = 0
    for row in rows:
        qid = row["id"]
        attempts = int(row.get("attempts") or 0) + 1
        # 잡기: '대기'일 때만 '처리중'으로 (compare-and-set). 겹친 실행 방지.
        ok = (
            sb.table("questions").update({"status": "처리중", "attempts": attempts, "error": None})
            .eq("id", qid).eq("status", "대기").execute().data
        )
        if not ok:
            continue
        (QUEUE_DIR / f"{qid}.json").write_text(
            json.dumps({
                "id": qid,
                "question": row["question"],
                "page": row.get("page"),
                "source": row.get("source") or "visitor",
                "attempts": attempts,
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        claimed += 1
        print(f"[{qid[:8]}] 대기 → 처리중, 큐 파일 기록")
    print(f"이번 실행 {claimed}건 옮김")


if __name__ == "__main__":
    main()
