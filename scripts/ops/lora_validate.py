#!/usr/bin/env python3
"""LoRA 수집 데이터 재검증기: 저장된 (prompt, completion)을 독립적으로 재생해 지금의 가드 기준으로 다시 채점한다.

logic_replace.jsonl 각 줄에 대해: prompt에서 원본 소스와 린트 로그를 복원 -> completion(줄 수정 JSON) 적용(apply_edits, 현재 가드 전부)
-> 결과가 ast 정상 + 최상위 def/class 보존 + `ruff check --select F` 통과인지, 원본은 실제로 위반이었는지 확인한다.
통과한 줄만 validated/logic_replace.jsonl에 쓰고, 실패한 줄은 rejected/에 사유와 함께 남긴다(원본 파일은 건드리지 않는다).
사용: python scripts/ops/lora_validate.py [.hermes/data/lora_raw/logic_replace.jsonl]
"""
import ast
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
import actor_critic_loop as acl  # noqa: E402

NUMBERED = re.compile(r"^ *\d+\| ?(.*)$")


def ruff_f(src: str) -> bool:
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.py")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(src)
        r = subprocess.run([sys.executable, "-m", "ruff", "check", "--select", "F", "--no-cache", p],
                           capture_output=True, creationflags=acl.NOWIN, check=False)
        return r.returncode == 0


def check(row: dict) -> str | None:
    """통과하면 None, 실패하면 사유."""
    p = row["prompt"]
    if "## 소스 코드\n" not in p or "## 린트 에러 로그\n" not in p:
        return "prompt 형식 아님"
    log = p.split("## 린트 에러 로그\n", 1)[1].split("\n\n## 소스 코드\n", 1)[0]
    body = p.split("## 소스 코드\n", 1)[1].rstrip("\n").split("\n")
    lines = []
    for ln in body:
        m = NUMBERED.match(ln)
        if not m:
            return "소스 복원 실패"
        lines.append(m.group(1))
    src = "\n".join(lines) + "\n"
    try:
        ast.parse(src)
    except SyntaxError:
        return "복원한 원본이 문법 오류"
    if ruff_f(src):
        return "원본에 린트 위반 없음(무의미한 샘플)"
    new, why, _ = acl.apply_edits(src, row["completion"], log)
    if new is None:
        return f"현재 가드 거부: {why[:60]}"
    try:
        ast.parse(new)
    except SyntaxError:
        return "적용 결과 문법 오류"
    if not acl.top_names(new) >= acl.top_names(src):
        return "최상위 함수·클래스 소실"
    if not ruff_f(new):
        return "적용 결과가 ruff F 미통과"
    return None


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(acl.DATA_DIR, "logic_replace.jsonl")
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    ok, bad, seen = [], [], set()
    for r in rows:
        key = (r["prompt"], r["completion"], r.get("model"))  # 다른 모델이 낸 같은 정답은 별개 샘플
        why = "완전 중복" if key in seen else check(r)
        seen.add(key)
        (ok if why is None else bad).append((r, why))
    out = os.path.join(os.path.dirname(path), "validated")
    rej = os.path.join(os.path.dirname(path), "rejected")
    os.makedirs(out, exist_ok=True)
    os.makedirs(rej, exist_ok=True)
    name = os.path.basename(path)
    with open(os.path.join(out, name), "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r, _ in ok)
    with open(os.path.join(rej, name), "w", encoding="utf-8") as f:
        f.writelines(json.dumps({**r, "reject_reason": w}, ensure_ascii=False) + "\n" for r, w in bad)
    print(f"입력 {len(rows)}줄 -> 통과 {len(ok)} / 거부 {len(bad)}")
    for r, w in bad:
        print("  거부:", w)
    print(f"고유 prompt {len({r['prompt'] for r, _ in ok})} / 고유 completion {len({r['completion'] for r, _ in ok})}")
    by_model = {}
    for r, _ in ok:
        by_model[r.get("model", "untagged(태그 도입 전)")] = by_model.get(r.get("model", "untagged(태그 도입 전)"), 0) + 1
    print("모델별 통과:", by_model)


if __name__ == "__main__":
    main()
