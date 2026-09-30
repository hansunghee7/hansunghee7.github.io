#!/usr/bin/env python3
"""에이전트 오케스트레이션 벤치 러너(클라우드 계획자 -> 로컬 작업자 -> 검증). 1회 실행용 기초 스크립트.

흐름: 계획자가 린트 결과를 보고 위임장(delegate)을 만든다 -> [관문1] 스키마·의미 검사 -> 로컬 작업자(actor_critic_loop, Ollama)가 고친다
      -> [관문2] 결과 봉투 스키마 검사 + 오케스트레이터가 ruff를 직접 다시 돌려 작업자의 PASS 주장을 확인한다.
계획자 모드: mock(기본, 무료·결정적) / claude(claude-sonnet-5-5, ANTHROPIC_API_KEY 필요, 호출당 비용 발생).
사용: ACL_BACKEND=ollama:qwen2.5-coder:14b python scripts/ops/orchestrate_bench.py --target bench/hard_mixed.py [--planner mock|claude] [--inject-fault]
출력: 마지막 줄에 JSON 지표 한 줄(완수 여부, 관문 개입 수, 가드 거절 수, 토큰, 지연). 설계: docs/오케스트레이션_벤치마크_설계.md
"""
import argparse
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
FINDING = re.compile(r"^(F\d+)\b[^\n]*\n\s*-->\s.*?:(\d+):\d+", re.M)

# 위임장: 계획자 -> 작업자. strict 도구 스키마와 같은 모양(additionalProperties false, 전 필드 required).
DELEGATE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["task_id", "target", "rule_family", "flagged_lines", "instruction"],
    "properties": {
        "task_id": {"type": "string", "pattern": "^[a-z0-9_-]{1,40}$"},
        "target": {"type": "string", "pattern": "^bench/hard_[a-z0-9_]+\\.py$"},
        "rule_family": {"type": "string", "enum": ["F"]},
        "flagged_lines": {"type": "array", "items": {"type": "integer", "minimum": 1}, "minItems": 1},
        "instruction": {"type": "string", "maxLength": 300},
    },
}
# 결과 봉투: 작업자 -> 계획자
ENVELOPE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["task_id", "status", "iterations", "guard_rejects"],
    "properties": {
        "task_id": {"type": "string"}, "status": {"type": "string", "enum": ["PASS", "FAIL"]},
        "iterations": {"type": "integer", "minimum": 0}, "guard_rejects": {"type": "integer", "minimum": 0},
    },
}


def ruff(path: str) -> tuple[bool, str]:
    r = subprocess.run([sys.executable, "-m", "ruff", "check", "--select", "F", "--output-format", "full", "--no-cache", path],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NOWIN, check=False)
    return r.returncode == 0, r.stdout


def plan_mock(report: str, target: str, task_id: str, fault: bool, note: str) -> tuple[dict, dict]:
    lines = sorted({int(n) for _, n in FINDING.findall(report)})
    if fault and not note:  # 결함 주입: 첫 위임장에 지적되지 않은 줄을 섞어 관문1이 잡는지 본다
        lines = lines + [max(lines) + 50]
    return {"task_id": task_id, "target": target, "rule_family": "F", "flagged_lines": lines, "instruction": ""}, {"in": 0, "out": 0}


def plan_claude(report: str, target: str, task_id: str, fault: bool, note: str) -> tuple[dict, dict]:
    import anthropic  # 지연 import: mock 모드는 SDK·키가 없어도 돈다
    tool = {"name": "delegate", "description": "Delegate the lint fix to the local worker.", "strict": True,
            "input_schema": DELEGATE_SCHEMA}
    retry = f" Previous attempt was rejected: {note}" if note else ""
    prompt = (f"Lint report for {target}:\n{report}\n\nCall the delegate tool exactly once. task_id={task_id}. "
              f"flagged_lines must be exactly the lines the report flags.{retry}")
    resp = anthropic.Anthropic().messages.create(
        model="claude-sonnet-5-5", max_tokens=1024, thinking={"type": "between_tools"},
        tools=[tool], tool_choice={"type": "auto"}, messages=[{"role": "user", "content": prompt}])
    call = next((b for b in resp.content if b.type == "tool_use"), None)
    return (call.input if call else {}), {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}


