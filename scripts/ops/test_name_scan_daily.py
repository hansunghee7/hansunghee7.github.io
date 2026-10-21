import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import env_alias_daily as ea  # noqa: E402
import name_scan_daily as ns  # noqa: E402


def test_parse_summary_fail():
    text = "# x\n\n- 실행 시각: a\n- 판정: **완료 불가** (위반 3, 예정 12, 미확인 1). 종료 코드는 위반 기준(1)\n- complete=false\n"
    assert ns.parse_summary(text) == {"verdict": "완료 불가", "violation": 3, "planned": 12, "unverified": 1}


def test_parse_summary_ok_and_missing():
    assert ns.parse_summary("a\n- 판정: **완료 가능** (위반 0, 예정 0, 미확인 0)\n")["verdict"] == "완료 가능"
    assert ns.parse_summary("판정 없음\n") is None


def test_parse_summary_partial_numbers():
    s = ns.parse_summary("- 판정: **완료 불가** (예정 5)\n")
    assert (s["violation"], s["planned"], s["unverified"]) == (0, 5, 0)


def test_summary_line():
    s = {"verdict": "완료 불가", "violation": 1, "planned": 2, "unverified": 3}
    assert ns.summary_line(s, "2026-10-22") == "2026-10-22 판정=완료 불가 위반=1 예정=2 미확인=3"


def test_count_needle():
    assert ea.count_needle('a env_alias_legacy b\nenv_alias_legacy') == 2
    assert ea.count_needle("") == 0


def test_parse_run_ids_limit_and_bad_json():
    raw = "[" + ",".join('{"databaseId": %d, "name": "x"}' % i for i in range(30)) + "]"
    assert ea.parse_run_ids(raw) == list(range(20))
    assert ea.parse_run_ids("not json") == []


def test_present_names():
    assert ea.present_names("A\r\n B \n\n") == {"A", "B"}


def test_format_line_warning():
    ok = ea.format_line("T", 4, 0, ["x"], ["y", "z"], 0)
    assert ok == "T 실행=4 별칭로그=0 옛이름=1/3 새이름=2/3"
    bad = ea.format_line("T", 4, 2, [], [], 1)
    assert bad.endswith("조회실패=1 주의")
