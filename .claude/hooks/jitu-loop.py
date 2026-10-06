#!/usr/bin/env python3
"""지투 PO 성장 루프 훅(2026-10-06 사장님 지시: 보강 4·2·3·1을 1회성이 아니라 루프로, 문서와 훅에 적용).
방법은 docs/지투_PO_성장루프.md, 기록 도구는 scripts/ops/jitu_po.py. 이 훅은 "다음 바퀴가 돌게" 하는 세 가지 결정적 지점만 맡는다(키워드 해석은 하지 않는다, CLAUDE#4e7b).

모드(인자):
  prompt     UserPromptSubmit: 사장님이 "하이 지투"처럼 지투를 부르며 시작하면, 기한이 지난 루프 항목(열린 검사 공백, 7일 넘게 안 잰 지표,
             분류 안 한 고객 신호, 점검일 지난 예측)을 한 번에 보여 준다. 기한 지난 것이 없으면 아무것도 출력하지 않는다.
  pre-bash   PreToolUse(Bash): `gh pr checks ... | ...` 로 파이프를 붙인 채 같은 명령에서 `gh pr merge`를 하면 막는다(exit 2).
             이유: 파이프가 종료 코드를 가려 CI가 실패여도 병합이 실행된다(2026-10-06 지투, simplifier-saegim#558 사고, 보강 4의 첫 사례).
  stop       Stop: 지투 세션의 마지막 답변이 "정하실 것"에서 결정을 묻는데 ① 추천이 없거나 ② 답이 없을 때의 기본값·마감이 없으면 막는다(exit 2),
             또는 ③ 30분 넘게 전에 이미 물은 결정(ask 기록)과 거의 같은 질문이면 "한 줄 상태만"으로 막는다. "정하실 것: 없음"은 통과.
             사장님 지시 2026-10-06 ①②(탑티어 PM의 결정 요청: 추천+기본값+마감, 같은 결정을 되묻지 않기). stop_hook_active면 통과(무한 반복 방지).
  pre-send   PreToolUse(SendMessage): 지투가 노트에게 보내는 메시지를 본다(사장님 지시 2026-10-06). ① 새 일을 시키는 요청("...해 주세요/달라")에는 `[영역: 이름]`
             표지가 있고 그 영역에 "요구사항을 빠짐없이 모았다는 확신(req ready)"이 기록돼 있어야 한다. 반응이 빨라도 취합이 끝나기 전에는 전달하지 않는다.
             ② 노트의 개발을 멈추거나 바꾸라는 요청("멈춰/중단/스펙 변경/보류해 주세요" 등)에는 `[멈춤·변경 이득: 근거 한 줄]` 표지가 있어야 한다.
             ③ 사용자 문구·문안·표기·용어·메일 본문을 고쳐 달라는 요청은 지투 몫이다. 노트에게 보내려면 `[지투 직접 불가: 이유 12자 이상]` 표지가 있어야 한다
             (사장님 지시 2026-10-06: 습관적으로 문구 수정을 노트에게 넘겼다가 지투와 중복 작업이 생김).
             정보 전달·검토 결과·병합 알림처럼 일을 시키지 않는 메시지는 통과한다. 노트가 아닌 상대, 지투가 아닌 세션도 통과.
  post-bash  PostToolUse(Bash): 지투 세션에서 `gh pr merge`가 병합되면 "예측 한 줄과 점검일을 남겨라"(보강 1),
             `git revert`·`git reset --hard`·`gh pr revert`를 하면 "검사 공백을 남겨라"(보강 4)를 상기시킨다(막지 않는다).
지투 세션 판정: 트랜스크립트의 첫 사용자 발화에 '지투'가 있을 때(queue-gate.py와 같은 방식).
입력: stdin JSON(Claude Code 훅 규격). 검사기 오류는 통과한다.
"""
import json
import os
import re
import subprocess
import sys

try:
    sys.stderr.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "..", "..", "scripts", "ops", "jitu_po.py")
GREETING = re.compile(r"^\s*(하이|안녕)\s*[~～〜]?\s*(지투)\b")