def gate1(delegation: dict, report: str) -> str:
    """관문1: 스키마 위반 또는 린트가 지적하지 않은 줄이면 사유 문자열, 통과면 빈 문자열."""
    try:
        jsonschema.validate(delegation, DELEGATE_SCHEMA)
    except jsonschema.ValidationError as e:
        return f"스키마 위반: {e.message[:200]}"
    real = {int(n) for _, n in FINDING.findall(report)}
    extra = sorted(set(delegation["flagged_lines"]) - real)
    return f"린트가 지적하지 않은 줄 포함: {extra}" if extra else ""


def worker(delegation: dict, tmp: str) -> tuple[dict, list, float]:
    t = os.path.join(tmp, "t.py")
    shutil.copyfile(os.path.join(ROOT, delegation["target"]), t)
    usage_log = os.path.join(tmp, "usage.log")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "ACL_USAGE_LOG": usage_log, "ACL_EXTRA_NOTE": delegation["instruction"]}
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "actor_critic_loop.py"), "--mode", "logic", t], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env, timeout=900, creationflags=NOWIN, check=False)
    dt = time.time() - t0
    m = dict(re.findall(r"\[metric\] (\w+): (\w+)", r.stdout))
    usage = [tuple(map(int, ln.split()[1:])) for ln in open(usage_log, encoding="utf-8")] if os.path.exists(usage_log) else []
    env_msg = {"task_id": delegation["task_id"], "status": m.get("Status", "FAIL"),
               "iterations": int(m.get("Iterations", 0)), "guard_rejects": int(m.get("GuardRejects", 0))}
    return env_msg, usage, dt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="bench/hard_mixed.py")
    ap.add_argument("--planner", choices=["mock", "claude"], default="mock")
    ap.add_argument("--inject-fault", action="store_true")
    a = ap.parse_args()
    planner = plan_claude if a.planner == "claude" else plan_mock
    task_id = "t1"
    m = {"planner": a.planner, "target": a.target, "gate1_interventions": 0, "gate2_interventions": 0, "completed": False,
         "planner_tokens": {"in": 0, "out": 0}, "worker_tokens": {"in": 0, "out": 0}, "latency_s": {}}
    with tempfile.TemporaryDirectory() as tmp:
        probe = os.path.join(tmp, "probe.py")
        shutil.copyfile(os.path.join(ROOT, a.target), probe)
        _, report = ruff(probe)
        note, delegation, t0 = "", None, time.time()
        for _ in range(2):  # 계획자는 관문1 거절 사유를 받아 한 번 다시 시도한다
            delegation, tok = planner(report, a.target, task_id, a.inject_fault, note)
            m["planner_tokens"]["in"] += tok["in"]
            m["planner_tokens"]["out"] += tok["out"]
            note = gate1(delegation, report)
            if not note:
                break
            m["gate1_interventions"] += 1
        m["latency_s"]["plan"] = round(time.time() - t0, 2)
        if note:
            m["stopped_at"] = "gate1"
        else:
            env_msg, usage, dt = worker(delegation, tmp)
            m["latency_s"]["worker"] = round(dt, 2)
            m["worker_tokens"] = {"in": sum(u[0] for u in usage), "out": sum(u[1] for u in usage)}
            m["worker_guard_rejects"] = env_msg["guard_rejects"]
            m["worker_iterations"] = env_msg["iterations"]
            try:
                jsonschema.validate(env_msg, ENVELOPE_SCHEMA)
                bad = ""
            except jsonschema.ValidationError as e:
                bad = e.message
            ok, _ = ruff(os.path.join(tmp, "t.py"))  # 작업자의 주장이 아니라 직접 재검증
            if bad or (env_msg["status"] == "PASS") != ok:
                m["gate2_interventions"] += 1
                m["stopped_at"] = "gate2"
            m["completed"] = (not bad) and ok and env_msg["status"] == "PASS"
    print(json.dumps(m, ensure_ascii=False))


if __name__ == "__main__":
    main()
