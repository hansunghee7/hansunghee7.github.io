#!/usr/bin/env python3
"""무균실 루프 벤치: bench/ 타겟 x N회를 임시 복사본에서 돌려 Iterations 분포를 JSONL로 남긴다.

사용: ACL_BACKEND=openrouter:<모델 id> python scripts/ops/bench_acl.py --n 8 --tag base [--extra "프롬프트 덧말"]
지표: 1회차 통과(Iterations==1) / 최종 통과(Status==PASS). 결과: .hermes/data/bench_results/<tag>.jsonl(gitignore)
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def one(target: str, run: int, extra: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        t = os.path.join(d, "t.py")
        shutil.copyfile(os.path.join(ROOT, target), t)
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "ACL_EXTRA_NOTE": extra}
        r = subprocess.run([sys.executable, os.path.join(ROOT, "actor_critic_loop.py"), "--mode", "logic", t],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                           timeout=600, creationflags=NOWIN, check=False)
    m = dict(re.findall(r"\[metric\] (\w+): (\w+)", r.stdout))
    return {"run": run, "target": target, "Iterations": int(m.get("Iterations", -1)), "Status": m.get("Status", "ERR")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--extra", default="")
    a = ap.parse_args()
    targets = sorted(os.path.relpath(p, ROOT).replace("\\", "/") for p in glob.glob(os.path.join(ROOT, "bench", "hard_*.py")))
    jobs = [(t, i) for t in targets for i in range(1, a.n + 1)]
    with ThreadPoolExecutor(int(os.environ.get("ACL_PAR", "4"))) as ex:
        rows = list(ex.map(lambda j: one(j[0], j[1], a.extra), jobs))
    out = os.path.join(ROOT, ".hermes", "data", "bench_results", f"{a.tag}.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    for t in targets:
        rs = [r for r in rows if r["target"] == t]
        print(f"{t}: 1회차 {sum(r['Iterations'] == 1 and r['Status'] == 'PASS' for r in rs)}/{len(rs)}, 최종 {sum(r['Status'] == 'PASS' for r in rs)}/{len(rs)}")
    print(f"합계: 1회차 {sum(r['Iterations'] == 1 and r['Status'] == 'PASS' for r in rows)}/{len(rows)}, 최종 {sum(r['Status'] == 'PASS' for r in rows)}/{len(rows)}")


if __name__ == "__main__":
    main()
