#!/usr/bin/env python3
"""Stop 훅: 막혔다고 말하는 답변은 이번 턴에 프로세스표·절차 기록을 열어 봤을 때만 통과한다(사장님 지시 2026-10-04).

사고(2026-10-04 핏): 비즈(Vids) 내려받기에서 기록된 절차를 찾아보지 않고 추측으로 메뉴를 눌러 한참 막혔고, 사장님이 정답 경로를 보여 주셨다.
규칙(2026-10-11 좁힘: 이번 턴 도구 결과에 오류가 하나도 없으면 설명·보고 문장이라 통과): 마지막 답변에 '막힘' 표현(막혔·안 됩니다·실패했·멈췄 등)이 있으면, 이번 턴 도구 호출에
  프로세스표·GENERATION_PIPELINES·레시피·업무대장 같은 절차 기록을 읽거나 검색한 흔적이 있어야 한다.
  없으면 exit 2로 "먼저 프로세스표를 찾아 읽고 다시 답하라"고 알린다.
입력: stdin JSON(Claude Code Stop 훅). stop_hook_active면 통과(무한 루프 방지). 검사기 오류는 통과.
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("commit_gate", Path(__file__).parent / "commit-gate.py")
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)

# 2026-10-10 좁힘(사장님 승인 "추천대로 적용"): '되지 않·못 했·멈춰·못 받·막힌'은 통계·위험 안내·설명 문장에 오탐이 잦아 뺐다(한 세션 5회 재현).
# 코드 표기(백틱)는 판정에서 제외한다. 막힘을 직접 말하는 표현만 남긴다.
STUCK = re.compile(r"(막혔|막혀|안\s*됩니다|안\s*됐|실패했|실패합니다|멈췄|동작하지\s*않|열리지\s*않|내려받아지지)")
CODE = re.compile(r"(```.*?```|`[^`\n]*`)", re.S)
NOT_STUCK = re.compile(r"(막히지\s*않|막힘\s*없|막힌\s*곳\s*없|실패\s*없|문제\s*없)")
PROC_REF = re.compile(r"(프로세스표|GENERATION_PIPELINES|구PC_작업실_영상레시피|영상레시피|업무대장|DAILY_ROUTINE|session-start|hermes-delegate|ink-desk)")


# 2026-10-13 추가(사장님 지적 "사장한테 뭐 시킬 때 기록 찾는 훅이 왜 안 도나", 10/12에도 같은 질문): 사장님께 사람 개입을 요청하는 답변은 막힘 표현이 없어도
# 이번 턴에 기록 검색(recall.py·ledger_lint·opsdb·proc.py·프로세스표·업무대장·Grep docs)을 한 흔적이 있어야 한다.
ASK_TAG = re.compile(r"\[사람 개입 필요:")
RECORD_REF = re.compile(r"(recall\.py|ledger_lint|opsdb\.py|proc\.py|pipeline_db|session_brief|프로세스표|업무대장|진행상황\.md|docs[/\\]|[/\\]docs\b)")
# 2026-10-16 추가(사장님 승인, 카드 탐#106): 돈 이야기(상한·결제·과금 등)를 하는 답변은 사람 개입 요청이 없어도
# 같은 턴에 기록 검색을 해야 한다. 사고: Actions 예산 조언이 사장님 10/15 원문을 확인하지 않은 채 세 번 바뀜.
MONEY = re.compile(r"(\$\s?\d|\d\s?달러|₩\s?\d|\d\s?만\s?원|결제|과금|청구|요금제|상한|예산)")
# 2026-10-20 추가(사장님 지시 "앞으로 사장에게 제안을 할 때는 필수로 과거 기록 찾고 제안", 카드 탐-관문): 제안·추천·"정하실 것: (없음 아님)"이 있는 답변은
# 같은 턴에 기록 검색(recall.py·proc.py·ledger_lint·opsdb·프로세스표·업무대장)을 한 흔적이 있어야 한다. 사고: 이미 정한 결정을 되묻는 제안이 반복됨(10/20 Claude Code 로그인 방식 재질문 등).
PROPOSE = re.compile(r"(정하실\s*것\s*[:：]\s*(?!\s*없음)\S|제\s*추천은|추천\s*(?:합니다|드립니다)|권장\s*합니다|제안\s*(?:합니다|드립니다|해\s*봅니다|드려요)|제의\s*합니다|제안\s*[:：])")  # 10/20 비티·덱스 리뷰 반영: 띄어쓰기·'추천드립니다'·'권장합니다' 추가(코드 블록 안 문구는 오탐 방지로 계속 제외)


# 2026-10-19 추가(노트 요청, 사장님 "추천대로 진행", 사고: 비티(GCP 풀=Vertex)가 되는데 '비티 없음'으로 보고, cxo-db #490·노트 #65~#69):
# "비티 없음/막힘/한도로 막힘" 보고는 같은 턴에 Vertex 경로(ask_bt.sh BT_MODEL=vertex) 호출이나 agent_calls.csv 확인 흔적이 있어야 한다.
BT_CLAIM = re.compile(r"(비티[^.\n]{0,10}(없음|없습니다|막힘|막혔|막혀|불가|쓸\s*수\s*없|못\s*씁|사용\s*안)|비티\s*한도[^.\n]{0,8}(막|소진|초과)|한도로\s*막)")
BT_NEG = re.compile(r"(비티[^.\n]{0,10}(막히지|막힘\s*없|불가\s*아님)|막히지\s*않)")
# 증거(덱스 리뷰 10/19 반영): agent_calls.csv는 언급이 아니라 읽는 명령(tail·head·cat·grep·Get-Content·Read)과 함께일 때만 인정한다.
BT_EVIDENCE = re.compile(r"(BT_MODEL\s*=\s*vertex|ask_bt\.sh[^\n]*vertex|(?:tail|head|cat|grep|type|Get-Content|Read)\b[^\n]*agent_calls\.csv)")


def consulted(tools, ref=PROC_REF):
    for name, inp in tools:
        blob = name + " " + " ".join(str(v) for v in inp.values())
        if name in ("Read", "Grep", "Glob", "Bash", "PowerShell", "Skill") and ref.search(blob):
            return True
    return False


EXIT_ERR = re.compile(r"(?:Exit code|exit code|종료 코드)[:\s]*([1-9]\d*)")


def turn_has_error(path):
    """이번 턴(마지막 진짜 사용자 발화 이후) 도구 결과에 오류(is_error true 또는 0이 아닌 종료 코드)가 있는지. commit-gate.load_turn과 같은 턴 경계를 쓴다. 파싱 실패는 예외로 올려 통과시킨다."""
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    start = 0
    for i, ev in enumerate(events):
        if ev.get("type") != "user":
            continue
        c = ev.get("message", {}).get("content", [])
        parts = [c] if isinstance(c, str) else [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
        joined = chr(10).join(parts)
        if joined and "SYSTEM NOTIFICATION" not in joined and not joined.lstrip().startswith("<system-reminder>"):
            start = i
    for ev in events[start + 1:]:
        if ev.get("type") != "user":
            continue
        c = ev.get("message", {}).get("content", [])
        if not isinstance(c, list):
            continue
        for p in c:
            if not isinstance(p, dict) or p.get("type") != "tool_result":
                continue
            if p.get("is_error") is True:
                return True
            body = p.get("content")
            if isinstance(body, list):
                body = " ".join(x.get("text", "") for x in body if isinstance(x, dict))
            if isinstance(body, str) and EXIT_ERR.match(body.lstrip()):
                return True
    return False


def check(text, tools, has_error=True):
    """has_error: 이번 턴 도구 결과에 오류가 하나라도 있는가. 없으면(설명·통계·보고 문장의 오탐) 통과한다(2026-10-11 좁힘)."""
    plain = CODE.sub("", text)
    if BT_CLAIM.search(BT_NEG.sub("", plain)) and not consulted(tools, BT_EVIDENCE):
        return "bt-claim-without-vertex-check"
    if ASK_TAG.search(text) and not consulted(tools, RECORD_REF):
        return "ask-without-record-lookup"
    if MONEY.search(CODE.sub("", text)) and not consulted(tools, RECORD_REF):
        return "money-without-record-lookup"
    if PROPOSE.search(CODE.sub("", text)) and not consulted(tools, RECORD_REF):
        return "propose-without-record-lookup"
    if not has_error:
        return None
    text = CODE.sub("", text)
    if not STUCK.search(text):
        return None
    stripped = NOT_STUCK.sub("", text)
    if not STUCK.search(stripped):
        return None
    if consulted(tools):
        return None
    return "no-process-lookup"


if __name__ == "__main__":
    for _s in (sys.stdin, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        data = json.load(sys.stdin) if not sys.stdin.isatty() else {}
        if data.get("stop_hook_active"):
            sys.exit(0)
        if data.get("_text") is not None:
            text, tools = data["_text"], data.get("_tools", [])
            err = data.get("_error", True)
        elif data.get("transcript_path"):
            text, tools = cg.load_turn(data["transcript_path"])
            err = turn_has_error(data["transcript_path"])
        else:
            sys.exit(0)
        verdict = check(text, tools, err) if text else None
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
    if not verdict:
        sys.exit(0)
    # 2026-10-19: 발동 기록(오탐률 기준선 복원용, 덱스 #132 설계). 원문은 남기지 않고 분기·시각·오류 여부만 쓴다. 기록 실패는 무시한다.
    try:
        import datetime
        with open(os.environ.get("STUCK_GATE_LOG", "C:/work/_ops/stuck_gate_log.jsonl"), "a", encoding="utf-8") as _f:
            _f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "verdict": verdict, "has_error": bool(err), "rule": "2026-10-19"}, ensure_ascii=False) + "\n")
    except Exception:
        pass
    if verdict == "bt-claim-without-vertex-check":
        print("비티 없음·막힘·한도 보고인데 이번 턴에 Vertex 경로 확인 흔적(ask_bt.sh BT_MODEL=vertex 호출 또는 agent_calls.csv 최근 행 확인)이 없습니다(사장님 10/19 승인, 노트 요청, cxo-db #490). "
              "비티(GCP 풀=Vertex)는 안티그래비티가 막혀도 계속 됩니다. `BT_MODEL=vertex bash scripts/ops/ask_bt.sh <카드> <출력>`으로 실제 호출하거나 agent_calls.csv를 확인한 뒤 다시 답하세요.", file=sys.stderr)
        sys.exit(2)
    if verdict == "ask-without-record-lookup":
        print("사장님께 사람 개입을 요청하는 답변인데 이번 턴에 기록(recall.py·ledger_lint.py --find·프로세스표·업무대장)을 찾아본 흔적이 없습니다(사장님 지시 2026-10-13). "
              "이미 사장님이 해 둔 일(예: SNS 연결)이거나 정해 둔 결정일 수 있으니, 먼저 기록을 검색해 대조한 뒤 필요한 부탁만 남기고 다시 답하세요.", file=sys.stderr)
        sys.exit(2)
    if verdict == "propose-without-record-lookup":
        print("사장님께 제안·추천·결정 요청(정하실 것)을 하는 답변인데 이번 턴에 기록(recall.py·proc.py·ledger_lint.py --find·프로세스표·업무대장)을 찾아본 흔적이 없습니다(사장님 지시 2026-10-20). "
              "먼저 기록을 검색해 이미 정한 결정·선례가 있는지 대조하고, 기존 결정을 바꾸자는 제안이면 '기존 원문 X → 새 근거 Y' 형식으로, 이미 정해진 것은 되묻지 말고 실행으로 다시 답하세요.", file=sys.stderr)
        sys.exit(2)
    if verdict == "money-without-record-lookup":
        print("돈 이야기(상한·결제·과금·예산 등)가 있는 답변인데 이번 턴에 기록(recall.py·proc.py·업무대장)을 찾아본 흔적이 없습니다(사장님 승인 2026-10-16, 카드 탐#106). "
              "사장님이 이미 정한 예산 원칙이 있을 수 있으니 먼저 기록을 검색해 대조하고, 바꾸자는 제안이면 '기존 원문 X → 새 근거 Y' 형식으로 다시 답하세요.", file=sys.stderr)
        sys.exit(2)
    print("막혔다는 말이 있지만 이번 턴에 절차 기록(프로세스표·GENERATION_PIPELINES·영상레시피·업무대장)을 찾아 읽은 흔적이 없습니다(사장님 지시 2026-10-04). "
          "추측으로 다시 시도하지 말고, 먼저 해당 프로세스표/절차 기록을 검색·열람해 기록된 단계와 대조한 뒤 어느 단계에서 막혔는지 다시 답하세요. "
          "기록에 없으면 그 사실을 적고 프로세스표에 추가하세요.", file=sys.stderr)
    sys.exit(2)
