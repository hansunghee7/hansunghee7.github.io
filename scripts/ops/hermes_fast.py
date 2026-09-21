#!/usr/bin/env python3
"""헤르메스를 제미나이 API로 빠르게 돌린다(사장님 지시 2026-09-22: 헤르메스를 빠르고 똑똑하게 쓸 때는 제미나이 키).

- 키는 `gemini_fast.py`와 같은 대장(비공개 registry)의 role=fast 키만 쓰고, 오늘 호출이 적은 키부터 돌려 쓴다.
  다이얼로그 키(role=dialog)는 쓰지 않는다. 키 값은 환경변수로만 자식 프로세스에 넘기고 어디에도 출력하지 않는다.
- 기본 모델은 응답 1초대인 gemini-3.5-flash-lite. 더 똑똑한 답이 필요하면 --model gemini-3.6-flash(응답 4초대).
- 출력은 파일로 받는다(파이프로 받으면 헤르메스가 띄운 브라우저 데몬 때문에 늦게 끝날 수 있다).

사용: python scripts/ops/hermes_fast.py "지시문" [--model gemini-3.6-flash] [--out 결과.txt] [--timeout 300]
"""
import argparse, os, re, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_fast as g  # noqa: E402

DEFAULT_MODEL = "gemini-3.5-flash-lite"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()

    day = g.read_counter().get(g.today_pt(), {})
    keys = sorted(g.load_keys(), key=lambda k: day.get(k["fp"], {}).get("calls", 0))
    if not keys:
        sys.exit("사용 가능한 키 없음(대장 registry/gemini-keys.json 확인)")
    out = a.out or os.path.join(tempfile.gettempdir(), "hermes_fast_out.txt")
    models = [a.model] + ([DEFAULT_MODEL] if a.model != DEFAULT_MODEL else [])  # 모델이 과부하(503)면 flash-lite로 한 단계 내린다
    for model, k in [(m, k) for m in models for k in keys]:
        assert k["fp"] not in g.dialog_fps()
        env = dict(os.environ, GOOGLE_API_KEY=k["value"], GEMINI_API_KEY=k["value"])
        t = time.time()
        with open(out, "w", encoding="utf-8") as f:
            try:
                p = subprocess.run(["hermes", "chat", "-q", a.prompt, "--oneshot", "--provider", "gemini", "-m", model],
                                   stdout=f, stderr=subprocess.STDOUT, env=env, timeout=a.timeout)
                rc = p.returncode
            except subprocess.TimeoutExpired:
                rc = "timeout"
        secs = round(time.time() - t, 1)
        text = ANSI.sub("", open(out, encoding="utf-8", errors="replace").read())
        failed = rc != 0 or re.search(r"\b(429|quota|RESOURCE_EXHAUSTED|API key not valid)\b", text, re.I)
        g.bump(k["fp"], not failed, secs)
        print(f"키 {k['fp']} 모델 {model} 종료 {rc} {secs}초 → {out}")
        if not failed:
            print(text[-600:])
            return
    sys.exit("모든 키에서 실패")


if __name__ == "__main__":
    main()
