"""[옛이름 허용: 유료 실행기 관문이 옛 이름과 새 이름을 함께 인식해야 함]
PreToolUse(Bash|PowerShell) 훅(2026-10-18 노트, 사장님 지시 "유료 배포는 사장 컨펌, 무료 배포는 편하게"): 깃허브 실행기(Actions 유료분)로
Carvit 작업을 돌리는 명령만 막는다. 무료(우리 실행기 saegim-test) 배포·실행은 그대로 통과한다.
막는 것: ① `gh variable set SAEGIM_*_RUNNER` 또는 새 이름 `CARVIT_*_RUNNER`(2026-10-21 B3 P2 S1-1, 옛 이름과 함께 인식)의 값이 self-hosted가 아닌 경우(예: "ubuntu-latest") ② `gh workflow run <파일>`인데
그 워크플로가 깃허브 실행기에서 도는 경우(saegim 체크아웃의 runs-on으로 판정, 파일을 못 읽으면 통과).
사장님 컨펌을 받았으면 같은 명령 끝에 `# 사장님컨펌: <날짜와 원문 한 줄>`을 붙여 다시 실행한다(C:/work/_ops/paid_runner_log.jsonl에 남는다).
runner_watch.py --switch의 자동 우회(사장님 10/16 사전 승인)는 스크립트 안에서 돌아 이 훅과 무관하다. 파싱 실패는 통과(fail-open)."""
import json, os, re, sys, time
try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SAEGIM = os.environ.get("SAEGIM_CHECKOUT", "C:/work/simplifier-saegim")
LOG = os.environ.get("PAID_RUNNER_LOG", "C:/work/_ops/paid_runner_log.jsonl")
CONFIRM = re.compile(r"#\s*사장님컨펌\s*:\s*(\S.{4,})")


def _hosted_workflow(name: str) -> bool:
    path = os.path.join(SAEGIM, ".github", "workflows", os.path.basename(name))
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return False
    for line in text.splitlines():
        m = re.match(r"\s*runs-on:\s*(.+)$", line)
        if not m:
            continue
        v = m.group(1)
        if "self-hosted" in v:
            continue  # 기본이 우리 실행기(변수 스위치 포함)
        return True
    return False


RUNNER_VAR = re.compile(r"\b((?:SAEGIM|CARVIT)_[A-Z_]*RUNNER)\b", re.I)
GH = re.compile(r"(?<![\w.-])gh(?:\.exe)?\s", re.I)
VAR_SET = re.compile(r"\bvariable\s+set\b", re.I)
API_WRITE = re.compile(r"(?:-X|--method)[\s=]+(?:PATCH|POST|PUT)\b|\s(?:-f|-F|--field|--raw-field|--input)[\s=]", re.I)
API_VAR_PATH = re.compile(r"actions/variables", re.I)
UNKNOWN_VALUE = re.compile(r"--body-file|--input|=@|<|\$\(|`", re.I)


def _segments(cmd: str):
    """명령 한 줄을 ; && || 줄바꿈 파이프로 쪼갠다(파이프로 들어오는 값은 안 보이므로 '값 불명'으로 차단된다)."""
    return re.split(r";|&&|\|\||\n|\|", cmd)


def _value_ok(seg: str) -> bool:
    """자체 실행기 이름표 값만 허용. 유료 라벨이 섞였거나, 값이 안 보이거나(파일·파이프·치환), self-hosted가 없으면 차단 쪽."""
    if UNKNOWN_VALUE.search(seg):
        return False
    if re.search(r"ubuntu|windows|macos", seg, re.I):
        return False
    return bool(re.search(r"self-hosted", seg, re.I))


def check(cmd: str) -> str | None:
    """막을 이유(문자열) 또는 None."""
    if not GH.search(cmd):
        return None
    for seg in _segments(cmd):
        if not GH.search(seg):
            continue
        m = RUNNER_VAR.search(seg)
        if not m:
            continue
        is_set = VAR_SET.search(seg) is not None
        is_api = bool(re.search(r"\bapi\b", seg, re.I) and API_VAR_PATH.search(seg) and API_WRITE.search(seg))
        if (is_set or is_api) and not _value_ok(seg):
            return f"저장소 변수 {m.group(1)}를 깃허브 실행기(유료분) 값이거나 값을 알 수 없게 바꾸는 명령"
    if "simplifier-saegim" in cmd or "-R" not in cmd:
        for m in re.finditer(r"gh(?:\.exe)?\s+workflow\s+run\s+([\w.\-/]+\.ya?ml)", cmd):
            if _hosted_workflow(m.group(1)):
                return f"깃허브 실행기(유료분)에서 도는 워크플로 {os.path.basename(m.group(1))} 실행"
    return None


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        sys.exit(0)
    cmd = str((data.get("tool_input") or {}).get("command", ""))
    why = check(cmd)
    if not why:
        sys.exit(0)
    ok = CONFIRM.search(cmd)
    if ok:
        try:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "why": why, "confirm": ok.group(1)[:200],
                                    "cmd": cmd[:300]}, ensure_ascii=False) + "\n")
        except Exception:
            pass
        sys.exit(0)
    sys.stderr.write(
        f"[유료 실행기 관문] {why}입니다. 깃허브 실행기는 Actions 유료분이라 사장님 컨펌이 필요합니다(탐 #110·#111, CLAUDE.md dp01). "
        "무료 경로(우리 실행기 saegim-test)로 할 수 있으면 그쪽을 쓰세요. 컨펌을 받았으면 명령 끝에 "
        "`# 사장님컨펌: <날짜와 원문 한 줄>`을 붙여 다시 실행하세요.")
    sys.exit(2)


if __name__ == "__main__":
    main()
