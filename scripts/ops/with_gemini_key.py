#!/usr/bin/env python3
"""키 대장(비공개 registry/gemini-keys.json)의 키를 자식 프로세스의 환경변수로만 넘겨 명령을 실행한다.

키 값은 화면·파일·메시지 어디에도 쓰지 않는다. 전달은 값이 아니라 "대장 id"로 한다(사장님 지시 2026-09-22: 핏에게 제미나이 키 전달).
role=dialog 키는 넘기지 않는다.

사용: python scripts/ops/with_gemini_key.py <대장 id> -- <실행할 명령...>
예:   python scripts/ops/with_gemini_key.py fit-video -- python pilot-shorts2/gemini_feedback.py ...
설정되는 환경변수: GEMINI_API_KEY, GOOGLE_API_KEY (자식 프로세스에서만)
"""
import os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_fast as g  # noqa: E402


def main():
    if len(sys.argv) < 4 or sys.argv[2] != "--":
        sys.exit(__doc__)
    key_id, cmd = sys.argv[1], sys.argv[3:]
    entry = next((e for e in g.registry() if e["id"] == key_id), None)
    if not entry:
        sys.exit(f"대장에 id '{key_id}'가 없습니다: " + ", ".join(e["id"] for e in g.registry()))
    if entry.get("role") == "dialog":
        sys.exit("다이얼로그 키는 넘기지 않습니다")
    text = open(entry["source"]["file"], encoding="utf-8", errors="ignore").read()
    var = entry["source"]["var"]
    m = re.search(rf"^\s*(?:set\s+)?{var}\s*=\s*['\"]?([^\s'\"]+)", text, re.M | re.I)
    if not m or g.fp(m.group(1)) != entry["fp"]:
        sys.exit("키 파일의 지문이 대장과 다릅니다(키가 바뀌었으면 대장을 고칠 것)")
    env = dict(os.environ, GEMINI_API_KEY=m.group(1), GOOGLE_API_KEY=m.group(1))
    sys.exit(subprocess.call(cmd, env=env))


if __name__ == "__main__":
    main()
