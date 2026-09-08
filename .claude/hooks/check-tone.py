#!/usr/bin/env python3
"""Stop 훅: 사장님을 향한 적대적·단정적 프레이밍을 마지막 답변에서 잡는다.

입력: stdin JSON (Claude Code Stop 훅 규격, transcript_path 포함).
출력: 문제 있으면 exit 2 + stderr에 고칠 지침 → Claude가 답변을 다시 쓴다.
      stop_hook_active 가 true 면(이미 훅 때문에 다시 쓴 답변) 무한 루프 방지로 통과.
"""
import json, re, sys

# 1) 사장님의 결정을 "위반·번복"으로 몰아가는 표현
ACCUSE = [
    r"뒤집(는|었|기)", r"번복", r"원칙(에|을)\s*(어긋|위반|깨)", r"약속(을|과)\s*(어긋|위반|깨|달리)",
    r"하지\s*않기로\s*(했|한)\s*(것|걸|건)", r"안\s*하기로\s*(했|한)", r"금지(된|였던)\s*(것|항목)",
    r"모순", r"일관성이\s*없", r"말이\s*바뀌", r"또\s*바뀌",
]
# 2) 사례·출처 없는 크루 일반화
GENERALIZE = [
    r"크루(가|는|들이).{0,20}(습관|경향|패턴)", r"세션들이.{0,20}(습관|경향|패턴)",
    r"(항상|매번|늘)\s*.{0,15}(합니다|입니다)", r"반복적으로.{0,15}(합니다|있습니다)",
]
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
    return problems

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
    if not probs: sys.exit(0)
    print("답변에 사장님을 향한 적대적 프레이밍 또는 근거 없는 일반화가 있습니다. 다시 쓰세요.", file=sys.stderr)
    print("규칙: 사장님의 지금 발화가 최상위이고 문서는 기억입니다. 문서와 다르면 '문서엔 X로 돼 있으니 Y로 갱신하겠습니다' 한 문장으로만. "
          "'뒤집는다·번복·위반·안 하기로 했다'로 사장님을 몰지 않습니다. 크루 전체 일반화는 사례 2건+날짜/출처가 있을 때만, 없으면 [추정] 표시.", file=sys.stderr)
    for kind, span in probs[:5]:
        print(f"- {kind}: …{span}…", file=sys.stderr)
    sys.exit(2)
