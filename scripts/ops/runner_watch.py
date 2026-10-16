"""Carvit 저장소 자체 실행기(saegim-test) 생존 감시와 자동 우회(2026-10-16 탐, 공정 카드 탐#113·#114).

이름표 saegim-test를 단 실행기 중 하나라도 online이면 정상(종료 코드 0). 모두 offline이면 1 → watch.py가 알린다.
실행기가 다 꺼지면 Carvit PR 시험이 줄을 서서 기다린다. 구PC 복구: ssh goosolar '~/actions-runner/keepalive.sh'

--switch(사장님 10/16 '자동우회 승인'): 연속 2회 offline이면 저장소 변수 SAEGIM_CI_RUNNER를 ["ubuntu-latest"]로 바꿔
Carvit CI(test.yml·deploy-cloud-run.yml의 changes·container-smoke)가 깃허브 실행기로 돌게 하고, 다시 online이면
["self-hosted","saegim-test"]로 되돌린다. 변수가 없으면(404) 워크플로 기본값 = 자체 실행기.
종료 코드: 자체 실행기 online(정상 경로) 0, 우회 중·offline·조회 실패 1.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = "hansunghee7/simplifier-saegim"
LABEL = "saegim-test"
VAR = "SAEGIM_CI_RUNNER"
SELF_VALUE = '["self-hosted","saegim-test"]'
HOSTED_VALUE = '["ubuntu-latest"]'
OFFLINE_THRESHOLD = 2
STATE_FILE = Path("C:/work/_ops/runner_watch_state.json")
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def is_hosted(var_value):
    """변수 값이 깃허브 실행기(ubuntu-latest)를 가리키는가. None(변수 없음)은 자체 실행기."""
    return bool(var_value) and "ubuntu-latest" in var_value


def decide(online, prev_streak, var_value):
    """순수 판단 함수: (online, 직전 연속 offline 횟수, 변수 값) -> (action, 새 연속 offline 횟수).

    action: "fallback"(깃허브 실행기로 전환) | "restore"(자체 실행기로 복귀) | "none".
    """
    if online:
        return ("restore" if is_hosted(var_value) else "none"), 0
    streak = prev_streak + 1
    if not is_hosted(var_value) and streak >= OFFLINE_THRESHOLD:
        return "fallback", streak
    return "none", streak


def gh(args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", creationflags=FLAGS)


def read_runners():
    r = gh(["api", f"repos/{REPO}/actions/runners"])
    if r.returncode != 0:
        return None, (r.stderr or "")[:200]
    runners = [x for x in json.loads(r.stdout).get("runners", []) if LABEL in [l["name"] for l in x.get("labels", [])]]
    return runners, ""


def read_var():
    """(값, 오류). 변수가 없으면 (None, "")."""
    r = gh(["api", f"repos/{REPO}/actions/variables/{VAR}"])
    if r.returncode != 0:
        if "404" in (r.stderr or "") or "Not Found" in (r.stderr or "") + (r.stdout or ""):
            return None, ""
        return None, (r.stderr or "")[:200] or "변수 조회 실패"
    return json.loads(r.stdout).get("value"), ""


def write_var(value, exists):
    if exists:
        r = gh(["api", "-X", "PATCH", f"repos/{REPO}/actions/variables/{VAR}", "-f", f"value={value}"])
    else:
        r = gh(["api", "-X", "POST", f"repos/{REPO}/actions/variables", "-f", f"name={VAR}", "-f", f"value={value}"])
    return r.returncode == 0, (r.stderr or "")[:200]


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"offline_streak": 0}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def main(argv):
    runners, err = read_runners()
    if runners is None:
        print("실행기 목록을 읽지 못함:", err)
        return 1
    online = any(x["status"] == "online" for x in runners)
    print(" · ".join(f"{x['name']} {x['status']}{' (작업 중)' if x.get('busy') else ''}" for x in runners) or "실행기 없음")
    if "--switch" not in argv:
        return 0 if online else 1

    var_value, verr = read_var()
    if verr:
        print("변수 조회 실패(전환 판단 보류):", verr)
        return 0 if online else 1
    state = load_state()
    action, streak = decide(online, int(state.get("offline_streak", 0)), var_value)
    state["offline_streak"] = streak
    if action == "fallback":
        ok, e = write_var(HOSTED_VALUE, var_value is not None)
        print(f"자체 실행기가 연속 {streak}회 offline → Carvit CI를 깃허브 실행기(ubuntu-latest)로 우회 전환: "
              + ("성공" if ok else f"실패 {e}"))
        var_value = HOSTED_VALUE if ok else var_value
    elif action == "restore":
        ok, e = write_var(SELF_VALUE, True)
        print("자체 실행기가 다시 online → Carvit CI를 자체 실행기(saegim-test)로 복귀: " + ("성공" if ok else f"실패 {e}"))
        var_value = SELF_VALUE if ok else var_value
    elif not online:
        print(f"자체 실행기 offline 연속 {streak}회"
              + (" (이미 깃허브 실행기로 우회 중)" if is_hosted(var_value) else f" (전환 기준 {OFFLINE_THRESHOLD}회)"))
    save_state(state)
    print(f"{VAR} = {var_value if var_value is not None else '(없음 = 자체 실행기)'}")
    return 0 if online and not is_hosted(var_value) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
