"""슬랙 시험 채널에 에이전트 이름을 붙여 글을 올린다(탐-DM장애 #7 말하기 실험, chat:write 방식).
- 봇 토큰(SLACK_BOT_TOKEN)은 금고가 .env에 담은 것을 읽는다. 값은 출력하지 않는다.
- 글은 '[이름] 내용'으로 올라간다(봇 하나를 여러 에이전트가 쓰므로 이름으로 구분). 시험 채널 하나로 제한한다.
사용: python scripts/ops/slack_post.py --as 탐 "보낼 글" [--env C:/work/_ops/n152/.env]
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
CHANNEL = "C0CBP55T8MP"  # agent-comm-test(비공개 시험 채널)


def read_env(path, name):
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"{name} 없음({path})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as", dest="who", required=True)
    ap.add_argument("text")
    ap.add_argument("--env", default="C:/work/_ops/n152/.env")
    a = ap.parse_args()
    token = read_env(a.env, "SLACK_BOT_TOKEN")
    body = urllib.parse.urlencode({"channel": CHANNEL, "text": f"[{a.who}] {a.text}"}).encode()
    req = urllib.request.Request("https://slack.com/api/chat.postMessage", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    print("ok" if data.get("ok") else "실패: " + str(data.get("error")))


if __name__ == "__main__":
    main()
