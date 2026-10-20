"""PreToolUse 훅(2026-10-20 탐, 사장님 지시): Write/Edit/MultiEdit로 옛 이름(saegim·새김)을 새로 늘리면 쓰기 전에 막는다.

왜: 제품 이름은 Carvit인데 에이전트들이 세션마다 정책을 잊고 옛 이름을 응용해 늘렸다(예: 'saegim dm' 신조어).
문서에만 "새로 쓰지 말라"고 적으면 다음 세션이 또 잊는다(CLAUDE.md id:4e7b). 쓰는 순간 도구 관문에서 막는다.
올릴 때 막는 CI 검사(scripts/check_saegim_names.py, 노트 PR 2494)와 짝이다: CI는 늦고 이 훅은 즉시다.

규칙: 이번 쓰기가 옛 이름이 든 낱말(예: saegim_x, saegim-dm)을 새로 만들면 막는다. 허용: ① 시스템 ID로 고정된 낱말
(저장소·GCP 프로젝트·확장 폴더·실행기 이름표 등, 바꿀 수 없거나 바꾸면 고객 설정이 끊김) ② 이미 파일에 있던 낱말을 그대로
유지하는 편집(줄이는 것은 항상 허용). 탈출구: 내용에 "[옛이름 허용: 이유]"를 적으면 통과하고 로그를 남긴다.
한계: Bash·PowerShell로 쓰는 파일은 못 막는다(CI가 잡는다). 대화 문장도 못 막는다.
"""
import json
import os
import re
import sys
import time

try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

OLD = re.compile(r"[A-Za-z0-9_.\-/가-힣]*(?:saegim|새김)[A-Za-z0-9_.\-가-힣]*", re.IGNORECASE)
# 시스템 ID로 고정된 낱말(docs/이름_정책.md 3층). 새 낱말을 여기 추가하려면 정책 문서도 같이 고친다.
ALLOWED = re.compile(
    r"^(?:.*/)?(?:simplifier-saegim|saegim-pass(?:-[a-z0-9-]+)?|saegim-mcp(?:-[a-z0-9]+)?|saegim-test|saegim-runner"
    r"|saegim-wt[a-z0-9-]*|note-saegim[a-z0-9-]*|jitu-saegim[a-z0-9-]*|wt-saegim[a-z0-9-]*|mcp__saegim__[a-z_]+"
    r"|saegim-gate(?:\.py|\.sh)?|saegim-outage(?:-notify)?(?:\.py|\.sh)?|saegim_gate|saegim_usage[a-z_.]*)$",
    re.IGNORECASE,
)
ESCAPE = "[옛이름 허용:"
LOG = os.environ.get("OLD_NAME_GATE_LOG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "old-name-gate.log"))


def words(text):
    return [w.strip(".,;:)(") for w in OLD.findall(text or "")]


def new_words(new_text, old_text):
    """새 글에 있고 옛 글엔 없는 옛 이름 낱말 중 허용 목록 밖의 것."""
    before = set(w.lower() for w in words(old_text))
    return sorted({w for w in words(new_text) if w.lower() not in before and not ALLOWED.match(w)})


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0
    tool = data.get("tool_name", "")
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ""
    if tool not in ("Write", "Edit", "MultiEdit") or not path:
        return 0
    pairs = []  # (새 글, 옛 글)
    if tool == "Write":
        old = ""
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                old = f.read()
        except OSError:
            pass
        pairs.append((ti.get("content", ""), old))
    elif tool == "Edit":
        pairs.append((ti.get("new_string", ""), ti.get("old_string", "")))
    else:
        for e in ti.get("edits") or []:
            pairs.append((e.get("new_string", ""), e.get("old_string", "")))
    bad = sorted({w for n, o in pairs for w in new_words(n, o)})
    if not bad:
        return 0
    if any(ESCAPE in n for n, _ in pairs):
        try:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%F %T')} {path} {bad}\n")
        except OSError:
            pass
        return 0
    print(
        "옛 이름(saegim·새김)을 새로 늘리는 쓰기라 막았습니다: " + ", ".join(bad[:6]) + "\n"
        "제품 이름은 Carvit(카빗)입니다. 같은 뜻의 carvit/카빗 낱말로 바꿔 쓰세요(예: 카빗DM). 정책: docs/이름_정책.md\n"
        "시스템 ID(저장소·GCP 프로젝트 등)를 그대로 가리켜야 하면 내용에 [옛이름 허용: 이유] 한 줄을 적으세요(로그가 남습니다).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
