#!/usr/bin/env python3
"""Stop 훅: 사장님을 향한 적대적·단정적 프레이밍을 마지막 답변에서 잡는다.

입력: stdin JSON (Claude Code Stop 훅 규격, transcript_path 포함).
출력: 문제 있으면 exit 2 + stderr에 고칠 지침 → Claude가 답변을 다시 쓴다.
      stop_hook_active 가 true 면(이미 훅 때문에 다시 쓴 답변) 무한 루프 방지로 통과.
"""
import json, os, re, sys, time

# 1) 사장님의 결정을 "위반·번복"으로 몰아가는 표현
ACCUSE = [
    r"뒤집(는|었|기)", r"번복", r"원칙(에|을)\s*(어긋|위반|깨)", r"약속(을|과)\s*(어긋|위반|깨|달리)",
    r"하지\s*않기로\s*(했|한)\s*(것|걸|건)", r"안\s*하기로\s*(했|한)", r"금지(된|였던)\s*(것|항목)",
    r"모순", r"일관성이\s*없", r"말이\s*바뀌", r"또\s*바뀌",
]
# 2) 사례·출처 없는 크루 일반화
GENERALIZE = [
    r"크루(가|는|들이).{0,20}(습관|경향|패턴)", r"세션들이.{0,20}(습관|경향|패턴)",
    # 앞뒤 글자가 한글이면 다른 낱말의 일부다(2026-09-20 오탐 두 건: "오늘 낮입니다"의 "늘", "늘어나는지는 확인이 필요합니다"의 "늘")
    r"(?<![가-힣])(항상|매번|늘)(?![가-힣])\s*.{0,15}(합니다|입니다)", r"반복적으로.{0,15}(합니다|있습니다)",
]
# 3) 사장님께 행동을 시키는 요청(에이전틱 원칙 CLAUDE.md id:ag01, 사장님 지시 2026-10-03 "에이전트가 최대한 다 하고 사장님은 필수만").
#    사람 개입은 4종뿐: 외부 서비스 자격증명 / 비가역·돈 승인 / 제품·방향 결정 / 규칙상 에이전트 금지(계정 생성, 외부 발신 등).
#    카빗 패스 PIN 입력은 허용 목록에 없다(사장님 지시 2026-10-03: PIN 입력도 사장님이 안 하는 방향을 찾는다 = 없앨 개입). 요청하면 항상 막고,
#    PIN 없이 가는 설계(대장 N116)에 개선 과제를 올렸다는 표시 [PIN 개선 과제: N숫자]가 있을 때만 통과한다.
#    그 밖의 "…해 주세요" 요청은 에이전트가 먼저 할 수 있는지 확인해야 하고, 정말 필요하면 [사람 개입 필요: 사유] 한 줄을 단다.
ASK_PIN = r"사장님[이께가에서은는]*[^.\n]{0,60}PIN[^.\n]{0,20}(입력|열어|풀어|넣어)[^.\n]{0,12}(주세요|주시면|주시겠|해\s*주|부탁|하셔야|하시면 됩니다|해야 합니다)"
PIN_TAG = r"\[PIN 개선 과제:\s*N\d+"
ASK_BOSS = r"사장님[이께가에서은는]*[^.\n]{0,60}(입력|눌러|클릭|실행|열어|새로\s*고침|붙여\s*넣|복사|로그인|확인|재시작|설치|접속)[^.\n]{0,12}(주세요|주시면|주시겠|해\s*주|부탁|하셔야|하시면 됩니다|해야 합니다)"
HUMAN_TAG = r"\[사람 개입 필요:\s*(자격증명|비가역|돈|제품 결정|방향 결정|규칙상 금지|외부 발신|계정 생성)"
# 통과 표지: 근거를 달았거나 추정임을 밝힌 경우
EVIDENCE = [r"\[추정\]", r"\[사례:", r"\(20\d\d-\d\d-\d\d", r"cxo-db\s*#\d+", r"원문", r"이력으로"]
# 허용 문맥: 문서 갱신 제안 형식
UPDATE_FORM = r"(문서|기록|§|절)(엔|에는|은|는).{0,40}(갱신|고치|옮기|바꾸)"

def last_assistant_text(path):
    text = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try: obj = json.loads(line)
            except Exception: continue
            if obj.get("type") == "assistant":
                msg = obj.get("message", {})
                parts = msg.get("content", [])
                if isinstance(parts, str): text = [parts]; continue
                t = [p.get("text","") for p in parts if isinstance(p, dict) and p.get("type") == "text"]
                if t: text = t
    return "\n".join(text)

