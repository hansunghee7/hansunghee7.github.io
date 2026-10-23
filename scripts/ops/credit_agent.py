# -*- coding: utf-8 -*-
"""Claude API 크레딧 에이전트 래퍼(2026-10-24 탐). credit_run.py의 도구 사용판.

왜: Max 주간 한도가 바닥나도 일을 이어 가려고, 도구(Bash·Read·Edit 등)를 쓰는 헤드리스 클로드를 API 크레딧으로 돌린다. 사장님 지시 2026-10-24 "클로드API 사용하면 주간크레딧 덜쓰지 않나요".
credit_run.py는 도구 없이 글만 주고받는 래퍼라 명령 실행이 필요한 일은 이 래퍼를 쓴다.
키: credit_run.find_key()와 같다(환경변수 ANTHROPIC_API_KEY_OPS 또는 헤르메스 환경 파일). 값은 어디에도 출력하지 않고 자식 프로세스 환경에만 ANTHROPIC_API_KEY로 넣는다.
안전: --bare(훅·플러그인·CLAUDE.md 자동 읽기·구독 로그인 모두 생략, 인증은 API 키만), 허용 도구는 --allow로 좁게 준 것만(그 밖은 거절), 호출 한 번의 예산 --max-budget-usd, 하루 상한 --daily-usd(장부 합계), 제한 시간 --timeout.
종료 코드: 0 성공 / 2 호출 실패 / 3 하루 상한 초과 / 4 키 없음
사용: python credit_agent.py --who 탐 --model claude-sonnet-5-5 --prompt-file job.md --cwd <작업폴더> --allow "Bash(gh run list:*)" --allow Read [--max-budget-usd 3] [--daily-usd 25] [--out 결과.md] [--dry]
주의: --bare라 CLAUDE.md가 자동으로 안 읽힌다. 규칙은 프롬프트에 직접 넣는다. 이 래퍼 장부: CREDIT_LEDGER(기본 C:/work/_ops/claude_api_usage.csv), 누가 불렀는지는 --who.
"""
import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from credit_run import append_ledger, find_key, ledger_path, today_total  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", required=True)
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--allow", action="append", default=[], help="허용 도구 패턴(여러 번), 예: 'Bash(gh run list:*)' Read")
    ap.add_argument("--max-budget-usd", type=float, default=3.0)
    ap.add_argument("--daily-usd", type=float, default=25.0)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--out")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if not a.allow:
        print("NO-ALLOW: 허용 도구를 --allow로 하나 이상 주세요(기본 거절)", file=sys.stderr)
        return 2
    led = ledger_path()
    used = today_total(led)
    if used >= a.daily_usd:
        print("DAILY-CAP used=%.4f cap=%.2f: not called" % (used, a.daily_usd), file=sys.stderr)
        return 3
    key = find_key()
    if not key:
        print("NO-KEY: put ANTHROPIC_API_KEY_OPS via pass.py envput", file=sys.stderr)
        return 4
    prompt = Path(a.prompt_file).read_text(encoding="utf-8")
    cwd = str(Path(a.cwd).resolve())
    if a.dry:
        print("DRY ok used=%.4f cap=%.2f model=%s chars=%d cwd=%s allow=%s" % (used, a.daily_usd, a.model, len(prompt), cwd, a.allow))
        return 0
    env = dict(os.environ)
    env["ANTHROPIC_API_KEY"] = key
    env.pop("ANTHROPIC_API_KEY_OPS", None)
    claude_bin = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or "claude"
    cmd = [claude_bin, "-p", "--bare", "--model", a.model, "--output-format", "json",
           "--permission-mode", "dontAsk", "--allowedTools", ",".join(a.allow),
           "--max-budget-usd", str(a.max_budget_usd)]
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(cmd, input=prompt, cwd=cwd, env=env, capture_output=True, text=True,
                           encoding="utf-8", timeout=a.timeout, creationflags=flags)
    except Exception as e:
        append_ledger(led, [ts, a.who, a.model + "@agent", 0, 0, 0, "fail:" + type(e).__name__])
        print("CALL-FAIL", type(e).__name__, file=sys.stderr)
        return 2
    try:
        d = json.loads(r.stdout)
    except Exception:
        append_ledger(led, [ts, a.who, a.model + "@agent", 0, 0, 0, "fail:badjson"])
        print("CALL-FAIL bad output rc=%s stderr=%s" % (r.returncode, (r.stderr or "")[:200]), file=sys.stderr)
        return 2
    u = d.get("usage") or {}
    cost = float(d.get("total_cost_usd") or 0)
    append_ledger(led, [ts, a.who, a.model + "@agent", cost, u.get("input_tokens", 0), u.get("output_tokens", 0),
                        "ok" if not d.get("is_error") else "fail:api"])
    text = d.get("result", "")
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    print("OK cost=%.4f turns=%s today=%.4f cap=%.2f" % (cost, d.get("num_turns"), used + cost, a.daily_usd), file=sys.stderr)
    return 0 if not d.get("is_error") else 2


if __name__ == "__main__":
    sys.exit(main())
