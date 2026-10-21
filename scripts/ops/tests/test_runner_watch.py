"""[옛이름 허용: 유료 실행기 관문이 옛 이름과 새 이름을 함께 인식해야 함]
runner_watch.py 자동 우회 판단(decide) 시험. 네트워크·gh 호출 없음."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json  # noqa: E402
import pytest  # noqa: E402
import runner_watch  # noqa: E402
from runner_watch import HOSTED_VALUE, SELF_VALUE, decide  # noqa: E402


def test_online_without_var_does_nothing():
    assert decide(True, 0, None) == ("none", 0)
    assert decide(True, 3, SELF_VALUE) == ("none", 0)


def test_first_offline_waits():
    assert decide(False, 0, None) == ("none", 1)


def test_second_offline_falls_back():
    assert decide(False, 1, None) == ("fallback", 2)
    assert decide(False, 1, SELF_VALUE) == ("fallback", 2)


def test_offline_while_in_fallback_stays():
    assert decide(False, 5, HOSTED_VALUE) == ("none", 6)


def test_online_again_restores():
    assert decide(True, 4, HOSTED_VALUE) == ("restore", 0)


class FakeGh:
    """gh 호출을 대신하는 가짜. store: {이름: 값}, fail_on: (메서드, 이름) 쓰기 실패 지정."""

    def __init__(self, store, fail_on=()):
        self.store, self.fail_on, self.calls = dict(store), set(fail_on), []

    def __call__(self, args):
        self.calls.append(args)
        method = args[args.index("-X") + 1] if "-X" in args else "GET"
        path = next(a for a in args if a.startswith("repos/"))
        name = path.rsplit("/", 1)[-1]
        form = {args[i + 1].split("=", 1)[0]: args[i + 1].split("=", 1)[1] for i, a in enumerate(args) if a == "-f"}
        if method == "POST":
            name = form["name"]
        if (method, name) in self.fail_on:
            return _R(1, "", "boom")
        if method == "GET":
            if name not in self.store:
                return _R(1, "", "HTTP 404 Not Found")
            return _R(0, json.dumps({"value": self.store[name]}), "")
        if method in ("PATCH", "POST"):
            self.store[name] = form["value"]
            return _R(0, "", "")
        if method == "DELETE":
            self.store.pop(name, None)
            return _R(0, "", "")
        raise AssertionError(args)


class _R:
    def __init__(self, rc, out, err):
        self.returncode, self.stdout, self.stderr = rc, out, err


NEW, OLD = runner_watch.VAR_NEW, runner_watch.VAR_OLD


def _fake(monkeypatch, store, fail_on=()):
    f = FakeGh(store, fail_on)
    monkeypatch.setattr(runner_watch, "gh", f)
    return f


def test_read_only_new(monkeypatch):
    _fake(monkeypatch, {NEW: SELF_VALUE})
    assert runner_watch.read_var() == (SELF_VALUE, "")


def test_read_only_old(monkeypatch):
    _fake(monkeypatch, {OLD: HOSTED_VALUE})
    assert runner_watch.read_var() == (HOSTED_VALUE, "")


def test_read_neither(monkeypatch):
    _fake(monkeypatch, {})
    assert runner_watch.read_var() == (None, "")


def test_mismatch_new_self_old_hosted_means_fallback(monkeypatch, capsys):
    _fake(monkeypatch, {NEW: SELF_VALUE, OLD: HOSTED_VALUE})
    value, err = runner_watch.read_var()
    assert (value, err) == (HOSTED_VALUE, "")
    assert runner_watch.is_hosted(value)
    assert "불일치" in capsys.readouterr().out


def test_mismatch_new_hosted_old_self_means_fallback(monkeypatch, capsys):
    _fake(monkeypatch, {NEW: HOSTED_VALUE, OLD: SELF_VALUE})
    assert runner_watch.read_var()[0] == HOSTED_VALUE
    assert "불일치" in capsys.readouterr().out


def test_write_creates_missing_and_patches_existing(monkeypatch):
    f = _fake(monkeypatch, {OLD: HOSTED_VALUE})  # 새 이름은 404
    assert runner_watch.write_var(SELF_VALUE) == (True, "")
    assert f.store == {NEW: SELF_VALUE, OLD: SELF_VALUE}


def test_write_failure_rolls_back_first(monkeypatch):
    f = _fake(monkeypatch, {NEW: SELF_VALUE, OLD: SELF_VALUE}, fail_on=[("PATCH", OLD)])
    with pytest.raises(RuntimeError) as e:
        runner_watch.write_var(HOSTED_VALUE)
    assert OLD in str(e.value) and "되돌림 성공" in str(e.value)
    assert f.store == {NEW: SELF_VALUE, OLD: SELF_VALUE}


def test_write_failure_rollback_deletes_newly_created(monkeypatch):
    f = _fake(monkeypatch, {OLD: SELF_VALUE}, fail_on=[("PATCH", OLD)])  # 새 이름은 POST로 만들어진 뒤 옛 이름 실패
    with pytest.raises(RuntimeError):
        runner_watch.write_var(HOSTED_VALUE)
    assert f.store == {OLD: SELF_VALUE}


def test_write_rollback_failure_is_reported(monkeypatch):
    _fake(monkeypatch, {NEW: SELF_VALUE, OLD: SELF_VALUE}, fail_on=[("PATCH", OLD)])
    f = runner_watch.gh
    orig = f.__call__
    patches = []

    def flaky(args):
        if "-X" in args and args[args.index("-X") + 1] == "PATCH" and args[args.index("-X") + 2].endswith(NEW):
            patches.append(1)
            if len(patches) == 2:  # 되돌림 시도도 실패
                return _R(1, "", "boom2")
        return orig(args)

    monkeypatch.setattr(runner_watch, "gh", flaky)
    with pytest.raises(RuntimeError) as e:
        runner_watch.write_var(HOSTED_VALUE)
    assert "되돌림 실패" in str(e.value)


def test_write_aborts_when_lookup_fails(monkeypatch):
    def bad(args):
        return _R(1, "", "HTTP 500")
    monkeypatch.setattr(runner_watch, "gh", bad)
    with pytest.raises(RuntimeError):
        runner_watch.write_var(SELF_VALUE)
