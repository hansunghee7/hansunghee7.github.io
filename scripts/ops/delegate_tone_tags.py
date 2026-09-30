#!/usr/bin/env python3
"""핏 카드 실행기: 대본 문장 목록 -> 줄별 톤 태그 초안. Tier: Local(Ollama, 미공개 대본이 장비 밖으로 나가지 않음).

입력은 기존 tone_tags.json(제미나이가 만든 기준본)의 text 열이다. 엔진은 text를 쓰지 않고 태그만 낸다.
검증기(코드): 줄 수·번호 일치 / tone 허용 목록(기존 5종) / speed 0.85~1.2 / pause 0.15~1.0 / emph 최대 3줄 / 봉투 스키마.
실패하면 사유를 붙여 재시도(최대 3회), 끝내 실패하면 기본값(explain,1.0,0.3,false)으로 채우고 "기본값 대체"로 표시.
비교(기준본이 있을 때): 톤 일치율. 어느 쪽이 맞는지는 판정하지 않는다(청취는 사장님).
사용: python scripts/ops/delegate_tone_tags.py <tone_tags.json 경로> [--model qwen2.5-coder:14b]
저장: .hermes/data/delegations/<시각>/tone_<폴더명>.json      카드: .hermes/task_cards/fit_tone_tags.md
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

import jsonschema

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TONES = ["hook", "explain", "twist", "tension", "closing"]
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["tags"], "properties": {"tags": {
    "type": "array", "items": {"type": "object", "additionalProperties": False,
                               "required": ["i", "tone", "speed", "pause", "emph", "why"],
                               "properties": {"i": {"type": "integer"}, "tone": {"type": "string"}, "speed": {"type": "number"},
                                              "pause": {"type": "number"}, "emph": {"type": "boolean"}, "why": {"type": "string"}}}}}}


def validate(tags: list, n: int) -> list[str]:
    why = []
    if [t["i"] for t in tags] != list(range(n)):
        why.append(f"줄 번호가 0~{n - 1}과 다름(개수 {len(tags)})")
    for t in tags:
        if t["tone"] not in TONES:
            why.append(f"{t['i']}번 tone '{t['tone']}'은 허용 목록({'/'.join(TONES)}) 밖")
        if not 0.85 <= t["speed"] <= 1.2:
            why.append(f"{t['i']}번 speed {t['speed']} 범위(0.85~1.2) 밖")
        if not 0.15 <= t["pause"] <= 1.0:
            why.append(f"{t['i']}번 pause {t['pause']} 범위(0.15~1.0) 밖")
    if sum(t["emph"] for t in tags) > 3:
        why.append("emph true가 3줄 초과")
    return why[:6]


def ask(prompt: str, model: str) -> tuple[str, int, int]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "OLLAMA_JSON": "1", "OLLAMA_NUM_CTX": "8192", "OLLAMA_NUM_PREDICT": "3000"}
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "ops", "ollama_ask.py"), model], input=prompt, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env, timeout=300, creationflags=NOWIN, check=False)
    u = re.search(r"USAGE (\d+) (\d+)", r.stderr)
    return r.stdout, int(u.group(1)) if u else 0, int(u.group(2)) if u else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    a = ap.parse_args()
    ref = json.load(open(a.ref, encoding="utf-8"))
    texts = [x["text"] for x in ref]
    n = len(texts)
    body = "\n".join(f"{i}: {t}" for i, t in enumerate(texts))
    m = {"ref": a.ref, "model": a.model, "lines": n, "attempts": 0, "tokens": {"in": 0, "out": 0}}
    notes, tags, t0 = [], None, time.time()
    for _ in range(3):
        m["attempts"] += 1
        fb = f"\n[이전 시도 거절 사유] {'; '.join(notes)}" if notes else ""
        prompt = ("쇼츠 음성 대본의 줄마다 낭독 톤 태그를 붙여라. 원문은 쓰지 마라. "
                  f"tone은 {'/'.join(TONES)} 중 하나(hook=첫 문장 궁금증, explain=담담한 설명, twist=반전, tension=긴장·위기, closing=마무리). "
                  "speed는 0.85~1.2, pause는 0.15~1.0(문장 뒤 쉼, 초), emph는 강조할 줄만 true(최대 3줄), why는 한 줄 사유. "
                  f"줄 번호는 0부터 {n - 1}까지 빠짐없이.{fb}\n"
                  '출력은 JSON 하나만: {"tags":[{"i":0,"tone":"...","speed":1.0,"pause":0.3,"emph":false,"why":"..."}]}. 다른 키 금지.\n\n'
                  f"## 대본\n{body}")
        out, tin, tout = ask(prompt, a.model)
        m["tokens"]["in"] += tin
        m["tokens"]["out"] += tout
        try:
            d = json.loads(out)
            jsonschema.validate(d, SCHEMA)
        except (ValueError, jsonschema.ValidationError):
            notes = ["JSON 봉투 위반"]
            continue
        notes = validate(d["tags"], n)
        if not notes:
            tags = d["tags"]
            break
    m["latency_s"] = round(time.time() - t0, 1)
    m["passed"] = tags is not None
    if tags is None:
        m["rejected_why"] = notes
        tags = [{"i": i, "tone": "explain", "speed": 1.0, "pause": 0.3, "emph": False, "why": "기본값 대체"} for i in range(n)]
    same = sum(1 for t, r in zip(tags, ref) if t["tone"] == r["tone"])
    m["tone_match_with_ref"] = f"{same}/{n}"
    m["diff_lines"] = [{"i": i, "ref": r["tone"], "engine": t["tone"], "text": r["text"][:30]} for i, (t, r) in enumerate(zip(tags, ref)) if t["tone"] != r["tone"]]
    out_dir = os.path.join(ROOT, ".hermes", "data", "delegations", time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)
    name = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(a.ref))))
    path = os.path.join(out_dir, f"tone_{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump([{**t, "text": x} for t, x in zip(tags, texts)], f, ensure_ascii=False, indent=1)
    m["saved"] = os.path.relpath(path, ROOT).replace("\\", "/")
    print(json.dumps(m, ensure_ascii=False))


if __name__ == "__main__":
    main()
