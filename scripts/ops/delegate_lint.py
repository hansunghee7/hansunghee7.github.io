#!/usr/bin/env python3
"""탐의 첫 위임 과업: 저장소의 실제 미사용 import·변수·중복 정의(F401/F811/F841)를 로컬 작업자에게 맡겨 '패치 제안'만 받는다.

저장소 파일은 절대 직접 고치지 않는다. 임시 복사본에서 무균실 루프(actor_critic_loop, Ollama)가 고치고,
이 스크립트가 ① 문법 ② 원래 지적 개수 감소 ③ 다른 규칙 오류가 늘지 않았는지 ④ 결과 봉투 스키마를 직접 확인한 뒤
통과한 파일만 unified diff로 .hermes/data/delegations/<시각>/ 에 저장한다. 적용은 탐이 diff를 보고 git apply로 한다(최종 판단은 탐).
사용: python scripts/ops/delegate_lint.py [--path scripts] [--max-files 5] [--max-lines 300]
출력: 마지막 줄 JSON 요약. 설계: docs/에이전트_헤르메스_위임_설계.md
"""
import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import jsonschema

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
RULES = "F401,F811,F841"
ENVELOPE = {
    "type": "object", "additionalProperties": False,
    "required": ["file", "status", "iterations", "guard_rejects", "findings_before", "findings_after"],
    "properties": {"file": {"type": "string"}, "status": {"enum": ["PASS", "FAIL"]},
                   "iterations": {"type": "integer", "minimum": 0}, "guard_rejects": {"type": "integer", "minimum": 0},
                   "findings_before": {"type": "integer", "minimum": 0}, "findings_after": {"type": "integer", "minimum": 0}},
}


def ruff_json(path: str, select: str) -> list:
    r = subprocess.run([sys.executable, "-m", "ruff", "check", "--select", select, "--output-format", "json", "--no-cache", path],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NOWIN, check=False)
    return json.loads(r.stdout or "[]")


def candidates(path: str, max_lines: int) -> tuple[list[str], list[str]]:
    found = ruff_json(os.path.join(ROOT, path), RULES)
    files = sorted({os.path.relpath(f["filename"], ROOT).replace("\\", "/") for f in found})
    ok, skipped = [], []
    for f in files:
        n = sum(1 for _ in open(os.path.join(ROOT, f), encoding="utf-8", errors="replace"))
        (ok if n <= max_lines else skipped).append(f)  # 로컬 모델 컨텍스트(8192토큰) 한계: 큰 파일은 제외
    return ok, skipped


def delegate(rel: str, tmp: str) -> dict:
    src = os.path.join(ROOT, rel)
    work = os.path.join(tmp, os.path.basename(rel))
    shutil.copyfile(src, work)
    before = len(ruff_json(work, RULES))
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.setdefault("ACL_BACKEND", "ollama:qwen2.5-coder:14b")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "actor_critic_loop.py"), "--mode", "logic", "--select", RULES, work],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=900,
                       creationflags=NOWIN, check=False)
    m = dict(re.findall(r"\[metric\] (\w+): (\w+)", r.stdout))
    return {"file": rel, "status": m.get("Status", "FAIL"), "iterations": int(m.get("Iterations", 0)),
            "guard_rejects": int(m.get("GuardRejects", 0)), "findings_before": before,
            "findings_after": len(ruff_json(work, RULES)), "_work": work}


def independent_check(rel: str, env_msg: dict) -> str:
    """작업자의 주장을 믿지 않고 다시 확인한다. 통과면 빈 문자열."""
    try:
        jsonschema.validate({k: v for k, v in env_msg.items() if not k.startswith("_")}, ENVELOPE)
    except jsonschema.ValidationError as e:
        return f"봉투 스키마 위반: {e.message[:120]}"
    work = env_msg["_work"]
    if env_msg["status"] != "PASS" or env_msg["findings_after"] != 0:
        return "루프가 PASS하지 못함"
    if subprocess.run([sys.executable, "-m", "py_compile", work], capture_output=True, creationflags=NOWIN, check=False).returncode:
        return "py_compile 실패"
    other_before = len(ruff_json(os.path.join(ROOT, rel), "F,E9")) - env_msg["findings_before"]
    other_after = len(ruff_json(work, "F,E9"))
    if other_after > max(other_before, 0):
        return f"다른 규칙 오류가 늘어남({other_before} -> {other_after})"
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="scripts")
    ap.add_argument("--max-files", type=int, default=5)
    ap.add_argument("--max-lines", type=int, default=300)
    a = ap.parse_args()
    files, skipped = candidates(a.path, a.max_lines)
    out_dir = os.path.join(ROOT, ".hermes", "data", "delegations", time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)
    summary = {"candidates": len(files), "skipped_too_long": skipped, "proposed": [], "rejected": [], "seconds": 0}
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        for rel in files[:a.max_files]:
            env_msg = delegate(rel, tmp)
            why = independent_check(rel, env_msg)
            if why:
                summary["rejected"].append({"file": rel, "why": why})
                continue
            old = open(os.path.join(ROOT, rel), encoding="utf-8").read().splitlines(keepends=True)
            new = open(env_msg["_work"], encoding="utf-8").read().splitlines(keepends=True)
            diff = "".join(difflib.unified_diff(old, new, f"a/{rel}", f"b/{rel}"))
            with open(os.path.join(out_dir, rel.replace("/", "__") + ".diff"), "w", encoding="utf-8", newline="\n") as f:
                f.write(diff)
            summary["proposed"].append({"file": rel, "iterations": env_msg["iterations"], "guard_rejects": env_msg["guard_rejects"],
                                        "findings": f"{env_msg['findings_before']}->0"})
    summary["seconds"] = round(time.time() - t0, 1)
    summary["out_dir"] = os.path.relpath(out_dir, ROOT).replace("\\", "/")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