def check(text):
    problems = []
    has_evidence = any(re.search(p, text) for p in EVIDENCE)
    for p in ACCUSE:
        for m in re.finditer(p, text):
            span = text[max(0,m.start()-40):m.end()+40].replace("\n"," ")
            if re.search(UPDATE_FORM, span): continue
            problems.append(("적대 프레이밍", span))
    for p in GENERALIZE:
        for m in re.finditer(p, text):
            span = text[max(0,m.start()-40):m.end()+40].replace("\n"," ")
            if has_evidence: continue
            problems.append(("근거 없는 일반화", span))
    if not re.search(PIN_TAG, text):
        for m in re.finditer(ASK_PIN, text):
            span = text[max(0,m.start()-30):m.end()+30].replace("\n"," ")
            problems.append(("사장님께 PIN 입력 요청", span))
    if not re.search(HUMAN_TAG, text):
        for m in re.finditer(ASK_BOSS, text):
            span = text[max(0,m.start()-30):m.end()+30].replace("\n"," ")
            if "PIN" in m.group(0) and re.search(PIN_TAG, text): continue  # PIN 요청은 개선 과제 표시가 있으면 PIN 규칙이 판정
            problems.append(("사장님께 행동 요청(사유 표시 없음)", span))
    return problems

HUMAN_LOG = os.environ.get("HUMAN_TOUCH_LOG", "C:/work/_ops/human_touch_log.jsonl")

def log_human_touch(text):
    """[사람 개입 필요: 사유] 표시가 있는 답변을 기록한다(시각, 사유, 표시 앞뒤 한 줄). 기록 실패는 답변을 막지 않는다."""
    try:
        for m in re.finditer(HUMAN_TAG, text):
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            line = text[line_start: line_end if line_end >= 0 else len(text)].strip()
            os.makedirs(os.path.dirname(HUMAN_LOG), exist_ok=True)
            with open(HUMAN_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.strftime("%F %T"), "reason": m.group(1), "line": line[:300]}, ensure_ascii=False) + "\n")
    except Exception:
        pass

if __name__ == "__main__":
    try:
        data = json.load(sys.stdin) if not sys.stdin.isatty() else {}
        if data.get("stop_hook_active"): sys.exit(0)
        text = data.get("_text") or (last_assistant_text(data["transcript_path"]) if data.get("transcript_path") else "")
        probs = check(text) if text else []
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)  # 검사기 자체 오류로 답변을 막지 않는다
    if not probs:
        log_human_touch(text)  # 사유를 달고 사람 개입을 요청한 답변은 기록(매주 "없앨 수 있는 개입"을 골라 제품 개선으로 연결)
        sys.exit(0)
    if any(k.startswith("사장님께 PIN") for k, _ in probs):
        print("사장님께 PIN 입력을 요청하는 문장이 있습니다. PIN 입력은 없앨 개입이라 요청할 수 없습니다(사장님 지시 2026-10-03). "
              "일반 키는 일반 칸(PIN 없이), 중요 키는 승인 방식으로 가는 설계(대장 N116 2단계)에 이번 막힘을 개선 과제로 올리고, 같은 답변에 [PIN 개선 과제: N116] 한 줄을 다세요. "
              "과제를 올리기 전에는 사장님 대신 에이전트가 할 수 있는 우회(다른 키 경로, 기다렸다 재시도, 텔레그램 알림)를 먼저 쓰세요.", file=sys.stderr)
    if any(k.startswith("사장님께 행동 요청") for k, _ in probs):
        print("사장님께 행동을 시키는 문장이 있습니다. 에이전틱 원칙(CLAUDE.md id:ag01): 사람은 4종(외부 자격증명, 비가역·돈 승인, 제품·방향 결정, 규칙상 금지)에만 개입합니다. "
              "먼저 에이전트가 직접 할 수 있는지(스크립트·도구·브라우저·헤르메스·재시도·기록 찾기) 확인해서 직접 하세요. 정말 불가피하면 같은 답변에 [사람 개입 필요: 사유] 한 줄을 다세요.", file=sys.stderr)
    print("답변에 사장님을 향한 적대적 프레이밍, 근거 없는 일반화 또는 사유 없는 행동 요청이 있습니다. 다시 쓰세요.", file=sys.stderr)
    print("규칙: 사장님의 지금 발화가 최상위이고 문서는 기억입니다. 문서와 다르면 '문서엔 X로 돼 있으니 Y로 갱신하겠습니다' 한 문장으로만. "
          "'뒤집는다·번복·위반·안 하기로 했다'로 사장님을 몰지 않습니다. 크루 전체 일반화는 사례 2건+날짜/출처가 있을 때만, 없으면 [추정] 표시.", file=sys.stderr)
    for kind, span in probs[:5]:
        print(f"- {kind}: …{span}…", file=sys.stderr)
    sys.exit(2)
