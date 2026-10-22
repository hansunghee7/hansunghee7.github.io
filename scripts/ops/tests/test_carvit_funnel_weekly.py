"""carvit_funnel_weekly 단위 시험 (gcloud 호출은 모의)."""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import carvit_funnel_weekly as m  # noqa: E402


def test_classify_paths():
    assert m.classify("https://mcp.carvit.ai/login?next=connect")[0] == "login_next_connect"
    assert m.classify("https://mcp.carvit.ai/login")[0] is None
    assert m.classify("https://mcp.carvit.ai/connect/")[0] == "connect"
    assert m.classify("https://mcp.carvit.ai/access?x=1")[0] == "access"
    assert m.classify("https://mcp.carvit.ai/other")[0] is None


def test_query_masking_drops_secrets():
    _, q = m.classify("https://mcp.carvit.ai/login?next=connect&token=SECRET&email=a@b.c")
    assert q == "next=connect"
    assert "SECRET" not in q and "email" not in q
    assert m.mask_query("next=evil&code=abc") == ""


def test_bot_and_aggregate():
    def e(ts, url, ua):
        return {"timestamp": ts, "httpRequest": {"requestUrl": url, "userAgent": ua}}
    logs = [
        e("2026-10-10T01:00:00Z", "https://x/connect?code=zzz", "Mozilla/5.0"),
        e("2026-10-10T02:00:00Z", "https://x/connect", "Googlebot/2.1"),
        e("2026-10-10T03:00:00Z", "https://x/login?next=connect", "Mozilla/5.0"),
        e("2026-10-10T03:00:00Z", "https://x/zzz", "Mozilla/5.0"),
    ]
    agg = m.aggregate(logs)
    assert agg[("2026-10-10", "connect")] == [2, 1]
    assert agg[("2026-10-10", "login_next_connect")] == [1, 1]
    assert len(agg) == 2


def test_fetch_failure_returns_exit_2(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "OUT_DIR", tmp_path)
    monkeypatch.setattr(sys, "argv", ["x", "--days", "7"])
    fake = mock.Mock(returncode=1, stdout="", stderr="Reauthentication failed")
    with mock.patch.object(m.subprocess, "run", return_value=fake):
        assert m.main() == 2


def test_main_success_writes_files(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "OUT_DIR", tmp_path)
    monkeypatch.setattr(sys, "argv", ["x", "--days", "7"])
    out = '[{"timestamp":"2026-10-10T01:00:00Z","httpRequest":{"requestUrl":"https://x/access","userAgent":"Mozilla"}}]'
    fake = mock.Mock(returncode=0, stdout=out, stderr="")
    with mock.patch.object(m.subprocess, "run", return_value=fake):
        assert m.main() == 0
    assert "access" in (tmp_path / "daily.csv").read_text(encoding="utf-8")
    assert "한계" in (tmp_path / "weekly.md").read_text(encoding="utf-8")
