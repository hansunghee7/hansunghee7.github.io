#!/usr/bin/env python3
"""노트 카드 실행기: PR 하나의 diff -> PR 설명 초안 JSON. Tier: Local(Ollama, diff가 장비 밖으로 나가지 않음).

엔진은 초안만 낸다. PR 본문·수용 기준·검증 증거 문장은 노트가 직접 쓴다(카드 '호출자의 최종 판단').
검증기(코드): 봉투 스키마 / 제목 60자 이하 / what 3~6개 / how_to_verify 1~3개 / touched_files가 실제 diff 파일의 부분집합
             / 괄호·긴 줄표 없음. 실패한 사유를 붙여 다시 시도(최대 3회), 그래도 실패하면 "거절"(노트가 직접 씀).
사용: python scripts/ops/delegate_pr_desc.py <PR번호> [--repo owner/name] [--model qwen2.5-coder:14b]
출력: 마지막 줄 JSON 지표. 초안 저장: .hermes/data/delegations/<시각>/pr_<번호>.json
카드: .hermes/task_cards/note_pr_description.md
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
DASHES = "—–―"
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["title", "what", "how_to_verify", "touched_files"],
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "what": {"type": "array", "items": {"type": "string"}},
        "how_to_verify": {"type": "array", "items": {"type": "string"}},
        "touched_files": {"type": "array", "items": {"type": "string"}},
    },
}


def gh(*args: str) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=60, creationflags=NOWIN, check=False)
    if r.returncode:
        sys.exit(f"gh 실패: {r.stderr[:200]}")
    return r.stdout


def validate(d: dict, files: set) -> list[str]:
    why = []
    if len(d["title"]) > 60:
        why.append(f"제목 {len(d['title'])}자로 60자 초과")
    if not 3 <= len(d["what"]) <= 6:
        why.append(f"what이 {len(d['what'])}개(3~6개여야 함)")
    if not 1 <= len(d["how_to_verify"]) <= 3:
        why.append(f"how_to_verify가 {len(d['how_to_verify'])}개(1~3개여야 함)")
    extra = set(d["touched_files"]) - files
    if extra:
        why.append(f"diff에 없는 파일: {sorted(extra)[:3]}")
    text = d["title"] + "".join(d["what"]) + "".join(d["how_to_verify"])
    if any(c in text for c in "()（）"):
        why.append("괄호 사용")
    if any(c in text for c in DASHES):
        why.append("긴 줄표 사용")
    return why


def ask(prompt: str, model: str) -> tuple[str, int, int]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "OLLAMA_JSON": "1", "OLLAMA_NUM_CTX": "16384", "OLLAMA_NUM_PREDICT": "1500"}
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "ops", "ollama_ask.py"), model], input=prompt, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env, timeout=600, creationflags=NOWIN, check=False)
    u = re.search(r"USAGE (\d+) (\d+)", r.stderr)
    return r.stdout, int(u.group(1)) if u else 0, int(u.group(2)) if u else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pr")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    a = ap.parse_args()
    rp = ["--repo", a.repo] if a.repo else []
    diff = gh("pr", "diff", a.pr, *rp)
    files = set(re.findall(r"^diff --git a/(\S+) b/", diff, re.M))
    lines = diff.count("\n")
    if lines > 800:
        sys.exit(f"diff {lines}줄: 카드 한도 800줄 초과(파일 단위로 쪼개야 함)")
    notes: list[str] = []
    m = {"pr": a.pr, "model": a.model, "diff_lines": lines, "attempts": 0, "tokens": {"in": 0, "out": 0}}
    t0, draft = time.time(), None
    for _ in range(3):
        m["attempts"] += 1
        fb = f"\n[이전 시도 거절 사유] {'; '.join(notes)}" if notes else ""
        prompt = ("아래 PR diff를 읽고 PR 설명 초안을 만들어라. diff에 없는 사실을 만들지 마라. 괄호와 긴 줄표를 쓰지 마라. 한국어.\n"
                  "title은 60자 이하 한 줄, what은 변경 내용 불릿 3~6개, how_to_verify는 확인 방법 1~3개, "
                  f"touched_files는 diff에 실제로 있는 파일 경로만.{fb}\n"
                  '출력은 JSON 하나만: {"title":"...","what":["..."],"how_to_verify":["..."],"touched_files":["..."]}. 다른 키 금지.\n\n'
                  f"## diff 파일 목록\n{chr(10).join(sorted(files))}\n\n## diff\n{diff}")
        out, tin, tout = ask(prompt, a.model)
        m["tokens"]["in"] += tin
        m["tokens"]["out"] += tout
        try:
            d = json.loads(out)
            jsonschema.validate(d, SCHEMA)
        except (ValueError, jsonschema.ValidationError):
            notes = ["JSON 봉투 위반"]
            continue
        notes = validate(d, files)
        if not notes:
            draft = d
            break
    m["latency_s"] = round(time.time() - t0, 1)
    m["passed"] = draft is not None
    m["rejected_why"] = notes if draft is None else []
    out_dir = os.path.join(ROOT, ".hermes", "data", "delegations", time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"pr_{a.pr}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"pr": a.pr, "status": "draft" if draft else "rejected", "draft": draft, "rejected_why": m["rejected_why"]},
                  f, ensure_ascii=False, indent=2)
    m["saved"] = os.path.relpath(path, ROOT).replace("\\", "/")
    print(json.dumps(m, ensure_ascii=False))


if __name__ == "__main__":
    main()
