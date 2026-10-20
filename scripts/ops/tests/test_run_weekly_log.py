"""run_weekly.py가 자식 두 개의 결과를 run.log에 남기고, 한쪽 실패에도 나머지를 돌리며 종료 코드 1을 유지하는지 시험."""
import importlib.util
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(os.path.dirname(HERE), "local_llm", "run_weekly.py")


def _load():
    spec = importlib.util.spec_from_file_location("run_weekly_under_test", TARGET)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_one_ok_one_fail_logged_and_exit1(tmp_path):
    mod = _load()
    (tmp_path / "ok.py").write_text("print('hello-ok')\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text(textwrap.dedent("""
        import sys
        print('partial', file=sys.stderr)
        sys.exit(3)
    """), encoding="utf-8")
    out = tmp_path / "out"
    mod.HERE = str(tmp_path)
    mod.OUT = str(out)
    mod.ROOT = str(tmp_path)
    mod.SCRIPTS = ("bad.py", "ok.py")  # 실패가 먼저여도 뒤 스크립트가 돌아야 한다
    assert mod.main() == 1
    log = (out / "run.log").read_text(encoding="utf-8")
    assert "END bad.py 종료 코드 3" in log
    assert "END ok.py 종료 코드 0" in log
    assert "STDERR bad.py: partial" in log
    assert "STDOUT ok.py: hello-ok" in log
    assert not (out / "last-run.txt").exists()


def test_all_ok_writes_last_run(tmp_path):
    mod = _load()
    (tmp_path / "ok.py").write_text("print('x')\n", encoding="utf-8")
    mod.HERE = mod.ROOT = str(tmp_path)
    mod.OUT = str(tmp_path / "out")
    mod.SCRIPTS = ("ok.py",)
    assert mod.main() == 0
    assert (tmp_path / "out" / "last-run.txt").exists()
