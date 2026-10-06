#!/usr/bin/env python3
"""구글 검색 연동 제미나이 리서치(무료 AI Studio 키 먼저, 막히면 Vertex AI 무료 크레딧). 2026-09-26 탐, 10/3 순서 보정.

경로(사장님 합의 2026-10-03, 정본 docs/제미나이_키_정책.md): ① 무료 AI Studio 키(키 대장의 일반 키, 값은 화면에 안 냄)로 먼저
    호출하고, 429·한도·차단이면 ② 개인 GCP 무료 크레딧(Vertex)으로 넘어간다. --route free|vertex|auto(기본 auto).
    어느 경로로 나갔는지는 stderr 한 줄과 research_log.jsonl의 route 칸에 남는다.

왜: 사장님 규칙 "리서치는 구글 검색 연동 제미나이로"(9/24). AI Studio 무료 키는 검색 연동이 429,
    유료 키는 선불 미충전 402라 막힘. Vertex AI는 개인 계정 "My First Project"(결제 계정 010823, 무료 체험
    $300 크레딧)에서 검색 연동까지 200(9/26 실측, 핏의 shorts-lab tools/sheet/vertex_gemini_call.py와 같은 경로).
    결제 계정은 무료 체험이라 유료로 올리지 않는 한 크레딧 밖 청구가 없다(사장님: 결제 연동 안 함).
인증: gcloud auth print-access-token(이 PC의 gcloud 기본 계정). 키 값 없음.

강제 규칙(사장님 9/26 "질문할 내용을 한방에 모아서 던져서 답을 얻고 부족한 것 더 조사하는 형태로 강제"):
  - 질문이 몇 개든 API는 한 번만 부른다(번호 붙여 한 요청으로 묶음). 질문마다 따로 부르지 않는다.
  - 주제(--topic)마다 24시간 안에 첫 조사 1회 + 보충(--followup) 1회까지. 첫 조사 뒤에는 --followup 없이 못 부른다.
  - 그 이상은 --more "이유"가 있어야 한다(기록에 남음). 기록: C:/work/_ops/research_log.jsonl

사용:
  python vertex_research.py --topic "carvit 도메인" "질문1" "질문2" "질문3"          첫 조사: 궁금한 것 전부 한 번에
  python vertex_research.py --topic "carvit 도메인" --followup "모자란 것1" "모자란 것2"  보충 조사 1회
  --file 질문들.txt(한 줄에 하나)  --common "공통 지시"  --out 결과.json  --model gemini-3.6-flash
출력: 질문별 답과 출처(제목·주소). 전체는 --out JSON.
"""
import argparse, json, os, shutil, subprocess, sys, time, urllib.error, urllib.request

sys.path.insert(0, "C:/work/hansunghee7.github.io/scripts/ops")  # 키 대장(gemini_fast): 키 값은 메모리에서만 쓴다

PROJECT = "project-e59cbc25-e96a-44f5-ac6"  # My First Project(개인 계정, 무료 체험 크레딧)
REGION = "global"  # gemini-3.6-flash는 global에서만 200(핏 9/23 실측)
LOG = os.environ.get("RESEARCH_LOG", "C:/work/_ops/research_log.jsonl")
DEFAULT_COMMON = "한국어로. 공식 문서 등 1차 출처 기준 사실만, 모르면 '확인 못 함'. 숫자에는 출처를 붙인다. 질문마다 15줄 이내."
NL = chr(10)


def token():
    return subprocess.run([shutil.which("gcloud"), "auth", "print-access-token"], capture_output=True, text=True, timeout=30, check=True).stdout.strip()


def build(qs, common):
    numbered = NL.join(f"Q{i}. {q}" for i, q in enumerate(qs, 1))
    prompt = f"아래 질문 {len(qs)}개에 모두 답하라. 질문마다 '## Q번호' 머리를 달고 번호 순서대로 쓴다.{NL}{NL}{numbered}{NL}{NL}{common}"
    return {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "tools": [{"googleSearch": {}}]}


