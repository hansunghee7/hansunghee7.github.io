"""probe_mail_link 모킹 시험(네트워크 없음). 실행: python scripts/ops/test_probe_mail_link.py"""
import io
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(__file__))
import probe_mail_link as p


class R(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def opener_for(rows, seen=None):
    def op(req, timeout=0):
        if seen is not None:
            seen.append(req)
        return R(json.dumps(rows).encode())
    return op


class T(unittest.TestCase):
    def setUp(self):
        os.environ["PROBE_MAIL_READ_KEY"] = "dummy-key-xyz"

    def test_link_since_and_headers(self):
        seen = []
        rows = [{"received_at": "2026-10-20T01:00:00Z", "text_body": "로그인: https://mcp.carvit.ai/auth/callback?code=abc123 끝"}]
        self.assertEqual(p.main(["--since", "2026-10-20T00:00:00Z"], opener_for(rows, seen)), 0)
        r = seen[0]
        self.assertIn("since=2026-10-20T00%3A00%3A00Z", r.full_url)
        self.assertIn("Mozilla", r.headers["User-agent"])
        self.assertEqual(r.headers["Authorization"], "Bearer dummy-key-xyz")

    def test_latest_wins_and_qp_raw(self):
        rows = [{"received_at": "2026-10-20T01:00:00Z", "text_body": "https://mcp.carvit.ai/old?code=1"},
                {"received_at": "2026-10-20T02:00:00Z", "text_body": "", "raw": "x\r\nhttps://mcp.carvit.ai/auth/callback?code=3D=\r\nnew\r\n"}]
        self.assertEqual(p.latest_link(rows), "https://mcp.carvit.ai/auth/callback?code=new")

    def test_ignores_foreign_links(self):
        self.assertIsNone(p.latest_link([{"received_at": "1", "text_body": "https://evil.example/x https://mcp.carvit.ai.evil.com/x"}]))

    def test_none_exit2(self):
        self.assertEqual(p.main([], opener_for([])), 2)

    def test_no_key_exit3(self):
        del os.environ["PROBE_MAIL_READ_KEY"]
        os.environ.pop("MAIL_PROBE_READ_KEY", None)
        self.assertEqual(p.main(["--env-file", "C:/nonexistent/none"], opener_for([])), 3)

    def test_http_error_exit4(self):
        def op(req, timeout=0):
            raise urllib.error.HTTPError("u", 403, "x", {}, None)
        self.assertEqual(p.main([], op), 4)

    def test_code_option(self):
        rows = [{"received_at": "2026-10-20T01:00:00Z", "text_body": "color #123456 https://x.io/a/1234567 코드 482913 입니다"}]
        self.assertEqual(p.latest_by(rows, p.extract_code), "482913")
        rows = [{"received_at": "1", "text_body": "", "html_body": "<style>.a{x:999999}</style><p>Code: <b>73920184</b></p>"}]
        self.assertEqual(p.latest_by(rows, p.extract_code), "73920184")
        self.assertEqual(p.main(["--code"], opener_for([{"received_at": "1", "text_body": "no digits 12345"}])), 2)

    def test_any_link_option(self):
        rows = [{"received_at": "1", "text_body": "https://evil.example/x https://github.com/help https://github.com/users/x/emails/confirm?token=abc"}]
        self.assertEqual(p.latest_by(rows, p.extract_any_link), "https://github.com/users/x/emails/confirm?token=abc")
        self.assertIsNone(p.latest_by([{"received_at": "1", "text_body": "https://github.com.evil.com/x"}], p.extract_any_link))

    def test_options_exit_codes(self):
        rows = [{"received_at": "1", "text_body": "코드 112233 https://github.com/verify?t=1"}]
        self.assertEqual(p.main(["--code"], opener_for(rows)), 0)
        self.assertEqual(p.main(["--any-link"], opener_for(rows)), 0)
        self.assertEqual(p.main(["--any-link"], opener_for([])), 2)


if __name__ == "__main__":
    unittest.main()
