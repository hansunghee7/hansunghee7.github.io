# -*- coding: utf-8 -*-
"""문서 구조 전수 스캔(2026-10-15 탐, 사장님: "크레딧도 많은데 컨텍스트 에이전트에게 우리 문서구조 쫙 한번 스캔해 달라").
1단계(스크립트, 토큰 0): 저장소별 마크다운 목록과 신호(줄 수, 마지막 수정, 30일 수정 횟수, 언급받는 수, '정본·최신·폐기' 같은 말 개수, 첫 제목, 앞부분)를 모은다.
2단계(감수 에이전트 = 오퍼스, api_run.py): 파일마다 사실 종류(상태·결정·규칙·이력·생성뷰·혼합)와 검색 층(1·2·3차), 처리(정본 유지·생성뷰로·이력으로·통합·가리키는 줄로)를 판정하고,
같은 사실이 여러 곳에 있는 묶음과 먼저 바꿀 순서를 낸다. 제안만 만든다(실행은 판정 뒤 context_apply 계열이 맡는다).
사용: python scripts/ops/doc_structure_scan.py [--dry] [--model claude-opus-5-5]
결과: C:/work/_ops/context_audit/docscan_YYYYMMDD_HHMM.md (재료 inv_*.md 같이 남김)"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path("C:/work/_ops/context_audit")
REPOS = {
    "공개 저장소": (Path("C:/work/hansunghee7.github.io"), r"^(CLAUDE\.md|docs/.*\.md|\.claude/(skills|rules|agents)/.*\.md|scripts/.*\.md)$"),
    "숏폼(shorts-lab)": (Path("C:/work/shorts-lab"), r"^(?!channels/.*/episodes/).*\.md$"),
}
WORDS = {"정본": r"정본", "최신": r"최신", "폐기": r"폐기|대체됨|무효|옛 ", "사고": r"사고"}
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def git(repo, *a):
    r = subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(repo), *a], capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=FLAGS)
    return r.stdout


def inventory():
    rows = []
    graph = {}
    try:
        g = json.loads(Path("C:/work/_ops/context_graph.json").read_text(encoding="utf-8"))["edges"]
        for src, dsts in g.items():
            for d in dsts:
                graph[d] = graph.get(d, 0) + 1
    except (OSError, ValueError, KeyError):
        pass
    since = time.strftime("%Y-%m-%d", time.localtime(time.time() - 30 * 86400))
    for name, (repo, pat) in REPOS.items():
        if not repo.exists():
            continue
        recent = {}
        for ln in git(repo, "log", f"--since={since}", "--name-only", "--format=").splitlines():
            if ln.endswith(".md"):
                recent[ln] = recent.get(ln, 0) + 1
        for f in git(repo, "ls-files").splitlines():
            if not re.match(pat, f):
                continue
            p = repo / f
            try:
                t = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            last = git(repo, "log", "-1", "--format=%ad", "--date=short", "--", f).strip()
            head = next((x.strip("# ").strip() for x in t.splitlines() if x.startswith("#")), "")
            cnt = " ".join(f"{k}{len(re.findall(v, t))}" for k, v in WORDS.items())
            body = re.sub(r"\s+", " ", t)[:260]
            rows.append(f"- [{name}] {f} | {len(t.splitlines())}줄 | 마지막 {last} | 30일 수정 {recent.get(f, 0)} | 언급받음 {graph.get(f, 0)} | {cnt} | 제목: {head[:60]} | 앞부분: {body}")
    return rows


PROMPT = """너는 컨텍스트 감수 에이전트다. 1인 회사(사장님 1명 + AI 에이전트 5명: 탐=인프라, 핏=숏폼, 마야=SNS, 지투=제품, 노트=개발)의 문서 구조 전체를 판정한다.
회사의 문제: 같은 사실이 여러 문서에 복사돼 서로 달라지고, 바뀐 결정의 옛 버전이 정본 자리에 남아, 에이전트가 낡은 사본을 먼저 읽고 틀린 설명을 한다(예: 10/15 핏이 완성된 편을 10/14 보류 문서를 보고 '보류'라고 설명).
사장님 원칙: 최신 결정만 정본으로 남고, 그 전 정보는 히스토리로 간다. 찾아야 하는 것은 찾기 쉽게, 혼란스럽게 만드는 정보는 찾기 어렵게. 옮기는 일은 전체를 보는 에이전트가 한다.
지금 설계(페이블 제안): 사실을 5종으로 나눠 한 곳에만 쓴다. 상태=사건 기록(jsonl·DB, 마지막 사건이 현재), 결정=사장님 말 원장, 규칙·절차=공정 카드(DB), 이력=git·비공개 저장소·_이력/ 폴더, 생성뷰=_생성뷰/*.view.md(손대지 않음). 검색 층: 1차=공정 카드+최신 결정+상태 마지막 사건, 2차=정본 문서, 3차=이력·생성뷰.
아래는 두 저장소의 마크다운 전체 목록과 신호다(언급받음 = 다른 파일이 이 파일을 가리키는 수).

출력(한국어, 150줄 이내, 근거는 파일 경로로):
1. 한 줄 진단과 숫자 요약(종류별 파일 수, 섞인 문서 수, 3차로 내려야 할 수).
2. 혼합 문서 상위 10개: 파일 / 섞인 종류 / 쪼개는 법(어느 부분을 어디로).
3. 같은 사실이 여러 곳에 있는 묶음 5~10개: 사실 / 파일들 / 정본으로 둘 하나 / 나머지 처리.
4. 3차로 내릴 것(이력·생성뷰·폐기) 목록: 파일 / 이유 / 갈 곳. 확신 있는 것만.
5. 1차·2차에 올려야 하는데 묻혀 있는 것.
6. 먼저 바꿀 순서 5단계: 단계마다 무엇을, 누가(에이전트 이름), 되돌리기 쉬운지, 효과 측정.
7. DB로 옮겨야 할 문서(사장님 10/15 "문서 중 DB화가 필요한 것도 쭉"): 표·목록·상태·대장처럼 행 단위로 바뀌는 데이터를 md로 들고 있는 파일. 파일 / 담긴 데이터 / 옮길 곳(기존 opsdb tasks 구역·fit_* 표·새 표 중) / 옮긴 뒤 md는 생성뷰로 둘지 없앨지 / 우선순위(혼란 위험·갱신 빈도) / 담당 에이전트. 이미 DB가 정본이고 md가 사본인 것은 따로 표시. 상위 15개까지.
8. 하지 말 것 3개와 판단 한계.
마지막에 ```actions 블록으로 JSON 배열: 원소 = {{"op":"move","file":"저장소 상대 경로","repo":"공개 저장소|숏폼(shorts-lab)","to":"_이력/ 또는 _생성뷰/ 등","why":"한 줄"}}. 지금 바로 옮겨도 깨질 참조가 없고 확신 있는 것만, 최대 15개.

[목록 {n}개]
{inv}
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    model = a[a.index("--model") + 1] if "--model" in a else "claude-opus-5-5"
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M")
    rows = inventory()
    inv = OUT / f"inv_{stamp}.md"
    inv.write_text("\n".join(rows), encoding="utf-8")
    q = OUT / f"docscan_q_{stamp}.md"
    q.write_text(PROMPT.format(n=len(rows), inv="\n".join(rows)), encoding="utf-8")
    print(f"목록 {len(rows)}개, 질문 {q.stat().st_size // 1000}KB → {q}")
    if "--dry" in a:
        return 0
    o = OUT / f"docscan_{stamp}.md"
    r = subprocess.run([sys.executable, str(HERE / "api_run.py"), "--who", "컨텍스트감수", "--model", model, "--prompt-file", str(q), "--max-tokens", "16000", "--timeout", "1500", "--out", str(o)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=FLAGS)
    if r.returncode != 0 or not o.exists():
        print("문서 구조 스캔 실패: " + (r.stderr or r.stdout)[-300:])
        return 2
    # 출력 상한(16000)에서 잘리면 이어 쓰기 한 번(10/15 첫 실행이 6절에서 잘림)
    first = o.read_text(encoding="utf-8")
    if "```actions" not in first:
        q2 = OUT / f"docscan_q2_{stamp}.md"
        q2.write_text(q.read_text(encoding="utf-8") + "\n\n[너의 앞선 답(출력 상한에서 잘림)]\n" + first
                      + "\n\n위 답의 잘린 지점부터 이어서, 남은 절과 맨 끝 ```actions 블록까지 써라. 앞부분은 반복하지 마라.", encoding="utf-8")
        o2 = OUT / f"docscan_cont_{stamp}.md"
        r2 = subprocess.run([sys.executable, str(HERE / "api_run.py"), "--who", "컨텍스트감수", "--model", model, "--prompt-file", str(q2), "--max-tokens", "16000", "--timeout", "1500", "--out", str(o2)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=FLAGS)
        if r2.returncode == 0 and o2.exists():
            o.write_text(first + "\n" + o2.read_text(encoding="utf-8"), encoding="utf-8")
    o.write_text(o.read_text(encoding="utf-8") + "\n\n" + refcheck(o.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"문서 구조 스캔 완료: {o}")
    return 0


def refcheck(text):
    """이동 제안마다 저장소 전체(스크립트·워크플로·훅 포함)에서 경로·파일 이름 참조를 센다(10/15: 오퍼스가 '언급 0'이라 한 4개 중 3개가 스크립트 참조)."""
    m = re.search(r"```actions\s*(\[.*?\])\s*```", text, re.S)
    try:
        acts = json.loads(m.group(1)) if m else []
    except ValueError:
        return "## 참조 검사\n(actions 블록을 읽지 못함)"
    lines = ["## 참조 검사(스크립트·워크플로 포함, 옮기기 전 필수)"]
    for x in acts:
        repo = REPOS.get(x.get("repo", ""), (None,))[0]
        f = x.get("file", "")
        if not repo or not f:
            continue
        stem = Path(f).stem
        hits = [h for h in git(repo, "grep", "-l", "-F", stem).splitlines() if h != f and "아카이브" not in h and "_이력/" not in h]
        lines.append(f"- {'안전' if not hits else '참조 있음'}: {f}" + (f" ← {', '.join(hits[:4])}" if hits else ""))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
