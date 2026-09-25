# -*- coding: utf-8 -*-
"""사장님 텔레그램(신솔라 방)으로 컨펌받을 결과물을 그대로 보낸다.

사장님 지시(2026-09-25): 컨펌받아야 하는 결과물은 텔레그램으로 보낸다(전 에이전트).
우편함 --ask는 "무엇을 정해 달라"는 알림이고, 이 스크립트는 결과물 자체(글·사진·파일)를 보낸다.

사용:
  python scripts/ops/tg_boss.py text "메시지"                 글(4000자 넘으면 나눠 보냄)
  python scripts/ops/tg_boss.py text --file 초안.md            파일 내용을 글로(폰에서 바로 읽힘)
  python scripts/ops/tg_boss.py photo 사진.png "설명"          사진
  python scripts/ops/tg_boss.py doc 파일.html "설명"           파일(HTML은 폰 브라우저로 열림)

설정: 헤르메스 .env의 TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USERS 첫 번째(우편함 배달부와 같은 봇·같은 방).
값은 화면·로그에 출력하지 않는다.
"""
import sys
from pathlib import Path

import requests

ENV = Path(r"C:\Users\PC\AppData\Local\hermes\.env")


def conf():
    env = {}
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("\"'")
    return env["TELEGRAM_BOT_TOKEN"], env["TELEGRAM_ALLOWED_USERS"].split(",")[0].strip()


def call(method, data, files=None):
    tok, cid = conf()
    r = requests.post(f"https://api.telegram.org/bot{tok}/{method}", data={"chat_id": cid, **data},
                      files=files, timeout=120).json()
    print(method, "ok" if r.get("ok") else "실패: " + str(r.get("description")))
    return bool(r.get("ok"))


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    kind = argv[0]
    if kind == "text":
        body = Path(argv[2]).read_text(encoding="utf-8") if argv[1] == "--file" else argv[1]
        ok = all(call("sendMessage", {"text": body[i:i + 4000]}) for i in range(0, len(body), 4000))
    elif kind in ("photo", "doc"):
        # 관문(2026-09-25, CLAUDE#4e7b): 숏폼 제작물(음성·영상·장면)은 핏 제작함으로 간다(shorts-lab tools/notify/tg_send.py).
        # 핏 세션이 원칙7만 보고 신솔라 방으로 보낸 사고 → 기억 대신 도구가 막는다. 정말 신솔라 방이어야 하면 --force.
        p = str(Path(argv[1]).resolve())
        if "--force" not in argv and (("AI숏폼" in p) or ("shorts-lab" in p)) and Path(p).suffix.lower() in (
                ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".png", ".jpg", ".jpeg", ".webp"):
            sys.exit("숏폼 제작물은 핏 제작함으로: python C:/work/shorts-lab/tools/notify/tg_send.py "
                     "doc|final|audio|photos <파일> --title \"설명\" (신솔라 방이 맞으면 --force)")
        argv = [a for a in argv if a != "--force"]
        method, field = ("sendPhoto", "photo") if kind == "photo" else ("sendDocument", "document")
        with open(argv[1], "rb") as f:
            ok = call(method, {"caption": argv[2] if len(argv) > 2 else ""}, {field: f})
    else:
        sys.exit(__doc__)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
