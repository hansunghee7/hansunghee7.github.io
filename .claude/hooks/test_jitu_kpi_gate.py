"""지투 KPI 관문 시험(슈퍼얼라인, 2026-10-12): 결정 요청·예측은 고객수 연결(--kpi) 없이는 기록되지 않는다."""
import os
import subprocess
import sys
import tempfile
import unittest

TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "ops", "jitu_po.py")


def run(*args, env=None):
    e = dict(os.environ)
    e["PYTHONIOENCODING"] = "utf-8"
    e.update(env or {})
    return subprocess.run([sys.executable, TOOL] + list(args), capture_output=True, env=e)


class KpiGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"JITU_PO_DIR": self.tmp.name, "JITU_PO_KPI_GATE": "on"}

    def tearDown(self):
        self.tmp.cleanup()

    def ask(self, *extra):
        return run("ask", "add", "--text", "UX 개선을 할까요", "--rec", "한다, 이유 한 줄", "--default", "보류", *extra, env=self.env)

    def test_ask_without_kpi_is_blocked(self):
        r = self.ask()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("KPI 관문", r.stderr.decode("utf-8"))

    def test_ask_with_kpi_passes_and_records(self):
        r = self.ask("--kpi", "가입 24시간 내 첫 연결을 늘려 고객 획득에 도움")
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8"))
        data = open(os.path.join(self.tmp.name, "asks.jsonl"), encoding="utf-8").read()
        self.assertIn("고객 획득", data)

    def test_not_applicable_needs_a_real_reason(self):
        self.assertNotEqual(self.ask("--kpi", "해당없음:짧음").returncode, 0)
        self.assertEqual(self.ask("--kpi", "해당없음:내부 문서 정리라 고객수와 무관").returncode, 0)

    def test_predict_without_kpi_is_blocked(self):
        r = run("predict", "add", "--change", "x", "--expect", "y", "--metric", "z", "--check-on", "2026-10-20", env=self.env)
        self.assertNotEqual(r.returncode, 0)
        r = run("predict", "add", "--change", "x", "--expect", "y", "--metric", "z", "--check-on", "2026-10-20",
                "--kpi", "첫 연결 비율이 올라 고객 획득이 늘어난다", env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8"))

    def test_temp_store_is_not_gated_by_default(self):
        env = {"JITU_PO_DIR": self.tmp.name}  # 시험용 임시 저장소는 기존 시험이 그대로 돌게 강제하지 않는다
        r = run("ask", "add", "--text", "x를 할까요", "--rec", "한다", "--default", "보류", env=env)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