def parse(r):
    c = r["candidates"][0]
    text = "".join(p.get("text", "") for p in c.get("content", {}).get("parts", []))
    src = [{"title": ch.get("web", {}).get("title"), "uri": ch.get("web", {}).get("uri")} for ch in c.get("groundingMetadata", {}).get("groundingChunks", [])]
    return {"text": text, "sources": src, "usage": r.get("usageMetadata", {})}


def post(url, headers, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={**headers, "Content-Type": "application/json"})
    try:
        return parse(json.loads(urllib.request.urlopen(req, timeout=300).read()))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "code": e.code, "detail": e.read().decode("utf-8", "ignore")[:300]}


def ask_free(qs, common, model):
    """① 무료 AI Studio 키(대장의 키들, 오늘 호출이 적은 순). 429·403(한도·차단)이면 다음 키, 다 막히면 에러를 돌려준다."""
    try:
        import gemini_fast as g
        day = g.read_counter().get(g.today_pt(), {})
        keys = sorted(g.load_keys(), key=lambda k: day.get(k["fp"], {}).get("calls", 0))
    except Exception as e:  # 키 대장을 못 읽으면 무료 경로 없음 -> Vertex로
        return {"error": "키 대장 읽기 실패", "code": 0, "detail": str(e)[:200]}
    last = {"error": "무료 키 없음", "code": 0}
    for k in keys:
        t = time.time()
        res = post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                   {"x-goog-api-key": k["value"]}, build(qs, common))
        g.bump(k["fp"], "error" not in res, round(time.time() - t, 1))
        if "error" not in res:
            return res
        last = res
        if res.get("code") not in (429, 403, 503):  # 한도·차단·과부하가 아니면 키를 바꿔도 소용없음
            break
    return last


def ask_vertex(qs, common, model):
    """② GCP 무료 크레딧(Vertex AI). 회사 프로젝트 먼저, 402·403·429 등으로 막히면 개인 프로젝트(ask_vertex.py와 같은 순서)."""
    body = build(qs, common)
    try:
        import ask_vertex as av
        ctok = av.token(av.COMPANY_ACCOUNT)  # 로그인 만료면 빈 문자열 -> 개인으로
        if ctok:
            res = post(f"https://aiplatform.googleapis.com/v1/projects/{av.COMPANY_PROJECT}/locations/{REGION}/publishers/google/models/{model}:generateContent",
                       {"Authorization": "Bearer " + ctok}, body)
            if "error" not in res:
                return {**res, "project": "company"}
            print(f"[경로] 회사 프로젝트 실패({res['error']}), 개인 프로젝트로", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"[경로] 회사 프로젝트 건너뜀({type(e).__name__})", file=sys.stderr)
    url = f"https://aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}/publishers/google/models/{model}:generateContent"
    try:
        return {**post(url, {"Authorization": "Bearer " + token()}, body), "project": "personal"}
    except Exception as e:  # noqa: BLE001  gcloud 토큰 실패 등
        return {"error": type(e).__name__, "code": 0, "detail": str(e)[:200]}


def ask_nosearch(qs, common):
    """③ 마지막 폴백: 검색 연동 없는 무료 호출(gemini_fast: 라우터·키 풀). 답 맨 위에 '검색 없음'을 표시한다."""
    try:
        import gemini_fast as g
        q = build(qs, common)["contents"][0]["parts"][0]["text"]
        r = g.ask(q)
    except Exception as e:  # noqa: BLE001
        return {"error": "무료 폴백 실패", "code": 0, "detail": str(e)[:200]}
    if not r.get("ok"):
        return {"error": "무료 폴백 실패", "code": 0, "detail": str(r.get("status"))}
    return {"text": "[검색 없음: 구글 검색 연동 불가, 모델 지식으로만 답함]" + NL + NL + r.get("text", ""), "sources": [], "usage": {}}


