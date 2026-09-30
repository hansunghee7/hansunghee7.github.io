#!/usr/bin/env python3
"""로컬 Ollama 호출기(or_ask.py와 같은 규약): 표준입력 프롬프트 -> 표준출력 답.

사용: python scripts/ops/ollama_ask.py <모델, 예: qwen2.5-coder:14b>
서버는 localhost:11434(외부 전송 없음). temperature 0, 컨텍스트 8192.
"""
import json
import sys
import urllib.request


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    body = {"model": sys.argv[1], "prompt": sys.stdin.read(), "stream": False,
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1500}}
    req = urllib.request.Request("http://localhost:11434/api/generate", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    sys.stdout.reconfigure(encoding="utf-8")
    print(out.get("response", ""))
    print(f"USAGE {out.get('prompt_eval_count', 0)} {out.get('eval_count', 0)}", file=sys.stderr)


if __name__ == "__main__":
    main()
