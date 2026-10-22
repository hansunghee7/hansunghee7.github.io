"""카빗 DM 수신기를 켜는 한 줄 명령을 점검하고 출력한다 (카빗DM 3차 항목 5·11).

하는 일: 설정 폴더의 설정·코드 파일이 있는지 확인하고, 같은 설정으로 이미 돌고 있는 수신기가 없는지 보고,
Monitor 도구에 그대로 붙일 한 줄을 출력한다.
안 하는 일: 수신 코드 값을 읽거나 출력하지 않는다(파일 존재와 크기만 본다). 수신기를 직접 띄우지 않는다.

사용:
    python scripts/ops/carvit_monitor_cmd.py C:/work/_ops/jitu-knock
출력 마지막 줄(MONITOR_COMMAND=...)을 Monitor 도구의 command로 쓴다. 30분 뒤 감시 종료 알림이 오면 같은 명령을 다시 쓴다.
"""
import json
import subprocess
import sys
from pathlib import Path

RECEIVER = "carvit_autoreceive.py"


def running_with(config: Path) -> list[str]:
    ps = (
        "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*"
        + RECEIVER
        + "*' -and $_.CommandLine -like '*"
        + config.parent.name
        + "*' } | ForEach-Object { $_.ProcessId }"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except Exception:
        return []
    return [x.strip() for x in out.split() if x.strip().isdigit()]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("사용: python scripts/ops/carvit_monitor_cmd.py <설정 폴더>")
        return 2
    folder = Path(argv[1])
    config = folder / "autoreceive_config.json"
    receiver = folder / RECEIVER
    problems = []
    if not config.is_file():
        problems.append(f"설정 파일이 없음: {config}")
    if not receiver.is_file():
        problems.append(f"수신기 파일이 없음: {receiver}")
    code_file = None
    if config.is_file():
        try:
            cfg = json.loads(config.read_text(encoding="utf-8"))
        except Exception as e:
            problems.append(f"설정 파일을 읽지 못함: {e}")
            cfg = {}
        code_file = Path(cfg.get("autoreceive_code_file", "")) if cfg.get("autoreceive_code_file") else None
        if code_file is None or not code_file.is_file() or code_file.stat().st_size == 0:
            problems.append("수신 코드 파일이 없거나 비어 있음(값은 확인하지 않음)")
        if not cfg.get("state_file") and not cfg.get("log_dir"):
            problems.append("log_dir 또는 state_file이 없음(다른 에이전트와 상태 파일이 섞일 수 있음)")
        if cfg.get("max_alerts_per_hour", 0) < 1000:
            problems.append("max_alerts_per_hour가 낮음(권장 100000)")
    if problems:
        print("점검 실패:")
        for p in problems:
            print(" - " + p)
        return 1
    pids = running_with(config)
    if pids:
        print(f"이미 같은 설정으로 도는 수신기가 있음(프로세스 {', '.join(pids)}). 새로 켜지 않아도 됩니다.")
    print("MONITOR_COMMAND=python -I " + receiver.as_posix() + " --config " + config.as_posix() + " 2>&1")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv))
