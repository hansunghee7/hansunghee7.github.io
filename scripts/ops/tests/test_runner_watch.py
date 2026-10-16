"""runner_watch.py 자동 우회 판단(decide) 시험. 네트워크·gh 호출 없음."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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
