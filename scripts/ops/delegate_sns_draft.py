#!/usr/bin/env python3
"""마야 카드 실행기: 홈페이지 글 1편 -> SNS 채널별 초안(링크드인·페이스북·인스타·스레드). Tier: Local(Ollama).

엔진은 초안 JSON만 낸다. 큐(assets/data/sns_publish_queue.json)에는 아무것도 쓰지 않는다. 마야가 읽고 고친 뒤 사장님 승인을 받는다.
검증기(코드): 봉투 스키마(채널 4개 외 키 금지) / 채널별 글자수 한도 / 괄호 없음 / 긴 줄표 없음 / 글 URL 포함·다른 URL 없음 / 원문에 없는 숫자·영문 표기 금지 / 채널 간 유사도 / 링크드인 하한 / 반말·명령형 시작 금지(마야 검토 반영). 단서 표현 소실은 경고만.
검증 실패 채널은 사유를 붙여 그 채널만 다시 시도(최대 3회). 그래도 실패하면 제안 없이 "거절"로 표시한다(마야가 직접 씀).
사용: python scripts/ops/delegate_sns_draft.py 629 [--model qwen2.5-coder:14b]
출력: 마지막 줄 JSON 지표(통과 채널, 시도 횟수, 자율 교정 횟수, 토큰, 지연). 초안 저장: .hermes/data/delegations/<시각>/sns_<번호>.json
카드: .hermes/task_cards/maya_sns_draft.md
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
# 채널별 글자수 한도(탐 기본값, 마야가 조정). 스레드 500자는 카드 명시값.
LIMITS = {"linkedin": 1500, "facebook": 1000, "instagram": 1500, "threads": 500}
HINTS = {"linkedin": "전문적이지만 담백한 어조, 문단 2~3개", "facebook": "친근한 어조, 짧은 문단",
         "instagram": "캡션 톤, 줄바꿈 활용, 해시태그 없음", "threads": "한두 문장 핵심만, 대화하듯"}
MINS = {"linkedin": 400}  # 마야 검토(2026-09-30): 상한이 아니라 하한이 없는 게 문제였다
SIMILAR = 0.6  # 채널 초안끼리 글자열 유사도가 이 값을 넘으면 반려(링크드인·페이스북이 거의 같았다)
HEDGES = ("가상의 상황", "회사마다", "공식 정의")  # 원문의 단서 표현: 하나도 남지 않으면 경고만(거칠어서 반려는 안 함)
SENT = re.compile(r"(?<=[.!?])\s+")
BAD_CHARS = "()（）"
DASHES = "—–―"
ENVELOPE = {
    "type": "object", "additionalProperties": False, "required": ["drafts"],
    "properties": {"drafts": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["channel", "text"],
        "properties": {"channel": {"enum": list(LIMITS)}, "text": {"type": "string", "minLength": 1}}}}},
}


def load_post(no: str) -> tuple[str, str, str]:
    import glob
    path = next(iter(glob.glob(os.path.join(ROOT, "log_assets", "markdown", f"{no}_*.md"))), None)
    if not path:
        sys.exit(f"{no}번 글 파일이 없습니다")
    raw = open(path, encoding="utf-8").read()
    head, body = raw.split("---\n", 2)[1], raw.split("---\n", 2)[2].strip()
    title = re.search(r'^title:\s*"?(.*?)"?\s*$', head, re.M).group(1)
    body = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", body)  # 마크다운 링크는 글자만
    return title, body, f"https://simplifier.co.kr/logs/{no}/"


def validate(channel: str, text: str, url: str, source: str) -> list[str]:
    why = []
    if len(text) > LIMITS[channel]:
        why.append(f"글자수 {len(text)}자로 한도 {LIMITS[channel]}자 초과")
    if any(c in text for c in BAD_CHARS):
        why.append("괄호 사용")
    if any(c in text for c in DASHES):
        why.append("긴 줄표 사용")
    urls = re.findall(r"https?://\S+", text)
    if url not in text:
        why.append(f"글 URL({url}) 없음")
    if [u for u in urls if u.rstrip(".,)") != url]:
        why.append("글 URL 외 다른 URL 포함")
    known = set(re.findall(r"\d+", source)) | set(re.findall(r"\d+", url))
    extra = sorted(set(re.findall(r"\d+", text)) - known)
    if extra:
        why.append(f"원문에 없는 숫자 {extra}")
    if channel in MINS and len(text) < MINS[channel]:
        why.append(f"글자수 {len(text)}자로 하한 {MINS[channel]}자 미달")
    body = text.replace(url, " ").strip()
    sents = [x.strip() for x in SENT.split(body) if x.strip()]
    plain = [re.sub(r"[.!?…\s]+$", "", x) for x in sents]
    informal = [x for x in plain if re.search(r"(자|해라|하라)$", x) or (re.search(r"[가-힣]다$", x) and not re.search(r"니다$", x))]
    if informal:
        why.append(f"반말 어미 문장(존댓말로 통일): {informal[:2]}")
    if plain and re.search(r"(세요|십시오|해라|하라|보자|봅시다)$", plain[0]):
        why.append("첫 문장이 명령형(설명하듯 시작할 것)")
    known_en = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z\-]+", source)}
    extra_en = sorted({w for w in re.findall(r"[A-Za-z][A-Za-z\-]+", body) if w.lower() not in known_en})
    if extra_en:
        why.append(f"원문에 없는 영문 표기 {extra_en}")
    return why


def warnings(channel: str, text: str, source: str) -> list[str]:
    """반려하지 않고 마야에게 알리는 경고."""
    if channel != "threads" and any(h in source for h in HEDGES) and not any(h in text for h in HEDGES):
        return ["원문의 단서 표현(가상의 상황·회사마다·공식 정의 중 하나)이 초안에 남지 않음: 단정문으로 읽힐 수 있음"]
    return []


def similar_to_passed(text: str, passed: dict) -> str:
    from difflib import SequenceMatcher
    for c, t in passed.items():
        r = SequenceMatcher(None, text, t).ratio()
        if r > SIMILAR:
            return f"{c} 초안과 글자열 유사도 {r:.2f}로 {SIMILAR} 초과: 채널 성격에 맞게 문장 구성을 다르게 쓸 것"
    return ""


def ask(prompt: str, model: str) -> tuple[str, int, int]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "OLLAMA_JSON": "1", "OLLAMA_NUM_CTX": "16384", "OLLAMA_NUM_PREDICT": "3000"}
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "ops", "ollama_ask.py"), model], input=prompt, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env, timeout=600, creationflags=NOWIN, check=False)
    u = re.search(r"USAGE (\d+) (\d+)", r.stderr)
    return r.stdout, int(u.group(1)) if u else 0, int(u.group(2)) if u else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("post_no")
    ap.add_argument("--model", default="qwen2.5-coder:14b")
    a = ap.parse_args()
    title, body, url = load_post(a.post_no)
    if len(body) > 4000:
        sys.exit("입력이 4000자를 넘습니다(카드 한도)")
    source = f"{title}\n{body}"
    passed, notes, rejected_why = {}, {}, {}
    m = {"post": a.post_no, "model": a.model, "attempts": 0, "envelope_violations": 0, "warnings": {}, "tokens": {"in": 0, "out": 0}}
    t0 = time.time()
    for attempt in range(3):
        todo = [c for c in LIMITS if c not in passed]
        if not todo:
            break
        m["attempts"] += 1
        spec = "\n".join(f"- {c}: {LIMITS[c]}자 이내, {HINTS[c]}" for c in todo)
        fb = "".join(f"\n[{c} 이전 시도 거절 사유] {'; '.join(w)}" for c, w in notes.items() if c in todo)
        prompt = (f"아래 블로그 글을 SNS 채널별 초안으로 바꿔라. 글 내용에 없는 사실·숫자를 만들지 마라. 괄호와 긴 줄표를 쓰지 마라. "
                  f"모든 문장을 존댓말(입니다·합니다체)로 통일하고, 첫 문장을 명령형(알아보세요, 확인하세요)으로 시작하지 마라. 원문에 없는 영문 약어 풀이를 추가하지 마라. "
                  f"원문이 조심스럽게 말한 대목(가상의 상황, 회사마다 다름, 공식 정의 아님)은 단정문으로 바꾸지 말고 단서를 남겨라. 채널끼리 문장 구성이 겹치지 않게 각 채널 성격에 맞게 다르게 써라. "
                  f"각 초안 끝에 이 URL을 그대로 한 번 넣어라: {url}\n채널별 조건:\n{spec}{fb}\n\n"
                  f'출력은 JSON 하나만: {{"drafts":[{{"channel":"...","text":"..."}}]}}. 요청한 채널만, 다른 키 금지.\n\n'
                  f"## 제목\n{title}\n\n## 본문\n{body}")
        out, tin, tout = ask(prompt, a.model)
        if os.environ.get("SNS_DUMP"):  # 디버그: 엔진 원문 응답 보관
            open(os.environ["SNS_DUMP"], "a", encoding="utf-8").write(out + "\n=====\n")
        m["tokens"]["in"] += tin
        m["tokens"]["out"] += tout
        try:
            data = json.loads(out)
            jsonschema.validate(data, ENVELOPE)
            got = [d["channel"] for d in data["drafts"]]
            if set(got) - set(todo) or len(got) != len(set(got)):
                raise jsonschema.ValidationError("요청하지 않은 채널 또는 중복 채널")
        except (ValueError, jsonschema.ValidationError):
            m["envelope_violations"] += 1
            continue
        for d in data["drafts"]:
            why = validate(d["channel"], d["text"], url, source)
            sim = similar_to_passed(d["text"], passed) if d["channel"] != "threads" else ""  # 스레드는 짧은 요약이라 제외
            if sim:
                why.append(sim)
            if why:
                notes[d["channel"]] = why
            else:
                passed[d["channel"]] = d["text"]
                notes.pop(d["channel"], None)
                warn = warnings(d["channel"], d["text"], source)
                if warn:
                    m["warnings"][d["channel"]] = warn
    m["latency_s"] = round(time.time() - t0, 1)
    m["passed_channels"] = sorted(passed)
    m["rejected"] = {c: notes.get(c, ["봉투 위반 또는 응답 없음"]) for c in LIMITS if c not in passed}
    m["self_corrections"] = max(m["attempts"] - 1, 0)
    out_dir = os.path.join(ROOT, ".hermes", "data", "delegations", time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"sns_{a.post_no}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"post": a.post_no, "status": "draft", "drafts": [{"channel": c, "text": passed[c]} for c in LIMITS if c in passed],
                   "rejected": m["rejected"], "warnings": m["warnings"]}, f, ensure_ascii=False, indent=2)
    m["saved"] = os.path.relpath(path, ROOT).replace("\\", "/")
    print(json.dumps(m, ensure_ascii=False))


if __name__ == "__main__":
    main()
