"""PreToolUse 훅(2026-10-05 탐, 사장님 지시 "도구 관문 훅부터"): 큰 업무 md(업무대장·진행상황)를 통째로 읽거나 grep하려 하면 멈추고 운영 상태 DB 명령으로 안내한다.
이유: "DB에서 읽어라"가 문서 규칙뿐이라 핏이 하이 뒤에 md를 grep으로 읽었다(10/5). 문서 규칙은 세션이 바뀌면 빠지므로 도구 관문에 둔다(CLAUDE.md id:4e7b).
대상 파일: *_업무대장.md, 진행상황.md. DB 정본: 표 tasks(업무대장+인수인계), 읽기 명령 scripts/ops/opsdb.py, 하이 브리핑 scripts/ops/session_brief.py.
통과(작은 읽기): Read에 limit가 150 이하, sed -n 줄 범위, head/tail, wc, git 명령, 편집용 python 스크립트(읽기 동사가 없는 것).
예외: 명령/요청 문구에 "[DB 불가: 이유]"를 적으면 통과(DB가 뒤처졌거나 방금 바뀐 건을 확인할 때). 기록: C:/work/_ops/db_gate_log.jsonl (막힘·통과 사유, 도입 효과 측정용).
"""
import json
import re
import sys
import time

try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

TARGET = re.compile(r"(업무대장|진행상황)[^\s'\"/\\]*\.md|_업무대장\.md", re.I)
READ_VERB = re.compile(r"(?<![\w-])(cat|grep|egrep|rg|Select-String|Get-Content)(?![\w-])", re.I)
SAFE_VERB = re.compile(r"(?<![\w-])(git|sed\s+-n|head|tail|wc|ls|Test-Path|stat)(?![\w-])", re.I)
LOG = r"C:\work\_ops\db_gate_log.jsonl"

MSG = ("[DB 관문] 큰 업무 문서({f})를 통째로 읽거나 grep하지 않고 운영 상태 DB에서 읽습니다(읽는 양 94~99% 감소, 사장님 지시 10/5).\n"
       "· 내 인수인계·열린 건: python scripts/ops/session_brief.py <내이름>\n"
       "· 한 건: python scripts/ops/opsdb.py select tasks --where no=eq.N151 --cols title,raw --fmt json\n"
       "· 키워드로 찾기: python scripts/ops/opsdb.py select tasks --where \"title=ilike.*키워드*\" --cols no,title,status --fmt json\n"
       "· 문서 찾기: python scripts/ops/opsdb.py select docs --where \"title=ilike.*키워드*\" --cols path,title\n"
       "DB가 최대 1시간 뒤처질 수 있어 방금 바뀐 건을 확인해야 하면 명령/요청에 \"[DB 불가: 이유]\"를 적고 다시 하세요. 줄 범위가 정해진 작은 읽기(limit 150 이하, sed -n 'a,bp', head)는 통과합니다.")


def log(tool, decision, why):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%F %T"), "tool": tool, "decision": decision, "why": why[:120]}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0
    tool = data.get("tool_name")
    ti = data.get("tool_input") or {}
    if tool == "Read":
        path = str(ti.get("file_path", ""))
        m = TARGET.search(path)
        if not m:
            return 0
        lim = ti.get("limit")
        if isinstance(lim, int) and 0 < lim <= 150:
            log(tool, "pass", "작은 읽기 " + path)
            return 0
        log(tool, "block", path)
        sys.stderr.write(MSG.format(f=m.group(0)))
        return 2
    if tool == "Grep":
        blob = f"{ti.get('path', '')} {ti.get('glob', '')}"
        m = TARGET.search(blob)
        if not m:
            return 0
        log(tool, "block", blob)
        sys.stderr.write(MSG.format(f=m.group(0)))
        return 2
    if tool in ("Bash", "PowerShell"):
        cmd = str(ti.get("command", ""))
        m = TARGET.search(cmd)
        if not m:
            return 0
        if "[DB 불가:" in cmd:
            log(tool, "pass", "DB 불가 표시")
            return 0
        first = cmd.lstrip().split(None, 1)[0].lower() if cmd.strip() else ""
        if first in ("python", "python3", "py"):  # 스크립트·heredoc 편집은 통과(문장 속 단어 오탐 방지)
            log(tool, "pass", "python 스크립트")
            return 0
        if READ_VERB.search(cmd) and not first.startswith("git"):
            log(tool, "block", cmd)
            sys.stderr.write(MSG.format(f=m.group(0)))
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
