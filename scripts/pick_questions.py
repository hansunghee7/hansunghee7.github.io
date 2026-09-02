"""
"심플리파이어에게 질문하기" — 픽 처리.
정본 설계: docs/질문하기_파이프라인.md (단계 2, 계단 4).

propose_questions.py 가 만든 "질문 후보" 이슈에서 사장님이 체크한 줄(`- [x]`)을
접수함(Supabase questions)에 '대기'로 넣고, 그 줄 끝에 `✅ 접수됨` 표시를 붙여
두 번 넣지 않게 한다. pick-questions.yml 이 이슈 편집 이벤트마다 실행한다.

  ISSUE_NUMBER            처리할 이슈 번호 (워크플로가 넣어줌)
  GH_TOKEN                이슈 읽기·편집
  SUPABASE_URL / SUPABASE_SERVICE_KEY
"""
import functools
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
print = functools.partial(print, flush=True)

ROOT = Path(__file__).resolve().parent.parent
DONE = "✅ 접수됨"
CHECKED = re.compile(r"^- \[[xX]\] (.+?)\s*$")


def run(*args, capture=False, check=True):
    r = subprocess.run(args, cwd=ROOT, text=True, capture_output=capture, check=check)
    return (r.stdout or "").strip() if capture else ""


def main():
    n = os.environ["ISSUE_NUMBER"]
    body = json.loads(run("gh", "issue", "view", n, "--json", "body", capture=True))["body"]
    lines = body.split("\n")

    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    picked = 0
    for i, line in enumerate(lines):
        m = CHECKED.match(line)
        if not m or DONE in line:
            continue
        question = m.group(1).strip()
        sb.table("questions").insert({
            "question": question, "source": "pick", "email": None,
            "page": f"issue#{n}", "status": "대기",
        }).execute()
        lines[i] = f"{line}  {DONE}"
        picked += 1
        print(f"픽 → 대기: {question[:60]}")

    if picked:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("\n".join(lines)); path = f.name
        run("gh", "issue", "edit", n, "--body-file", path)
    print(f"처리 {picked}건")


if __name__ == "__main__":
    main()
