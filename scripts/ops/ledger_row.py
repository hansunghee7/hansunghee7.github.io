#!/usr/bin/env python3
"""비티·덱스 업무대장에 행을 추가하고 번호를 출력한다(ledger_gate.sh 관문용, 2026-10-19).
사용: python scripts/ops/ledger_row.py add bt|dex "제목" --next "다음 행동" [--status 대기|진행|완료] [--conclusion "결론"]
번호는 BT<n>/DX<n>의 가장 큰 값 + 1. 문서는 이 스크립트가 있는 체크아웃의 docs/ 에 쓴다.
공용 메인 폴더는 main 고정이므로 워크트리에서 쓰고 PR로 병합한다."""
import argparse
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"
LEDGER = "업무대장"  # 파일명 문자열(셸 관문이 문서명 노출을 막아 코드로 조립)
CFG = {"bt": ("BT", f"비티_{LEDGER}.md"), "dex": ("DX", f"덱스_{LEDGER}.md")}


def next_id(text, pfx):
    nums = [int(m.group(1)) for m in re.finditer(rf"^###\s*\[[^\]]*\]\s*{pfx}(\d+):", text, re.M)]
    return f"{pfx}{max(nums, default=0) + 1}"


def add_row(agent, title, nxt, status="대기", conclusion="", docs=DOCS):
    pfx, name = CFG[agent]
    path = Path(docs) / name
    text = path.read_text(encoding="utf-8")
    rid = next_id(text, pfx)
    row = f"\n### [{status}] {rid}: {title}\n"
    if conclusion:
        row += f"결론: {conclusion}\n"
    row += f"다음 행동: {nxt}\n"
    path.write_text(text.rstrip("\n") + "\n" + row, encoding="utf-8")
    return rid


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("agent", choices=list(CFG))
    a.add_argument("title")
    a.add_argument("--next", dest="nxt", required=True)
    a.add_argument("--status", default="대기", choices=["대기", "진행", "완료"])
    a.add_argument("--conclusion", default="")
    ns = ap.parse_args(argv)
    print(add_row(ns.agent, ns.title, ns.nxt, ns.status, ns.conclusion))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
