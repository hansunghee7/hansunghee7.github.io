#!/usr/bin/env python3
"""구솔라 텔레그램 봇으로 사장님께 직접 한 줄 알림을 보낸다(신PC가 꺼져 있어도 동작).

사용: tg_notify.py "제목" < 본문   또는   tg_notify.py "제목" "본문"
설정: ~/hermes-agent/.env 의 TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USERS(첫 번째 ID로 보냄).
값은 화면·로그에 출력하지 않는다. 종료 코드 0=전송됨, 1=실패.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

ENV = os.environ.get("TG_ENV", os.path.expanduser("~/hermes-agent/.env"))


def load_env(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def send(text):
    env = load_env(ENV)
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat = env.get("TELEGRAM_ALLOWED_USERS", "").split(",")[0].strip()
    if not token or not chat:
        print("[ERROR] 토큰 또는 허용 사용자 ID가 설정되지 않음", file=sys.stderr)
        return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": text[:3500]}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return bool(json.load(r).get("ok"))
    except Exception as e:  # 토큰이 든 URL이 예외 문구에 섞이지 않도록 종류만 출력
        print(f"[ERROR] 전송 실패: {type(e).__name__}", file=sys.stderr)
        return False


if __name__ == "__main__":
    title = sys.argv[1] if len(sys.argv) > 1 else "알림"
    body = sys.argv[2] if len(sys.argv) > 2 else ("" if sys.stdin.isatty() else sys.stdin.read())
    sys.exit(0 if send(f"{title}\n\n{body}".strip()) else 1)
