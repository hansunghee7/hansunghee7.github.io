import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import preflight as pf  # noqa: E402

SECRET = "sk-SECRET-VALUE-123"


def fake_run(cmd, timeout=pf.TIMEOUT):
    s = " ".join(map(str, cmd))
    if "pass.py" in s and "ping" in s:
        return 0, json.dumps({"ok": True, "host": "x", "token": SECRET})
    if "pass.py" in s and "list" in s:
        return 0, json.dumps({"ok": True, "locked": True, "keys": [{"name": "a", "value": SECRET}] * 3})
    if cmd[0] == "ssh":
        return 0, "ok\nMemAvailable:    2000000 kB\n1"
    if cmd[:2] == ["gh", "auth"]:
        return 0, "Logged in token " + SECRET
    if "rev-parse" in s:
        return 0, "main" if "hansunghee7" in s else "feat/x"
    if "rev-list" in s:
        return 0, "2"
    return 1, ""


class PreflightTest(unittest.TestCase):
    def run_all(self, ollama_ok=True):
        def uo(*a, **k):
            if not ollama_ok:
                raise OSError("down")
            m = mock.MagicMock()
            m.__enter__.return_value.read.return_value = json.dumps({"models": [{}, {}]}).encode()
            return m
        with mock.patch.object(pf, "run", fake_run), mock.patch("urllib.request.urlopen", uo):
            return pf.collect()

    def test_levels_and_no_secret(self):
        res = self.run_all()
        text = "\n".join(m for _, _, m in res)
        self.assertNotIn(SECRET, text)
        st = {m: s for _, s, m in res}
        self.assertTrue(any(s == pf.WARN and "1953MB" in m for _, s, m in res))
        self.assertIn("locked=true, 키 3개", text)
        self.assertTrue(any(s == pf.WARN and "cxo-db" in m for _, s, m in res))
        self.assertTrue(any(s == pf.WARN and "뒤처짐 2커밋" in m for _, s, m in res))
        self.assertEqual(sum(1 for s in st.values() if s == pf.FAIL), 0)

    def test_ollama_down_is_warn_and_log(self):
        res = self.run_all(ollama_ok=False)
        self.assertTrue(any(s == pf.WARN and "Ollama" in m for _, s, m in res))
        import tempfile
        p = os.path.join(tempfile.mkdtemp(), "l.jsonl")
        rec = pf.write_log(res, p)
        line = json.loads(open(p, encoding="utf-8").readline())
        self.assertEqual(line["fail"], 0)
        self.assertEqual(line["warn"], rec["warn"])
        self.assertNotIn(SECRET, open(p, encoding="utf-8").read())

    def test_exit_code_on_fail(self):
        def bad(cmd, timeout=pf.TIMEOUT):
            return -1, "시간 초과"
        with mock.patch.object(pf, "run", bad), mock.patch.object(pf, "write_log", lambda r: {"ok": 0, "warn": 0, "fail": 1}), \
                mock.patch("urllib.request.urlopen", side_effect=OSError):
            self.assertEqual(pf.main(), 1)


if __name__ == "__main__":
    unittest.main()
