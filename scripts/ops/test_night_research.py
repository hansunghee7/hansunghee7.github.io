import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "goosolar"))
import night_research as nr
from openai import RateLimitError

LINE = "주장 | https://example.com | quote text long enough"


def rate_error():
    return RateLimitError("Rate limit reached on tokens per day (TPD)",
                          response=mock.Mock(status_code=429, headers={}, request=None), body=None)


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.spec = os.path.join(self.d, "spec.json")
        json.dump({"name": "t", "questions": [
            {"id": "Q1", "group": "G", "q": "one"}, {"id": "Q2", "group": "G", "q": "two"}, {"id": "Q3", "group": "H", "q": "three"}]},
            open(self.spec, "w", encoding="utf-8"))
        for p in (mock.patch.object(nr, "load_env", lambda p: {"GROQ_API_KEY": "x"}),
                  mock.patch.object(nr, "shin_pc_up", lambda: False),
                  mock.patch.object(nr, "verify", lambda c: ("일치", "테스트"))):
            p.start()

    def tearDown(self):
        mock.patch.stopall()

    def run_main(self, ask):
        with mock.patch.object(nr, "ask", ask), mock.patch.object(sys, "argv", ["x", self.spec, self.d]):
            nr.main()
        return open(os.path.join(self.d, "t.md"), encoding="utf-8").read()

    def test_resume_after_rate_limit(self):
        calls = []

        def first(client, q):
            calls.append(q)
            if q == "two":
                raise rate_error()
            return LINE, 100

        rep1 = self.run_main(first)
        self.assertIn("1개 완료", rep1)
        self.assertIn("남음 Q2, Q3", rep1)
        self.assertEqual(calls, ["one", "two"])  # 429 뒤 Q3은 시도하지 않는다

        calls.clear()

        def second(client, q):
            calls.append(q)
            return LINE, 50

        rep2 = self.run_main(second)
        self.assertEqual(calls, ["two", "three"])  # 끝난 Q1은 다시 하지 않는다
        self.assertIn("전부 완료", rep2)
        self.assertIn("꺼져 있음(구PC 단독 가동)", rep2)
        self.assertEqual(rep2.count("| 일치 |"), 3)

    def test_finished_questions_not_repeated(self):
        self.run_main(lambda c, q: (LINE, 10))
        calls = []
        self.run_main(lambda c, q: (calls.append(q) or "x | - | -", 1))
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
