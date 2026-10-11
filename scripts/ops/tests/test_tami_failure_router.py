"""타미 실패 라우터 판정 시험: 성공(부정 표현 포함) 3종, 실패 3종, 중복 처리 방지."""
import importlib.util
import json
import os
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location("tfr", Path(__file__).resolve().parents[1] / "tami_failure_router.py")
tfr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tfr)


def put(path, text, age=300):
    path.write_text(text, encoding="utf-8")
    t = time.time() - age
    os.utime(path, (t, t))


def md(result, code=0):
    return f"# t\n\n## 의뢰(원본)\n\n실패하면 멈추고 보고, 막힘 시 보고\n\n## 결과\n\n{result}\n\n## 메타\n- exit code: {code}\n"


def test_success_with_negations():
    assert tfr.detect(md("성공: rc=0\n- 막힌 곳: 없음\n- 실패 0건")) is None
    assert tfr.detect(md("- 성공/실패: 성공 (rc=0)\n- 막힌 곳 없음")) is None
    assert tfr.detect(md("Failure\n\n- vids 로그 오류 한 줄: 씬29 막힘\n- 막힌 곳: 없음 - 진단 완료")) is None


def test_failures_detected():
    assert tfr.detect(md("실패: 씬24 없음"))[0] == "실패"
    assert tfr.detect(md("ok", code=1))[0] == "exit code"
    assert tfr.detect(md("명령이 3분 넘게 응답 없어 중단"))[0] == "막힘"


def test_rc_failure_even_with_blocker_line():
    assert tfr.detect(md("작업 rc=3\n막힌 곳: 없음"))[0] == "rc/exit"


def test_no_duplicate_processing(tmp_path, monkeypatch):
    rep = tmp_path / "r"
    rep.mkdir()
    put(rep / "a-result.md", md("실패: 뭔가 깨짐"))
    sent = []
    monkeypatch.setattr(tfr, "mail", lambda n, q, d: sent.append(n))
    st, fl = tmp_path / "state.json", tmp_path / "f.jsonl"
    st.write_text("[]", encoding="utf-8")
    assert len(tfr.run(rep, st, fl)) == 1
    assert tfr.run(rep, st, fl) == []
    assert sent == ["a-result.md"]
    assert len(fl.read_text(encoding="utf-8").splitlines()) == 1
    assert json.loads(st.read_text(encoding="utf-8")) == ["a-result.md"]


def test_first_run_seeds_without_alert(tmp_path, monkeypatch):
    rep = tmp_path / "r"
    rep.mkdir()
    put(rep / "old-result.md", md("실패"))
    monkeypatch.setattr(tfr, "mail", lambda *a: (_ for _ in ()).throw(AssertionError("mail")))
    assert tfr.run(rep, tmp_path / "s.json", tmp_path / "f.jsonl") == []
    assert not (tmp_path / "f.jsonl").exists()


def _setup(tmp_path, monkeypatch):
    rep = tmp_path / "r"
    rep.mkdir()
    sent = []
    monkeypatch.setattr(tfr, "mail", lambda n, q, d: sent.append(n))
    st = tmp_path / "state.json"
    st.write_text("[]", encoding="utf-8")
    return rep, st, tmp_path / "f.jsonl", sent


def test_broken_state_exits_2(tmp_path, monkeypatch):
    rep, st, fl, sent = _setup(tmp_path, monkeypatch)
    st.write_text("{깨짐", encoding="utf-8")
    try:
        tfr.run(rep, st, fl)
        assert False
    except tfr.StateError:
        pass
    import subprocess, sys
    r = subprocess.run([sys.executable, str(Path(tfr.__file__)), "--reports", str(rep), "--state", str(st)], capture_output=True)
    assert r.returncode == 2 and sent == []


def test_mail_cap_five_plus_summary(tmp_path, monkeypatch):
    rep, st, fl, sent = _setup(tmp_path, monkeypatch)
    for i in range(8):
        put(rep / f"f{i}-result.md", md("실패: x"))
    assert len(tfr.run(rep, st, fl)) == 8
    assert len(sent) == 6 and sent[-1] == "(외 3건)"
    assert len(fl.read_text(encoding="utf-8").splitlines()) == 8


def test_skip_non_tami_report(tmp_path, monkeypatch):
    rep, st, fl, sent = _setup(tmp_path, monkeypatch)
    put(rep / "free-result.md", "# 자유 보고\n\n## 결과\n\n실패 많음\n")
    assert tfr.run(rep, st, fl) == [] and sent == []


def test_fresh_file_deferred_not_recorded(tmp_path, monkeypatch):
    rep, st, fl, sent = _setup(tmp_path, monkeypatch)
    put(rep / "new-result.md", md("실패: x"), age=5)
    assert tfr.run(rep, st, fl) == []
    assert json.loads(st.read_text(encoding="utf-8")) == []
    put(rep / "new-result.md", md("실패: x"), age=120)
    assert len(tfr.run(rep, st, fl)) == 1


def test_result_heading_exact():
    assert tfr.detect(md("실패: x").replace("## 결과\n", "## 결과물\n")) is None