def ask_batch(qs, common, model, route="auto"):
    """질문 여러 개를 번호 붙여 한 요청으로. 무료 키 먼저, 한도 오류면 Vertex. 결과에 route를 붙인다."""
    if route in ("free", "auto"):
        res = ask_free(qs, common, model)
        if "error" not in res:
            return {**res, "route": "free"}
        print(f"[경로] 무료 키 실패({res['error']}), " + ("Vertex로 넘어갑니다" if route == "auto" else "끝"), file=sys.stderr)
        if route == "free":
            return {**res, "route": "free"}
    res = ask_vertex(qs, common, model)
    if "error" in res and res.get("code") in (0, 401, 402, 403, 429, 500, 503) and not os.environ.get("VERTEX_NO_FAILOVER"):
        print(f"[경로] Vertex 실패({res['error']}), 검색 없는 무료 호출로", file=sys.stderr)
        fb = ask_nosearch(qs, common)
        if "error" not in fb:
            return {**fb, "route": "free-nosearch"}
    return {**res, "route": "vertex"}


def recent(topic):
    if not os.path.exists(LOG):
        return []
    now, out = time.time(), []
    for line in open(LOG, encoding="utf-8"):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("topic") == topic and e.get("ok") and now - e.get("ts", 0) < 86400:
            out.append(e)
    return out


def gate(topic, n_q, followup, more):
    """API를 부르기 전에 판정. 막으면 안내문, 통과면 None."""
    done = recent(topic)
    if done and not followup and not more:
        return f"[리서치 관문] '{topic}'은 24시간 안에 이미 조사했습니다({len(done)}회). 결과를 읽고 모자란 것만 모아 --followup으로 한 번에 물으세요."
    if len(done) >= 2 and not more:
        return f"[리서치 관문] '{topic}'은 첫 조사+보충까지 끝났습니다. 더 부르려면 --more \"이유\"를 적으세요(기록에 남음)."
    if followup and not done:
        return f"[리서치 관문] '{topic}'의 첫 조사가 없습니다. --followup 없이 궁금한 것을 전부 모아 먼저 물으세요."
    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("questions", nargs="*")
    ap.add_argument("--file")
    ap.add_argument("--common", default=DEFAULT_COMMON)
    ap.add_argument("--model", default="gemini-3.6-flash")
    ap.add_argument("--out")
    ap.add_argument("--topic", help="조사 주제 이름(같은 주제는 첫 조사+보충 1회까지)")
    ap.add_argument("--followup", action="store_true", help="첫 조사 뒤 모자란 것 보충(1회)")
    ap.add_argument("--more", default="", help="보충 뒤에도 더 부를 때 이유")
    ap.add_argument("--route", choices=("auto", "free", "vertex"), default="auto", help="auto=무료 키 먼저, 막히면 Vertex")
    ap.add_argument("--check-only", action="store_true", help="API 없이 관문 판정만(시험용)")
    a = ap.parse_args()
    qs = list(a.questions)
    if a.file:
        qs += [l.strip() for l in open(a.file, encoding="utf-8") if l.strip()]
    if not qs or not a.topic:
        sys.exit(__doc__)
    msg = gate(a.topic, len(qs), a.followup, a.more)
    if msg:
        sys.exit(msg)
    if len(qs) == 1 and not a.followup and not a.more:
        print("[리서치 관문] 첫 조사에 질문이 1개뿐입니다. 궁금한 것을 더 모아 한 번에 묻는 게 원칙입니다(이번은 진행).", file=sys.stderr)
    if a.check_only:
        print("통과")
        return
    res = ask_batch(qs, a.common, a.model, a.route)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    kind = "more" if a.more else ("followup" if a.followup else "first")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "topic": a.topic, "n_q": len(qs), "kind": kind, "more": a.more,
                            "route": res.get("route"), "tokens": res.get("usage", {}).get("totalTokenCount"), "ok": "error" not in res}, ensure_ascii=False) + NL)
    if a.out:
        json.dump({"topic": a.topic, "questions": qs, **res}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if "error" in res:
        print("오류:", res["error"], res.get("detail", "")[:200])
        sys.exit(1)
    print(res["text"])
    print(NL + "출처:")
    for x in res["sources"][:15]:
        print(" -", x["title"], x["uri"] or "")
    print(f"{NL}(API 1회, 경로 {res.get('route')}, 질문 {len(qs)}개, 토큰 {res.get('usage', {}).get('totalTokenCount')})")


if __name__ == "__main__":
    main()
