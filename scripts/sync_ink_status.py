"""
잉크 초안 PR의 상태를 접수함(Supabase questions)에 되반영한다. LLM 호출
없음 -- PR 이벤트(열림/닫힘)에서 파일의 `question_id:` 프런트매터를 읽어
상태만 옮긴다. 초안 작성(Max 세션)과 상태 기록(이 스크립트)을 분리해서,
초안을 쓰는 클로드 코드 세션은 Supabase 자격증명을 몰라도 되게 한다.
정본 설계: docs/질문하기_파이프라인.md.

필요한 Secrets: SUPABASE_URL, SUPABASE_SERVICE_KEY (기존, 새로 등록할 것 없음).
환경변수(워크플로가 채움): PR_ACTION, PR_NUMBER, PR_MERGED, PR_HEAD_REF,
  CHANGED_FILES(개행 구분 상대 경로 목록)
"""
import functools
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
print = functools.partial(print, flush=True)

ROOT = Path(__file__).resolve().parent.parent
FM_ID = re.compile(r"^question_id:\s*(\S+)\s*$", re.MULTILINE)
FM_PUBLISHED = re.compile(r"^published:\s*(true|false)\s*$", re.MULTILINE)


def find_ink_file() -> Path | None:
    for rel in os.environ.get("CHANGED_FILES", "").splitlines():
        rel = rel.strip()
        if not rel.startswith("log_assets/markdown/") or not rel.endswith(".md"):
            continue
        path = ROOT / rel
        if path.exists() and FM_ID.search(path.read_text(encoding="utf-8")):
            return path
    return None


def main() -> None:
    path = find_ink_file()
    if not path:
        print("question_id 있는 잉크 초안 파일 없음 -- 건너뜀")
        return

    text = path.read_text(encoding="utf-8")
    qid = FM_ID.search(text).group(1)
    action = os.environ["PR_ACTION"]
    pr_number = os.environ.get("PR_NUMBER")
    merged = os.environ.get("PR_MERGED") == "true"

    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    if action in ("opened", "synchronize", "reopened"):
        sb.table("questions").update({
            "status": "초안",
            "draft_pr": int(pr_number) if pr_number else None,
            "draft_branch": os.environ.get("PR_HEAD_REF"),
            "draft_path": str(path.relative_to(ROOT)),
        }).eq("id", qid).execute()
        print(f"[{qid[:8]}] 초안 (PR #{pr_number})")
        return

    if action == "closed":
        if merged:
            m = FM_PUBLISHED.search(text)
            if m and m.group(1) == "true":
                sb.table("questions").update({"status": "발행"}).eq("id", qid).execute()
                print(f"[{qid[:8]}] 발행")
            else:
                print(f"[{qid[:8]}] 병합됐지만 published:false -- 상태 유지")
        else:
            sb.table("questions").update({"status": "반려"}).eq("id", qid).execute()
            print(f"[{qid[:8]}] 반려 (PR 닫힘, 병합 안 됨)")


if __name__ == "__main__":
    main()
