#!/usr/bin/env python3
"""로컬 Ollama 호출기(or_ask.py와 같은 규약): 표준입력 프롬프트 -> 표준출력 답.

사용: python scripts/ops/ollama_ask.py <모델, 예: qwen2.5-coder:14b>
서버는 localhost:11434(외부 전송 없음). temperature 0, 컨텍스트 8192.
호출 전 gpu_gate 관문을 거친다(환경변수 GPU_WHO=이름, GPU_NOW=1은 낮의 큰 작업 허용, GPU_GATE=off는 끔).
"""
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def est_gb(model: str) -> float:
    """모델 이름의 파라미터 수로 VRAM 필요량을 어림한다(Q4 기준, 실측: 14B≈10GB, 32B≈21GB)."""
    m = re.search(r"(\d+(?:\.\d+)?)b(?![a-z])", model.lower())
    return round(float(m.group(1)) * 0.65 + 1, 1) if m else 8.0


def already_loaded(model: str) -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=5) as r:
            return any(x.get("name") == model for x in json.load(r).get("models", []))
    except Exception:
        return False


def gate(model: str) -> None:
    """GPU 공용 관문(gpu_gate.py). 이미 올라가 있는 모델은 새 VRAM이 안 드니 통과, GPU_GATE=off면 건너뜀."""
    if os.environ.get("GPU_GATE") == "off" or already_loaded(model):
        return
    import gpu_gate
    ok, msg = gpu_gate.need(est_gb(model), os.environ.get("GPU_WHO", "탐"), f"ollama {model}",
                            now_flag=bool(os.environ.get("GPU_NOW")), ttl_min=5)
    if not ok:
        sys.stderr.reconfigure(encoding="utf-8")
        print(f"GPU 관문 거절: {msg}", file=sys.stderr)
        sys.exit(3)


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    gate(sys.argv[1])
    body = {"model": sys.argv[1], "prompt": sys.stdin.read(), "stream": False,
            "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE_REQ", "2m"),  # 쓰고 2분 뒤 VRAM을 놓는다(서버 기본은 30분이라 겹침의 원인)
            "options": {"temperature": 0, "num_ctx": int(os.environ.get("OLLAMA_NUM_CTX", "8192")),
                        "num_predict": int(os.environ.get("OLLAMA_NUM_PREDICT", "1500"))}}
    if os.environ.get("OLLAMA_JSON"):  # 문법이 맞는 JSON만 내게 한다(스키마 검증은 호출자 몫)
        body["format"] = "json"
    req = urllib.request.Request("http://localhost:11434/api/generate", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    sys.stdout.reconfigure(encoding="utf-8")
    print(out.get("response", ""))
    usage = f"USAGE {out.get('prompt_eval_count', 0)} {out.get('eval_count', 0)}"
    print(usage, file=sys.stderr)
    if os.environ.get("ACL_USAGE_LOG"):  # 오케스트레이션 벤치가 토큰을 집계하는 통로
        with open(os.environ["ACL_USAGE_LOG"], "a", encoding="utf-8") as f:
            f.write(usage + "\n")


if __name__ == "__main__":
    main()
