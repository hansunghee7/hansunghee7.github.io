"""[옛이름 허용: 유료 실행기 관문이 옛 이름과 새 이름을 함께 인식해야 함]
Carvit 저장소 자체 실행기(saegim-test) 생존 감시와 자동 우회(2026-10-16 탐, 공정 카드 탐#113·#114).

이름표 saegim-test를 단 실행기 중 하나라도 online이면 정상(종료 코드 0). 모두 offline이면 1 → watch.py가 알린다.
실행기가 다 꺼지면 Carvit PR 시험이 줄을 서서 기다린다. 구PC 복구: ssh goosolar '~/actions-runner/keepalive.sh'

--switch(사장님 10/16 '자동우회 승인'): 연속 2회 offline이면 저장소 변수 CARVIT_CI_RUNNER(새 이름 우선)와 SAEGIM_CI_RUNNER(옛 이름)를 같은 값 ["ubuntu-latest"]로 바꿔
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
VAR_NEW = "CARVIT_CI_RUNNER"  # 새 이름(읽기 우선, 2026-10-21 B3 P2 S1-1)
VAR_OLD = "SAEGIM_CI_RUNNER"  # 옛 이름(이행 기간 동안 같은 값으로 함께 씀, P4에서 제거)
VARS = (VAR_NEW, VAR_OLD)
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


def _read_one(name):
    """(값, 오류, 존재). 변수가 없으면 (None, "", False)."""
    r = gh(["api", f"repos/{REPO}/actions/variables/{name}"])
    if r.returncode != 0:
        if "404" in (r.stderr or "") or "Not Found" in (r.stderr or "") + (r.stdout or ""):
            return None, "", False
        return None, (r.stderr or "")[:200] or "변수 조회 실패", False
    return json.loads(r.stdout).get("value"), "", True


def read_var():
    """(값, 오류). 두 이름을 모두 읽는다. 둘 다 없으면 (None, "").

    두 값이 다르면 '불일치' 경고를 출력하고, 더 위험한 쪽(깃허브 실행기 값이 하나라도 있으면 그 값 = 우회 중)을 돌려준다.
    둘 다 같은 종류면 새 이름 값을 돌려준다.
    """
    found = {}
    for name in VARS:
        value, err, exists = _read_one(name)
        if err:
            return None, err
        if exists:
            found[name] = value
    if not found:
        return None, ""
    if len(found) == 2 and found[VAR_NEW] != found[VAR_OLD]:
        print(f"경고: {VAR_NEW}와 {VAR_OLD}의 값이 다름(불일치). 새={found[VAR_NEW]} 옛={found[VAR_OLD]}. "
              "깃허브 실행기 값이 하나라도 있으면 우회 중으로 판정")
        for name in VARS:
            if is_hosted(found[name]):
                return found[name], ""
    return found.get(VAR_NEW, found.get(VAR_OLD)), ""


def _put(name, value, exists):
    if exists:
        r = gh(["api", "-X", "PATCH", f"repos/{REPO}/actions/variables/{name}", "-f", f"value={value}"])
    else:
        r = gh(["api", "-X", "POST", f"repos/{REPO}/actions/variables", "-f", f"name={name}", "-f", f"value={value}"])
    return r.returncode == 0, (r.stderr or "")[:200]


def _delete(name):
    r = gh(["api", "-X", "DELETE", f"repos/{REPO}/actions/variables/{name}"])
    return r.returncode == 0


def write_var(value, exists=None):
    """두 이름 모두에 같은 값을 쓴다(이름별로 존재 확인 뒤 PATCH/POST, exists 인자는 호환용으로 무시).

    한쪽이 실패하면 이미 쓴 쪽을 원래 값으로 되돌리려 시도하고(원래 없던 변수는 삭제) RuntimeError를 올린다.
    성공하면 (True, "").
    """
    before = {}
    for name in VARS:
        old, err, there = _read_one(name)
        if err:
            raise RuntimeError(f"{name} 조회 실패로 쓰기 중단: {err}")
        before[name] = (old, there)
    written = []
    for name in VARS:
        ok, e = _put(name, value, before[name][1])
        if ok:
            written.append(name)
            continue
        failed_back = []
        for done in written:
            old, there = before[done]
            restored = _put(done, old, True)[0] if there else _delete(done)
            if not restored:
                failed_back.append(done)
        msg = f"{name} 쓰기 실패({e})"
        if written:
            msg += "; 되돌림 " + ("실패: " + ",".join(failed_back) + " 값이 서로 다를 수 있음" if failed_back else "성공")
        raise RuntimeError(msg)
    return True, ""


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
        try:
            ok, e = write_var(HOSTED_VALUE)
        except RuntimeError as exc:
            ok, e = False, str(exc)
        print(f"자체 실행기가 연속 {streak}회 offline → Carvit CI를 깃허브 실행기(ubuntu-latest)로 우회 전환: "
              + ("성공" if ok else f"실패 {e}"))
        var_value = HOSTED_VALUE if ok else var_value
    elif action == "restore":
        try:
            ok, e = write_var(SELF_VALUE)
        except RuntimeError as exc:
            ok, e = False, str(exc)
        print("자체 실행기가 다시 online → Carvit CI를 자체 실행기(saegim-test)로 복귀: " + ("성공" if ok else f"실패 {e}"))
        var_value = SELF_VALUE if ok else var_value
    elif not online:
        print(f"자체 실행기 offline 연속 {streak}회"
              + (" (이미 깃허브 실행기로 우회 중)" if is_hosted(var_value) else f" (전환 기준 {OFFLINE_THRESHOLD}회)"))
    save_state(state)
    print(f"{VAR_NEW}/{VAR_OLD} = {var_value if var_value is not None else '(없음 = 자체 실행기)'}")
    return 0 if online and not is_hosted(var_value) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
