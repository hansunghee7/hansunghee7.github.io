"""pythonw(작업 스케줄러)는 sys.stdout이 None이다. brief_snapshot.py가 import 시점에 죽지 않는지 본다(2026-10-20 05:40 실행 결과 1 사고)."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "brief_snapshot.py"


def test_import_survives_none_stdout():
    code = (
        "import sys, runpy\n"
        "sys.stdout = None; sys.stderr = None\n"
        f"sys.argv = ['x', '--help']\n"
        f"try:\n    runpy.run_path(r'{SCRIPT}', run_name='__main__')\n"
        "except SystemExit:\n    pass\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
