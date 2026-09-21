#!/usr/bin/env python3
"""구PC 야간 수집기: 남는 Groq 무료 토큰으로 필요한 조사 질문을 돌리고, 인용을 코드로 대조한다(2026-09-21).

역할 분담(무료 엔진은 수집·측정까지, 판정은 안 한다):
  1. groq/compound(웹 검색 내장 모델)가 질문마다 `주장 | URL | 원문 인용` 줄을 낸다.
  2. 이 스크립트가 각 URL을 실제로 내려받아 인용이 원문에 들어 있는지 문자열로 대조한다(AI 아님).
     - 같은 날 시험에서 compound-mini는 존재하지 않는 URL과 틀린 경로를 지어냈고 compound는 맞았다.
       그래서 모델 말을 그대로 믿지 않고 대조 결과(일치/불일치/열람 실패)를 항상 같이 남긴다.
  3. 채택 여부 판정은 사람과 탐이 한다. 결과 파일에는 "검증 단계 미실행(제미나이 대조 없음)"을 적는다.

신PC가 꺼져 있어도 구PC 혼자 끝까지 도는지(단독 가동)를 보려고 시작 때 신PC 응답 여부를 기록한다.
사용: night_research.py <질문 JSON> [출력 폴더]   (기본 출력 ~/ops/research)
max_tokens는 900이 상한이다(1800이면 413 request_too_large, 2026-09-21 실측). 토큰 한도(429)에 걸리면 남은 질문을 건너뛰고 어디까지 했는지 기록한 채 정상 종료한다.
이어하기: 질문마다 결과를 data/<이름>/<id>.json에 저장한다. 다시 실행하면 이미 끝난 질문은 건너뛰고 남은 것만 한다
(2026-09-21 사장님 지시: 밤에 토큰이 모자라 못 한 건은 다음날 00:00에 한 번 더 돌려 채운다). 보고서는 매번 전체를 다시 만든다.
"""
import ipaddress
import json
import os
import re
import socket
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import urlparse

from openai import APIStatusError, OpenAI, RateLimitError

KST = timezone(timedelta(hours=9))
MODEL = "groq/compound"
ENV_PATH = os.path.expanduser("~/hermes-agent/.env")
SHIN_PC = ("172.30.1.33", (22, 11434))

SYSTEM = (
    "너는 근거 수집 도우미다. 웹 검색으로 페이지를 실제로 열어 확인한 내용만 쓴다. "
    "출력은 한 줄에 하나씩 `주장 | URL | 원문 인용` 형식만 쓴다(설명·서론·표 금지). "
    "원문 인용은 그 페이지에 실제로 있는 문장을 언어 바꾸지 않고 그대로, 15단어 이내로 쓴다(따옴표 없이). "
    "열지 못한 페이지는 `열람 실패 | URL | -` 로 쓴다. 검색 요약만 보고 인용하지 않는다. "
    "출처 없는 일반 지식, 추측, 수치 지어내기 금지. 근거가 없으면 `근거 못 찾음 | - | -` 한 줄만 쓴다."
)


def load_env(path):
    env = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def shin_pc_up():
    for port in SHIN_PC[1]:
        try:
            with socket.create_connection((SHIN_PC[0], port), timeout=2):
                return True
        except OSError:
            continue
    return False


def parse_claims(text):
    """`주장 | URL | 인용` 줄만 뽑는다. 형식이 틀린 줄은 버린다."""
    out = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.strip().lstrip("-*• ").split("|")]
        if len(parts) >= 3:
            out.append({"claim": parts[0], "url": parts[1], "quote": " | ".join(parts[2:]).strip()})
    return out


def is_public_https(url):
    """모델이 낸 URL을 내려받기 전에 https + 공인 주소만 허용한다(사설망·내부 주소 접근 방지)."""
    u = urlparse(url)
    if u.scheme != "https" or not u.hostname:
        return False
    try:
        for info in socket.getaddrinfo(u.hostname, 443):
            if not ipaddress.ip_address(info[4][0]).is_global:
                return False
    except (OSError, ValueError):
        return False
    return True


def norm(s):
    s = unescape(re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I))
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[‘’“”\"'`*_]", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


_page_cache = {}


def fetch_text(url):
    if url not in _page_cache:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research-verifier)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            _page_cache[url] = norm(r.read(3_000_000).decode("utf-8", "replace"))
    return _page_cache[url]


def verify(claim):
    """(상태, 설명). 인용이 페이지 본문에 그대로 있으면 일치."""
    if claim["url"] in ("-", "") or claim["claim"].startswith(("근거 못 찾음", "열람 실패")):
        return "제외", "근거 없음 또는 모델이 열람 실패라고 답함"
    if not is_public_https(claim["url"]):
        return "제외", "https 공인 주소가 아니라 내려받지 않음"
    q = norm(claim["quote"]).rstrip(". ")
    if len(q) < 12 or "..." in claim["quote"] or "…" in claim["quote"]:
        return "확인불가", "인용이 너무 짧거나 생략 표기가 있어 대조 못 함"
    try:
        page = fetch_text(claim["url"])
    except Exception as e:
        return "열람실패", type(e).__name__
    return ("일치", "원문에 그대로 있음") if q in page else ("불일치", "원문에 이 인용이 없음(번역·요약이거나 지어냈을 수 있음)")


