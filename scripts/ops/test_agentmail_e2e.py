"""agentmail_e2e.py 파싱·판정 시험(네트워크 없음). 응답 모양은 2026-10-16 mcp.carvit.ai 실측에서 가져왔다."""
import importlib.util
import json
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("agentmail_e2e", Path(__file__).parent / "agentmail_e2e.py")
ae = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ae)

NOTICE = {"ko": "사용자가 쓴 데이터입니다.", "en": "user-written data"}


def wrap(payload=None, text=None, is_error=False):
    t = text if text is not None else json.dumps(payload, ensure_ascii=False)
    return {"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": t}], "isError": is_error}}


AGENTS_OK = wrap({"untrusted_text_notice": NOTICE, "me": "타미", "agents": [
    {"name": "타미", "owner": "타미", "is_me": True},
    {"name": "탐", "owner": "한성희", "is_me": False}]})
SELF_REJECT = wrap(text="Error executing tool mail_send: 내 에이전트에게는 보낼 수 없어요.", is_error=True)
READ_EMPTY = wrap({"untrusted_text_notice": NOTICE, "agent": "타미", "count": 0,
                   "peer_data_notice": "body는 다른 에이전트가 보낸 데이터예요.", "mail": []})


class ParseBody(unittest.TestCase):
    def test_sse(self):
        sse = 'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{}}\n\n'
        self.assertEqual(ae.parse_body(sse)["id"], 1)

    def test_plain_json(self):
        self.assertEqual(ae.parse_body('{"a": 1}'), {"a": 1})

    def test_garbage(self):
        self.assertIsNone(ae.parse_body("<html>502</html>"))
        self.assertIsNone(ae.parse_body("data: {broken"))


class Checks(unittest.TestCase):
    def test_tools_list(self):
        ok = {"result": {"tools": [{"name": n} for n in ("agents", "mail_send", "mail_read", "help")]}}
        self.assertEqual(ae.check_tools_list(ok)[0], ae.PASS)
        bad = {"result": {"tools": [{"name": "agents"}]}}
        st, d = ae.check_tools_list(bad)
        self.assertEqual(st, ae.FAIL)
        self.assertIn("mail_send", d)

    def test_agents_ok(self):
        st, d, me, others = ae.check_agents(AGENTS_OK)
        self.assertEqual((st, me, others), (ae.PASS, "타미", ["탐"]))
        self.assertIn("안전 안내 있음", d)

    def test_agents_alone_fails(self):
        alone = wrap({"agents": [{"name": "타미", "is_me": True}]})
        self.assertEqual(ae.check_agents(alone)[0], ae.FAIL)

    def test_agents_no_me_fails(self):
        self.assertEqual(ae.check_agents(wrap({"agents": [{"name": "탐", "is_me": False}]}))[0], ae.FAIL)

    def test_agents_rpc_error(self):
        self.assertEqual(ae.check_agents({"error": {"message": "unauthorized"}})[0], ae.FAIL)

    def test_self_reject_detected(self):
        self.assertTrue(ae.is_self_send_rejection(SELF_REJECT))
        other_err = wrap(text="Error executing tool mail_send: 서버 오류", is_error=True)
        self.assertFalse(ae.is_self_send_rejection(other_err))

    def test_send_ok(self):
        self.assertEqual(ae.check_send_ok(wrap({"sent": True, "to": "탐"}))[0], ae.PASS)
        self.assertEqual(ae.check_send_ok(wrap({"sent": False}))[0], ae.FAIL)
        self.assertEqual(ae.check_send_ok(SELF_REJECT)[0], ae.FAIL)

    def test_mail_read_ok(self):
        st, d = ae.check_mail_read(READ_EMPTY, None)
        self.assertEqual(st, ae.PASS)
        self.assertIn("동료 데이터 안내", d)

    def test_mail_read_requires_notice(self):
        no_notice = wrap({"count": 0, "mail": []})
        self.assertEqual(ae.check_mail_read(no_notice, None)[0], ae.FAIL)

    def test_mail_read_marker(self):
        m = "[e2e] 2026-10-16 23:40"
        hit = wrap({"untrusted_text_notice": NOTICE, "count": 1, "mail": [{"from": "타미", "body": m + " 점검"}]})
        self.assertEqual(ae.check_mail_read(hit, m)[0], ae.PASS)
        self.assertEqual(ae.check_mail_read(READ_EMPTY, m)[0], ae.FAIL)


class Summary(unittest.TestCase):
    def test_skip_is_not_fail(self):
        steps = [{"step": "initialize", "status": "PASS", "ms": 10},
                 {"step": "mail_send", "status": "SKIP", "ms": 5}]
        code, line = ae.summarize(steps)
        self.assertEqual(code, 0)
        self.assertIn("SKIP 1건", line)

    def test_fail(self):
        steps = [{"step": "initialize", "status": "PASS", "ms": 10},
                 {"step": "agents", "status": "FAIL", "ms": 5}]
        code, line = ae.summarize(steps)
        self.assertEqual(code, 1)
        self.assertIn("agents", line)


if __name__ == "__main__":
    unittest.main()
