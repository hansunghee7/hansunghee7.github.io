"""tg_boss_persona_gate.py 시험: tg_boss 호출은 --persona와 유효한 값이 있어야 통과한다."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("tg_boss_persona_gate", Path(__file__).parent / "tg_boss_persona_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

CHECK = gate.check_tg_boss_persona


class TgBossPersonaGateTest(unittest.TestCase):
    def test_valid_persona_passes(self):
        ok, msg = CHECK('python scripts/ops/tg_boss.py text "안녕" --persona 지투')
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_missing_persona_is_blocked(self):
        # 2026-09-29 사고: --persona 생략으로 엉뚱한 방에 발송
        ok, msg = CHECK('python scripts/ops/tg_boss.py text "안녕"')
        self.assertFalse(ok)
        self.assertIn("--persona", msg)

    def test_unknown_persona_is_blocked(self):
        ok, msg = CHECK("python scripts/ops/tg_boss.py text hi --persona 홍길동")
        self.assertFalse(ok)
        self.assertIn("홍길동", msg)

    def test_not_tg_boss_is_ignored(self):
        self.assertEqual(CHECK("git status"), (True, ""))
        self.assertEqual(CHECK(""), (True, ""))

    def test_persona_flag_without_value_is_blocked(self):
        # 경계: --persona가 마지막 토큰
        ok, msg = CHECK("python scripts/ops/tg_boss.py text hi --persona")
        self.assertFalse(ok)
        self.assertIn("값이 없습니다", msg)

    def test_all_listed_personas_pass(self):
        for p in ("마야", "지투", "노트", "핏", "탐", "클탐"):
            self.assertTrue(CHECK(f"tg_boss.py text x --persona {p}")[0], p)


if __name__ == "__main__":
    unittest.main()