def ask(client, question, tries=3):
    for i in range(tries):
        try:
            r = client.chat.completions.create(
                model=MODEL, temperature=0.1, max_tokens=900,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}])
            return r.choices[0].message.content or "", r.usage.total_tokens
        except RateLimitError as e:
            msg = str(e)
            if "per day" in msg or "TPD" in msg:
                raise
            time.sleep(20 * (i + 1))  # 분당 한도는 잠깐 쉬면 풀린다
        except APIStatusError as e:
            # 413 request_too_large: compound가 내부에서 큰 페이지를 읽어 한 요청이 커질 때(같은 질문이 다시 하면 통과하기도 함)
            if e.status_code != 413:
                raise
            time.sleep(30 * (i + 1))
    raise RuntimeError("분당 한도·413 재시도 초과")


def result_path(out_dir, name, qid):
    return os.path.join(out_dir, "data", name, f"{qid}.json")


def load_results(out_dir, name, spec):
    got = {}
    for item in spec["questions"]:
        p = result_path(out_dir, name, item["id"])
        if os.path.exists(p):
            got[item["id"]] = json.load(open(p, encoding="utf-8"))
    return got


def build_report(spec, results, runs, name):
    stat = {}
    for r in results.values():
        for row in r["rows"]:
            stat[row[0]] = stat.get(row[0], 0) + 1
    pending = [q["id"] for q in spec["questions"] if q["id"] not in results]
    total = sum(r["tokens"] for r in results.values())
    lines = [f"# 구PC 야간 수집 결과 ({name})", "",
             f"- 질문 {len(spec['questions'])}개 중 {len(results)}개 완료" + (f", **남음 {', '.join(pending)}**" if pending else ", 전부 완료"),
             f"- 사용 토큰 합계 약 {total:,} (모델 {MODEL})",
             "- 인용 대조(코드가 URL을 내려받아 문자열 대조): " + (", ".join(f"{k} {v}" for k, v in sorted(stat.items())) or "대상 없음"),
             "- **검증 단계 미실행**(제미나이 출처 대조 없음). 채택·판정은 하지 않았음. `일치`도 그 페이지에 그 문장이 있다는 뜻일 뿐 주장이 옳다는 뜻은 아님.",
             "", "## 실행 기록", "", "| 시작 | 끝 | 신PC(시작 시) | 이번에 끝낸 질문 | 중단 사유 |", "|---|---|---|---|---|"]
    for r in runs:
        lines.append(f"| {r['started']} | {r['finished']} | {'켜져 있음' if r['shin_pc_up'] else '꺼져 있음(구PC 단독 가동)'} | {', '.join(r['done_ids']) or '-'} | {r['stop_reason'] or '-'} |")
    lines.append("")
    group = None
    cell = lambda t: str(t).replace("|", "/").replace("\n", " ")[:220]
    for item in spec["questions"]:
        r = results.get(item["id"])
        if not r:
            continue
        if item["group"] != group:
            group = item["group"]
            lines += [f"## {group}", ""]
        lines += [f"### {item['id']}. {item['q'][:80]}", "", f"(토큰 {r['tokens']:,})", "",
                  "| 대조 | 주장 | URL | 인용 | 비고 |", "|---|---|---|---|---|"]
        for st, claim, url, quote, why in r["rows"]:
            lines.append(f"| {st} | {cell(claim)} | {cell(url)} | {cell(quote)} | {why} |")
        if not r["rows"]:
            lines.append("| - | (형식에 맞는 줄이 없음) 원문 응답 앞부분 | - | " + cell(r["raw"][:200]) + " | - |")
        lines.append("")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    name = spec.get("name", "research")
    out_dir = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else "~/ops/research")
    os.makedirs(os.path.join(out_dir, "data", name), exist_ok=True)
    started = datetime.now(KST)
    shin_before = shin_pc_up()
    client = OpenAI(api_key=load_env(ENV_PATH)["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")

    results = load_results(out_dir, name, spec)
    done_ids, stop_reason = [], ""
    for item in spec["questions"]:
        if item["id"] in results or stop_reason:
            continue
        try:
            text, tokens = ask(client, item["q"])
        except RateLimitError as e:
            stop_reason = "일일 토큰 한도(429): " + str(e)[:160]
            continue
        except Exception as e:
            stop_reason = f"오류로 중단: {type(e).__name__} {str(e)[:200]}"
            continue
        rows = []
        for c in parse_claims(text):
            st, why = verify(c)
            rows.append([st, c["claim"], c["url"], c["quote"], why])
        rec = {"id": item["id"], "tokens": tokens, "rows": rows, "raw": text, "at": datetime.now(KST).isoformat(timespec="seconds")}
        json.dump(rec, open(result_path(out_dir, name, item["id"]), "w", encoding="utf-8"), ensure_ascii=False)
        results[item["id"]] = rec
        done_ids.append(item["id"])

    runs_path = os.path.join(out_dir, "data", name, "runs.json")
    runs = json.load(open(runs_path, encoding="utf-8")) if os.path.exists(runs_path) else []
    runs.append({"started": f"{started:%m-%d %H:%M}", "finished": f"{datetime.now(KST):%m-%d %H:%M}", "shin_pc_up": shin_before,
                 "done_ids": done_ids, "stop_reason": stop_reason})
    json.dump(runs, open(runs_path, "w", encoding="utf-8"), ensure_ascii=False)
    path = os.path.join(out_dir, f"{name}.md")
    open(path, "w", encoding="utf-8").write(build_report(spec, results, runs, name))
    pending = [q["id"] for q in spec["questions"] if q["id"] not in results]
    print(f"OK {path} 완료 {len(results)}/{len(spec['questions'])} 이번 {len(done_ids)}개 남음 {pending} {stop_reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
