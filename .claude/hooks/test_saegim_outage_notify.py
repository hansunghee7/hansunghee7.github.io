"""saegim-outage-notify.py 시험: python .claude/hooks/test_saegim_outage_notify.py
가짜 mailbox.py(받은 인자를 로그에 적음)를 형제 폴더에 두고, outage 파일을 Write했을 때만 지투·사장님 두 통을 보내고
그 밖의 입력·우편함 없음·깨진 입력에서는 보내지 않고 항상 exit 0인지 본다."""
import json, os, subprocess, sys, tempfile
from pathlib import Path

H = Path(__file__).with_name("saegim-outage-notify.py")

bad = []


def check(label, cond):
    if not cond:
        bad.append(label)


def run(project, home, event):
    raw = event if isinstance(event, bytes) else json.dumps(event).encode("utf-8")
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project), "HOME": str(home), "USERPROFILE": str(home)}
    return subprocess.run([sys.executable, str(H)], input=raw, capture_output=True, env=env).returncode


def sent(log):
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    project = td / "repo"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True, capture_output=True)
    home = td / "home"
    home.mkdir()
    log = td / "sent.log"
    mb = td / "solar-bible" / "mailbox"
    mb.mkdir(parents=True)
    (mb / "mailbox.py").write_text(
        "import sys\nopen(%r, 'a', encoding='utf-8').write(sys.argv[2] + '\\n')\n" % str(log), encoding="utf-8")

    outage = {"tool_name": "Write", "tool_input": {"file_path": str(project / ".claude" / "saegim-outage")}}
    check("outage 생성: exit 0", run(project, home, outage) == 0)
    check("outage 생성: 지투·사장님 두 통", sent(log) == ["지투", "사장님"])

    log.unlink()
    win = {"tool_name": "Write", "tool_input": {"file_path": "C:\\work\\hansunghee7.github.io\\.claude\\saegim-outage"}}
    run(project, home, win)
    check("윈도우 경로(역슬래시)도 인식", sent(log) == ["지투", "사장님"])

    for label, ev in {
        "다른 파일 Write": {"tool_name": "Write", "tool_input": {"file_path": str(project / "a.md")}},
        "Edit 도구": {"tool_name": "Edit", "tool_input": {"file_path": str(project / ".claude" / "saegim-outage")}},
        "비슷한 이름": {"tool_name": "Write", "tool_input": {"file_path": str(project / ".claude" / "saegim-outage.bak")}},
        "입력 칸 없음": {"tool_name": "Write"},
    }.items():
        log.unlink(missing_ok=True)
        rc = run(project, home, ev)
        check(f"{label}: 통과·미발송", rc == 0 and sent(log) == [])

    log.unlink(missing_ok=True)
    check("깨진 입력: exit 0", run(project, home, b"not json") == 0 and sent(log) == [])

    # 우편함 스크립트가 없는 환경(다른 PC): 알림을 못 보내도 세션은 막지 않는다
    lone = td / "lone" / "repo"
    lone.mkdir(parents=True)
    ev = {"tool_name": "Write", "tool_input": {"file_path": str(lone / ".claude" / "saegim-outage")}}
    check("우편함 없음: exit 0", run(lone, home, ev) == 0)

n = 9
print("통과" if not bad else "실패: " + ", ".join(bad), f"({n - len(bad)}/{n})")
sys.exit(1 if bad else 0)
