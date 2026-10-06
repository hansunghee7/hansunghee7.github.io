"""ops-status.py 시험: python .claude/hooks/test_ops_status.py
상태 파일(state.json)을 임시 폴더에 만들어, 문제가 있을 때만 출력하고 파일이 없거나 깨졌으면 조용히 통과하는지 본다."""
import json, os, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

H = Path(__file__).with_name("ops-status.py")
KST = timezone(timedelta(hours=9))


def run(state_dir, content=None):
    if content is not None:
        Path(state_dir, "state.json").write_text(content, encoding="utf-8")
    p = subprocess.run([sys.executable, str(H)], capture_output=True, env={**os.environ, "OPS_STATE_DIR": str(state_dir)})
    return p.returncode, p.stdout.decode("utf-8", "replace")


def entry(status, minutes_ago, name="작업", detail="상세"):
    t = (datetime.now(KST) - timedelta(minutes=minutes_ago)).isoformat()
    return {"name": name, "status": status, "detail": detail, "checked": t, "since": t}


bad = []


def check(label, cond):
    if not cond:
        bad.append(label)


with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    rc, out = run(d)  # 상태 파일 없음
    check("파일 없음: 조용히 통과", rc == 0 and out == "")
    rc, out = run(d, "{깨진")
    check("깨진 json: 조용히 통과", rc == 0 and out == "")
    rc, out = run(d, json.dumps({}))
    check("빈 상태: 조용히 통과", rc == 0 and out == "")
    rc, out = run(d, json.dumps({"a": entry("ok", 5), "b": entry("warn", 5)}))
    check("정상/주의만: 출력 없음", rc == 0 and out == "")
    rc, out = run(d, json.dumps({"a": entry("fail", 5, "헤르메스 폴러", "마지막 성공 3시간 전")}))
    check("fail: 문제 줄 출력", rc == 0 and "🔴 지금 문제: 헤르메스 폴러" in out and "STATUS.md" in out)
    rc, out = run(d, json.dumps({"a": entry("ok", 90)}))
    check("감시가 60분 넘게 멈춤: 경고 출력", rc == 0 and "분째 안 돌고" in out)
    rc, out = run(d, json.dumps({f"k{i}": entry("fail", 5, f"작업{i}") for i in range(8)}))
    check("fail 8건: 5건만 나열하고 나머지는 건수", out.count("지금 문제") == 5 and "그 밖에 문제 3건" in out)

n = 7
print("통과" if not bad else "실패: " + ", ".join(bad), f"({n - len(bad)}/{n})")
sys.exit(1 if bad else 0)
