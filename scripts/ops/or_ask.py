#!/usr/bin/env python3
"""OpenRouter 벤치마크용 얇은 호출기: 표준입력 프롬프트 -> 표준출력 답. litellm(게이트웨이와 같은 라이브러리)으로 호출한다.

사용: <litellm 설치된 python> scripts/ops/or_ask.py <openrouter 모델 id, 예: meta-llama/llama-3.3-70b-instruct>
키는 환경변수 OPENROUTER_API_KEY로만 받는다(파일에서 읽지 않는다). 키 값은 어디에도 출력하지 않는다.
토큰 사용량은 표준에러에 'USAGE <입력> <출력>'으로만 남긴다(비용 집계용).
"""
import os
import sys


def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY 환경변수가 없음")
    import litellm

    litellm.drop_params = True
    resp = litellm.completion(
        model=f"openrouter/{sys.argv[1]}",
        messages=[{"role": "user", "content": sys.stdin.read()}],
        api_key=key,
        temperature=0,
        max_tokens=1500,
        timeout=90,
    )
    sys.stdout.reconfigure(encoding="utf-8")
    print(resp.choices[0].message.content or "")
    u = resp.usage
    print(f"USAGE {u.prompt_tokens} {u.completion_tokens}", file=sys.stderr)


if __name__ == "__main__":
    main()
