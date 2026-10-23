"""사장님 슬랙 계정(사용자 토큰)으로 시험 채널에 글을 올린다(탐-DM장애 #19, 규칙 ③: 말머리를 이 코드가 강제).
- 사용자 토큰(SLACK_USER_TOKEN)은 금고가 .env에 담은 것을 읽는다. 값은 출력하지 않는다.
- 채널은 시험 채널 하나로 고정. 글은 '[발신→수신 #번호 | 목적] 본문' 형식이 아니면 올리지 않는다.
- 슬랙 글은 승인으로 인정하지 않는다(규칙 ②). 말머리 없는 글은 사장님 글이므로 이 스크립트는 말머리 없이 올리지 않는다.
사용: python scripts/ops/slack_user_post.py "[탐→Claude #1 | 질문] <@U0C7JTNUB8W> 본문"
      python scripts/ops/slack_user_post.py --whoami   (어느 토큰인지 종류만 확인)
"""
import json
import re
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
CHANNEL = "C0CBP55T8MP"  # agent-comm-test(비공개 시험 채널)
ENV = "C:/work/_ops/n152/.env"
TAG = re.compile(r"^\[[^\]→\s]+→[^\]\s]+ #\d+ \| (요청|회신|알림|질문|승인요청|기록)\] .+")


def read_env(name):
    for line in open(ENV, encoding="utf-8"):
        line = line.strip()
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def api(method, token, params=None):
    req = urllib.request.Request("https://slack.com/api/" + method,
                                 data=urllib.parse.urlencode(params or {}).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def whoami():
    for n in ("SLACK_TMP_A", "SLACK_TMP_B", "SLACK_USER_TOKEN", "SLACK_BOT_TOKEN"):
        t = read_env(n)
        if not t:
            continue
        d = api("auth.test", t)
        kind = "봇" if d.get("bot_id") else "사용자"
        print(n, "ok" if d.get("ok") else "실패:" + str(d.get("error")), kind)


def main():
    if sys.argv[1:] == ["--whoami"]:
        return whoami()
    text = " ".join(sys.argv[1:])
    if not TAG.match(text):
        raise SystemExit("말머리 형식 아님: [발신→수신 #번호 | 요청|회신|알림|질문|승인요청|기록] 본문")
    token = read_env("SLACK_USER_TOKEN")
    if not token:
        raise SystemExit("SLACK_USER_TOKEN 없음")
    d = api("chat.postMessage", token, {"channel": CHANNEL, "text": text})
    print("ok ts=" + str(d.get("ts")) if d.get("ok") else "실패: " + str(d.get("error")))


if __name__ == "__main__":
    main()
