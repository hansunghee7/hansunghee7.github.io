"""Carvit 저장소 자체 실행기(saegim-test) 생존 감시(2026-10-16 탐, 공정 카드 탐#113·#114).

이름표 saegim-test를 단 실행기 중 하나라도 online이면 정상(종료 코드 0). 모두 offline이면 1 → watch.py가 알린다.
실행기가 다 꺼지면 Carvit PR 시험이 줄을 서서 기다린다. 구PC 복구: ssh goosolar '~/actions-runner/keepalive.sh'
"""
import json
import subprocess
import sys

REPO = "hansunghee7/simplifier-saegim"
LABEL = "saegim-test"
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def main():
    r = subprocess.run(["gh", "api", f"repos/{REPO}/actions/runners"], capture_output=True, text=True,
                       encoding="utf-8", creationflags=FLAGS)
    if r.returncode != 0:
        print("실행기 목록을 읽지 못함:", (r.stderr or "")[:200])
        return 1
    runners = [x for x in json.loads(r.stdout).get("runners", []) if LABEL in [l["name"] for l in x.get("labels", [])]]
    print(" · ".join(f"{x['name']} {x['status']}{' (작업 중)' if x.get('busy') else ''}" for x in runners) or "실행기 없음")
    return 0 if any(x["status"] == "online" for x in runners) else 1


if __name__ == "__main__":
    sys.exit(main())
