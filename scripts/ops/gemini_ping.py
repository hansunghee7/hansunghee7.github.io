#!/usr/bin/env python3
"""제미나이 API 키가 살아 있는지 확인한다(감시용). 모델 목록 조회라 생성 호출과 무료 한도(키당 하루 20회)를 소모하지 않는다.
키는 헤르메스 .env에서 읽고 절대 출력하지 않는다. 종료 코드 0 = 하나 이상 정상."""
import os
import sys
import urllib.error
import urllib.request

ENV = os.environ.get("HERMES_ENV", r"C:\Users\PC\AppData\Local\hermes\.env")
NAMES = (("GEMINI_VERIFY_KEY", "검증키"), ("GOOGLE_API_KEY", "보조키"))


def read_env(path):
    out = {}
    try:
        for line in open(path, encoding="utf-8"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def status(key):
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1", headers={"x-goog-api-key": key}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return type(e).__name__


def main():
    env, parts, ok = read_env(ENV), [], 0
    for name, label in NAMES:
        key = env.get(name)
        if not key:
            parts.append(f"{label} 없음")
            continue
        s = status(key)
        ok += s == 200
        parts.append(f"{label} {s}")
    print(" / ".join(parts) or "키를 찾지 못함")
    return 0 if ok else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
