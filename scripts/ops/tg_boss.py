# -*- coding: utf-8 -*-
"""사장님 텔레그램(페르소나별 컨펌 그룹)으로 컨펌받을 결과물을 그대로 보낸다.

사장님 지시(2026-09-25): 컨펌받아야 하는 결과물은 텔레그램으로 보낸다(전 에이전트).
우편함 --ask는 "무엇을 정해 달라"는 알림이고, 이 스크립트는 결과물 자체(글·사진·파일)를 보낸다.
2026-09-27 텔레그램 채널 정비: 봇을 탐전용봇으로 통합하고, 신솔라 방 하나에 다 섞이던 걸
페르소나별 "컨펌-XX" 그룹으로 분리했다(사장님 결정, CLAUDE.md 소통 매트릭스).

사용:
  python scripts/ops/tg_boss.py text "메시지" --persona 마야      글(4000자 넘으면 나눠 보냄)
  python scripts/ops/tg_boss.py text --file 초안.md --persona 지투 파일 내용을 글로(폰에서 바로 읽힘)
  python scripts/ops/tg_boss.py photo 사진.png "설명" --persona 핏  사진
  python scripts/ops/tg_boss.py doc 파일.html "설명" --persona 노트 파일(HTML은 폰 브라우저로 열림)

--persona 생략 시 "탐"으로 감(경고 출력). 페르소나: 마야·지투·노트·핏·탐·클탐.
설정: 탐전용봇 설정(~/.claude/channels/telegram/.env)의 TELEGRAM_BOT_TOKEN.
값은 화면·로그에 출력하지 않는다.
"""
import sys
from pathlib import Path

import requests

ENV = Path(r"C:\Users\PC\.claude\channels\telegram\.env")

PERSONA_CHATS = {
    "마야": "-5306851243",
    "지투": "-5465604522",
    "노트": "-5416791753",
    "핏": "-5392146307",
    "탐": "-5552561028",
    "클탐": "-5265200657",
}


def extract_persona(argv):
    if "--persona" in argv:
        i = argv.index("--persona")
        persona = argv[i + 1]
        del argv[i:i + 2]
    else:
        sys.exit("❌ --persona 필수 옵션 (생략 불가)\n"
                 "사용: python scripts/ops/tg_boss.py text \"메시지\" --persona 지투\n"
                 f"가능한 페르소나: {', '.join(PERSONA_CHATS)}")
    if persona not in PERSONA_CHATS:
        sys.exit("알 수 없는 페르소나: " + persona + " (가능: " + ", ".join(PERSONA_CHATS) + ")")
    return persona


def conf(persona):
    env = {}
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("\"'")
    return env["TELEGRAM_BOT_TOKEN"], PERSONA_CHATS[persona]


def call(method, data, persona, files=None):
    tok, cid = conf(persona)
    r = requests.post(f"https://api.telegram.org/bot{tok}/{method}", data={"chat_id": cid, **data},
                      files=files, timeout=120).json()
    print(method, "ok" if r.get("ok") else "실패: " + str(r.get("description")))
    return bool(r.get("ok"))


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    persona = extract_persona(argv)
    kind = argv[0]
    if kind == "text":
        body = Path(argv[2]).read_text(encoding="utf-8") if argv[1] == "--file" else argv[1]
        ok = all(call("sendMessage", {"text": body[i:i + 4000]}, persona) for i in range(0, len(body), 4000))
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
            ok = call(method, {"caption": argv[2] if len(argv) > 2 else ""}, persona, {field: f})
    else:
        sys.exit(__doc__)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