def bare_cmd(cmd):
    """heredoc 본문과 따옴표 안 글자를 지운 사본(popup-gate.py와 같은 방식: jq 식 안의 | 를 파이프로 오인하지 않으려고)."""
    b = re.sub(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\b", " ", cmd, flags=re.S)
    b = re.sub(r"'[^']*'|\"(?:\\.|[^\"\\])*\"", "''", b)
    return re.sub(r"\d*>&\d+|&>>?", " ", b)  # `2>&1`의 &를 명령 연결로 오인하지 않게 지운다(실제 사고 명령이 `--watch 2>&1 | tail`이었다)


def unsafe_merge(cmd):
    """같은 명령에 gh pr merge가 있고, 그 앞의 gh pr checks 줄에 파이프(`|`, `||` 제외)가 붙어 있으면 True."""
    b = bare_cmd(cmd)
    if not re.search(r"\bgh\s+pr\s+merge\b", b):
        return False
    for m in re.finditer(r"\bgh\s+pr\s+checks\b([^\n;&]*)", b):
        if re.search(r"(?<!\|)\|(?!\|)", m.group(1)):
            return True
    return False


def first_user_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("type") != "user":
                    continue
                c = ev.get("message", {}).get("content", [])
                parts = [c] if isinstance(c, str) else [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
                joined = "\n".join(parts)
                if joined and "SYSTEM NOTIFICATION" not in joined and not joined.lstrip().startswith("<system-reminder>"):
                    return joined
    except Exception:
        return ""
    return ""


def is_jitu(data):
    if os.environ.get("JITU_LOOP_FORCE_JITU") == "1":
        return True
    return "지투" in first_user_text(data.get("transcript_path", "") or "")


def last_assistant_text(path):
    last = ""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("type") != "assistant":
                    continue
                for p in ev.get("message", {}).get("content", []) or []:
                    if isinstance(p, dict) and p.get("type") == "text" and p.get("text"):
                        last = p["text"]
    except Exception:
        return ""
    return last


DECIDE = re.compile(r"정하실 것\s*[:：]\s*(.+)")
NONE = re.compile(r"^\s*없음")
REC = re.compile(r"추천")
DEFAULT = re.compile(r"기본값|답이 없으면|답이 없을 때|마감")


def decision_block(text):
    """마지막 답변 속 '정하실 것'의 결정 부분(그 줄부터 다음 [표지] 줄 전까지)."""
    m = DECIDE.search(text)
    if not m or NONE.match(m.group(1)):
        return ""
    tail = text[m.start():]
    cut = re.search(r"\n\s*\[(?:사람 개입 필요|실행 대기|지금 돌고 있는 것|감시 중|해결 경로)", tail)
    return tail[:cut.start()] if cut else tail


def check_decision_text(text, asks, now_dt=None):
    """문제 목록(빈 목록이면 통과). asks=ask 기록 리스트."""
    blk = decision_block(text)
    if not blk:
        return []
    problems = []
    if not REC.search(blk):
        problems.append("추천이 없습니다(결정 요청에는 추천과 한 줄 이유를 같이 씁니다)")
    if not DEFAULT.search(blk):
        problems.append("답이 없을 때의 기본값 또는 마감이 없습니다(예: '답이 없으면 X로 두겠습니다')")
    import datetime as dt
    now = now_dt or dt.datetime.now()
    q = blk
    for r in asks:
        if r.get("answer"):
            continue
        try:
            created = dt.datetime.fromisoformat(r.get("created") or r["date"])
        except Exception:
            continue
        if (now - created).total_seconds() < 30 * 60:
            continue  # 방금 기록한 질문은 자기 자신이다
        if _similar(q, r["text"] + " " + r["rec"]):
            problems.append(f"이미 물은 결정 {r['id']}({r['date']})와 거의 같습니다. 답이 올 때까지 다시 묻지 말고 '{r['id']} 답 대기, 기본값은 {r['default'][:30]}' 한 줄 상태만 쓰세요")
            break
    return problems


def _similar(a, b, floor=0.6, minshared=4):
    ta = set(re.findall(r"[가-힣A-Za-z0-9]{2,}", a.lower()))
    tb = set(re.findall(r"[가-힣A-Za-z0-9]{2,}", b.lower()))
    if not ta or not tb:
        return False
    shared = len(ta & tb)
    return shared >= minshared and shared / min(len(ta), len(tb)) >= floor


def load_asks():
    p = os.path.join(os.environ.get("JITU_PO_DIR", "C:/work/_ops/jitu_po"), "asks.jsonl")
    rows = []
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    except Exception:
        return []
    return rows


AREA_TAG = re.compile(r"\[영역\s*[:：]\s*([^\]]+)\]")
GAIN_TAG = re.compile(r"\[멈춤[·.,]?\s*변경 이득\s*[:：]\s*([^\]]{12,})\]")
STOP_REQ = re.compile(r"(멈춰|멈추어|멈춤|중단|보류|롤백|되돌려|스펙[을를]? 바꿔|스펙 변경|계획[을를]? 바꿔|다시 만들어)[^.\n]{0,12}(주세요|달라|해 주|해주)")
OWNER_TAG = re.compile(r"\[지투 직접 불가\s*[:：]\s*([^\]]{12,})\]")
COPY_REQ = re.compile(
    r"(문구|문안|표기|용어|카피|메일 본문|안내 문장|번역 문장)[^.\n]{0,40}(고쳐|수정해|바꿔|정정해|통일해|넣어|반영해|적용해)\s*(주세요|달라|주시기)"
    r"|(고쳐|수정해|바꿔|정정해|통일해)\s*(주세요|달라|주시기)[^.\n]{0,20}(문구|문안|표기|용어)")
NEW_REQ = re.compile(r"(만들어|추가해|구현해|고쳐|수정해|진행해|착수해|올려|반영해|적용해|처리해|개선해|바꿔)\s*(주세요|달라|주시기)")


def send_problem(to, msg):
    """노트에게 보내는 메시지의 문제(없으면 빈 문자열)."""
    if "노트" not in str(to):
        return ""
    stop = STOP_REQ.search(msg)
    if stop:
        if not GAIN_TAG.search(msg):
            return ("노트의 개발을 멈추거나 바꾸라는 요청입니다. 지금 멈추고 바꾸는 편이 확실히 이득일 때만 보냅니다. 메시지에 "
                    "`[멈춤·변경 이득: 이득 근거를 12자 이상 한 줄(무엇을 얼마나 아끼거나 막는지)]` 표지를 넣으세요. "
                    "근거가 확실하지 않으면 보내지 말고 취합을 더 하세요(사장님 지시 2026-10-06).")
        return ""
    if COPY_REQ.search(msg) and not OWNER_TAG.search(msg):
        return ("사용자 문구·문안·표기·용어·메일 본문을 고치는 일은 지투가 직접 합니다(노트 몫은 서버 동작·DB·인증·배포·시험 실행기·성능). "
                "정말 지투가 직접 할 수 없는 이유가 있으면 메시지에 `[지투 직접 불가: 이유를 12자 이상 한 줄]` 표지를 넣으세요. "
                "먼저 확인: ① 사장님이 지투가 직접 하라고 했는가 ② 지투가 이미 직접 한 선례가 있는가(백로그 P12 지투 직접 구현, 가이드·FAQ·카피) "
                "③ 노트가 이미 같은 일을 하고 있지 않은가(사장님 지시 2026-10-06).")
    if NEW_REQ.search(msg):
        m = AREA_TAG.search(msg)
        if not m:
            return ("노트에게 새 일을 시키는 요청입니다. 해당 영역의 요구사항을 빠짐없이 모은 뒤에 보냅니다. `python scripts/ops/jitu_po.py req add --area 영역 --text ...`로 "
                    "모은 항목을 기록하고, 선행 작업·충돌·고객/DB 영향·확인 방법을 점검한 뒤 `req ready 영역 --note ...`로 확신을 기록하고, "
                    "메시지에 `[영역: 영역]` 표지를 넣으세요(사장님 지시 2026-10-06: 완벽히 취합하고 확신이 들 때 전달).")
        area = m.group(1).strip()
        try:
            r = subprocess.run([sys.executable, TOOL, "req", "check-send", area], capture_output=True, timeout=20,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            return ""
        if r.returncode != 0:
            return (r.stderr.decode("utf-8", "replace").strip() or f"영역 [{area}]은 아직 전달할 수 없습니다") + \
                   ". 빠진 것을 점검하고 `req ready` 뒤에 보내세요."
    return ""


def run_due():
    try:
        r = subprocess.run([sys.executable, TOOL, "due", "--quiet"], capture_output=True, timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout.decode("utf-8", "replace").strip()
    except Exception:
        return ""


def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0

    if mode == "prompt":
        if GREETING.match(str(data.get("prompt", ""))):
            out = run_due()
            if out:
                print(out)
        return 0

    if mode == "stop":
        if data.get("stop_hook_active") or not is_jitu(data):
            return 0
        text = last_assistant_text(data.get("transcript_path", "") or "")
        problems = check_decision_text(text, load_asks())
        if problems:
            sys.stderr.write("[결정 요청 관문] " + " / ".join(problems) + ". 고쳐서 다시 답하세요(보고 형식 8·9번, docs/사장님_보고_형식.md). "
                             "물은 결정은 `python scripts/ops/jitu_po.py ask add --text ... --rec ... --default ...`로 기록합니다.")
            return 2
        return 0

    if mode == "pre-send":
        ti = data.get("tool_input") or {}
        if not is_jitu(data):
            return 0
        problem = send_problem(ti.get("to", ""), str(ti.get("message", "")))
        if problem:
            sys.stderr.write("[노트 요청 관문] " + problem)
            return 2
        return 0

    cmd = str((data.get("tool_input") or {}).get("command", ""))

    if mode == "pre-bash":
        if unsafe_merge(cmd):
            sys.stderr.write(
                "[병합 안전 관문] `gh pr checks ... | ...` 처럼 파이프를 붙이면 종료 코드가 가려져 CI가 실패여도 `gh pr merge`가 실행됩니다"
                "(2026-10-06 simplifier-saegim#558 사고). 파이프 없이 `gh pr checks <번호> --watch && gh pr merge <번호> --squash` 로 쓰거나, "
                "`gh pr checks <번호> --json name,state` 결과를 따로 읽고 실패가 0일 때만 병합하세요. 출력을 줄이고 싶으면 `>/dev/null`로 돌리고 "
                "상태는 --json으로 읽습니다.")
            return 2
        return 0

    if mode == "post-bash":
        b = bare_cmd(cmd)
        msg = ""
        if re.search(r"\bgh\s+pr\s+merge\b", b):
            resp = str(data.get("tool_response", "")).lower()
            if "merged" in resp or "tool_response" not in data:
                msg = ("[루프 상기, 보강 1] 병합했습니다. 이 변경으로 무엇이 얼마나 바뀔지 한 줄과 점검일을 남기세요: "
                       "python scripts/ops/jitu_po.py predict add --change \"...\" --expect \"...\" --metric \"...\" --check-on YYYY-MM-DD "
                       "(사소한 문구·정리는 생략해도 됩니다. 점검일이 오면 predict check로 실제 값을 적습니다.)")
        elif re.search(r"\bgit\s+revert\b|\bgit\s+reset\s+--hard\b|\bgh\s+pr\s+revert\b", b):
            msg = ("[루프 상기, 보강 4] 되돌리기를 했습니다. 무엇이 깨졌고 어떤 검사가 없었는지, 추가한 검사(훅·테스트·프로세스표 단계)를 짝으로 남기세요: "
                   "python scripts/ops/jitu_po.py gap add --what \"...\" --missing \"없던 검사\" --added \"추가한 검사\"")
        if msg and is_jitu(data):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}, ensure_ascii=False))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
