#!/usr/bin/env python3
"""구글 검색 연동 제미나이 리서치(Vertex AI, GCP 무료 체험 크레딧). 2026-09-26 탐.

왜: 사장님 규칙 "리서치는 구글 검색 연동 제미나이로"(9/24). AI Studio 무료 키는 검색 연동이 429,
    유료 키는 선불 미충전 402라 막힘. Vertex AI는 개인 계정 "My First Project"(결제 계정 010823, 무료 체험
    $300 크레딧)에서 검색 연동까지 200(9/26 실측, 핏의 shorts-lab tools/sheet/vertex_gemini_call.py와 같은 경로).
    결제 계정은 무료 체험이라 유료로 올리지 않는 한 크레딧 밖 청구가 없다(사장님: 결제 연동 안 함).
인증: gcloud auth print-access-token(이 PC의 gcloud 기본 계정). 키 값 없음.

사용:
  python scripts/ops/vertex_research.py "질문1" "질문2" ...        질문마다 병렬 호출
  python scripts/ops/vertex_research.py --file 질문들.txt           한 줄에 질문 하나
  --common "모든 질문 뒤에 붙일 지시"  --out 결과.json  --model gemini-3.6-flash
출력: 질문별 답(앞 600자)과 출처(제목·주소). 전체는 --out JSON.
"""
import argparse, concurrent.futures as cf, json, shutil, subprocess, sys, urllib.error, urllib.request

PROJECT = "project-e59cbc25-e96a-44f5-ac6"  # My First Project(개인 계정, 무료 체험 크레딧)
REGION = "global"  # gemini-3.6-flash는 global에서만 200(핏 9/23 실측)
DEFAULT_COMMON = "한국어로. 공식 문서 등 1차 출처 기준 사실만, 모르면 '확인 못 함'. 숫자에는 출처를 붙인다. 15줄 이내."


def token():
    return subprocess.run([shutil.which("gcloud"), "auth", "print-access-token"], capture_output=True, text=True, timeout=30, check=True).stdout.strip()


def ask(q, common, model, tok):
    url = f"https://aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}/publishers/google/models/{model}:generateContent"
    body = {"contents": [{"role": "user", "parts": [{"text": q + "\n\n" + common}]}], "tools": [{"googleSearch": {}}]}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=180).read())
    except urllib.error.HTTPError as e:
        return {"q": q, "error": f"HTTP {e.code}", "detail": e.read().decode("utf-8", "ignore")[:300]}
    c = r["candidates"][0]
    text = "".join(p.get("text", "") for p in c.get("content", {}).get("parts", []))
    src = [{"title": ch.get("web", {}).get("title"), "uri": ch.get("web", {}).get("uri")} for ch in c.get("groundingMetadata", {}).get("groundingChunks", [])]
    return {"q": q, "text": text, "sources": src}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("questions", nargs="*")
    ap.add_argument("--file")
    ap.add_argument("--common", default=DEFAULT_COMMON)
    ap.add_argument("--model", default="gemini-3.6-flash")
    ap.add_argument("--out")
    a = ap.parse_args()
    qs = list(a.questions)
    if a.file:
        qs += [l.strip() for l in open(a.file, encoding="utf-8") if l.strip()]
    if not qs:
        sys.exit(__doc__)
    tok = token()
    with cf.ThreadPoolExecutor(min(6, len(qs))) as ex:
        res = list(ex.map(lambda q: ask(q, a.common, a.model, tok), qs))
    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in res:
        print("=" * 60); print("Q:", r["q"][:120])
        if "error" in r:
            print("오류:", r["error"], r.get("detail", "")[:160]); continue
        print(r["text"][:600])
        for s in r["sources"][:5]:
            print(" -", s["title"], s["uri"][:90] if s["uri"] else "")
    sys.exit(1 if any("error" in r for r in res) else 0)


if __name__ == "__main__":
    main()
