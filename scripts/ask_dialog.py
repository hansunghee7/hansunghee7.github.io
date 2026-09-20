"""심플리파이어 다이얼로그(질문하기 Worker)를 호출해 답을 마크다운으로 붙여 쓴다.

사용: python scripts/ask_dialog.py "질문(500자 이내)" <출력.md>
- 답은 사장님 기존 글을 근거로 한 RAG 응답이다. 사장님 발언이 아니라 참고 자료다.
- 공유 시크릿은 insight-7b3e9f2c/ask.html의 ASK_SHARED_SECRET에서 실행할 때 읽는다.
  값을 다른 파일에 복사하지 않는다. 환경변수·시크릿 저장소를 뒤지지 않는다.
- User-Agent를 붙이지 않으면 Cloudflare가 403 error code 1010으로 막는다(2026-09-20 실측).
  브라우저 흉내가 아니라 정직한 식별자를 쓴다.
- Worker의 제미나이 키 사용량은 미확인이다. 글 한 편에 2~3회 이내로만 부른다.
"""
import datetime
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://simplifier-ask.simon-8be.workers.dev/"
ASK_HTML = Path(__file__).resolve().parent.parent / "insight-7b3e9f2c" / "ask.html"


def read_secret():
    m = re.search(r"ASK_SHARED_SECRET\s*=\s*['\"]([^'\"]+)['\"]", ASK_HTML.read_text(encoding="utf-8"))
    if not m:
        sys.exit("ask.html에서 ASK_SHARED_SECRET을 찾지 못했다")
    return m.group(1)


def ask(question):
    if len(question) > 500:
        sys.exit("질문은 500자 이내여야 한다(%d자)" % len(question))
    body = json.dumps({"question": question, "history": []}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "User-Agent": "simplifier-maya-desk/1.0 (internal)",
        "X-Ask-Secret": read_secret(),
    })
    out = {"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "question": question,
           "text": "", "sources": [], "log_id": None, "followups": [], "error": None}
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            event = None
            for raw in r:
                line = raw.decode("utf-8").rstrip("\n")
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    try:
                        data = json.loads(line[5:].strip())
                    except ValueError:
                        continue
                    if event == "chunk":
                        out["text"] += data.get("text", "")
                    elif event == "sources":
                        out["sources"] = data.get("sources", [])
                    elif event == "log_id":
                        out["log_id"] = data.get("id")
                    elif event == "followups":
                        out["followups"] = data.get("questions", [])
                    elif event == "error":
                        out["error"] = json.dumps(data, ensure_ascii=False)
    except urllib.error.HTTPError as e:
        out["error"] = "HTTP %d %s" % (e.code, e.read().decode("utf-8", "replace")[:200])
    except Exception as e:  # 네트워크 차단(클라우드 세션 정책 등)도 여기로 온다
        out["error"] = str(e)[:200]
    return out


def render(out):
    lines = ["## 질문 (%s, log_id %s)" % (out["time"], out["log_id"]), "", out["question"], "",
             "### 답변 (사장님 기존 글 기반 RAG 응답, 사장님 발언 아님)", "", out["text"] or "(답 없음)", "",
             "### 참고 자료"]
    lines += ["- %s (유사도 %.2f) %s" % (s["title"], s["similarity"], s["source_url"]) for s in out["sources"]]
    lines += ["", "### 후속 질문 제안"] + ["- " + q for q in out["followups"]]
    if out["error"]:
        lines += ["", "### 오류", out["error"]]
    return "\n".join(lines) + "\n\n"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    result = ask(sys.argv[1])
    with open(sys.argv[2], "a", encoding="utf-8", newline="\n") as f:
        f.write(render(result))
    print("답변 %d자, 참고 자료 %d건, log_id %s, 오류 %s" % (
        len(result["text"]), len(result["sources"]), result["log_id"], result["error"]))
