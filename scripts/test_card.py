"""card.py 시험: 임시 폴더와 가짜 우편함으로 카드 수명주기와 규칙 위반을 확인한다."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "card.py"


class CardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cards = self.tmp / "cards"
        self.fake_log = self.tmp / "mail.log"
        self.fake_mail = self.tmp / "fakemail.py"
        self.fake_mail.write_text(
            "import os, sys\n"
            "open(os.environ['MAIL_LOG'], 'a', encoding='utf-8').write('|'.join(sys.argv[1:]) + '\\n')\n"
            "sys.exit(int(os.environ.get('MAIL_RC', '0')))\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def card(self, *args, mail_rc="0"):
        env = dict(os.environ, CARDS_DIR=str(self.cards), MAILBOX_PY=str(self.fake_mail),
                   MAIL_LOG=str(self.fake_log), MAIL_RC=mail_rc, PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                           encoding="utf-8", env=env)
        return r.stdout.strip(), r.returncode

    def cid(self):
        return next(self.cards.glob("*.md")).stem

    def test_1_new_records_tool_time_and_leaves_no_tmp(self):
        out, rc = self.card("new", "시험", "--title", "시험 글", "--by", "마야", "--next", "헤르메스")
        self.assertEqual(rc, 0)
        text = (self.cards / f"{self.cid()}.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"\n\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} 접수 마야")   # 시각은 도구가 기록
        self.assertEqual(list(self.cards.glob("*.tmp")), [])

    def test_2_duplicate_new_fails(self):
        self.card("new", "시험", "--title", "t", "--by", "마야")
        out, rc = self.card("new", "시험", "--title", "t", "--by", "마야")
        self.assertEqual(rc, 2)
        self.assertIn("이미 있는", out)

    def test_3_only_current_or_next_owner_can_advance(self):
        self.card("new", "시험", "--title", "t", "--by", "마야", "--next", "헤르메스")
        i = self.cid()
        out, rc = self.card("advance", i, "--stage", "수집", "--by", "탐")
        self.assertEqual(rc, 2)
        self.assertIn("차례", out)
        out, rc = self.card("advance", i, "--stage", "수집", "--by", "헤르메스", "--next", "제미나이")
        self.assertEqual(rc, 0)
        _, rc = self.card("advance", i, "--stage", "검증", "--by", "탐", "--force")   # 예외는 명시적으로만
        self.assertEqual(rc, 0)

    def test_4_invalid_stage_rejected(self):
        self.card("new", "시험", "--title", "t", "--by", "마야")
        out, rc = self.card("advance", self.cid(), "--stage", "엉뚱", "--by", "마야")
        self.assertEqual(rc, 2)

    def test_5_ask_boss_sets_state_and_sends_maya_format(self):
        self.card("new", "시험", "--title", "t", "--by", "마야")
        i = self.cid()
        out, rc = self.card("ask-boss", i, "--by", "마야", "--need", "1~3번 중 하나를 골라 알려 주세요",
                            "--notify", "--decision", "9/22 글 주제 컨펌 ①", "--summary", "후보 3개, 추천 1번(이유)")
        self.assertEqual(rc, 0)
        self.assertIn("알림 발송: 성공", out)
        sent = self.fake_log.read_text(encoding="utf-8").strip().split("|")
        self.assertEqual(sent[:3], ["send", "사장님", "9/22 글 주제 컨펌 ①"])       # 제목=결정 대상
        self.assertIn("후보 3개, 추천 1번(이유)", sent)                             # 본문=선택지 수와 추천
        self.assertIn("1~3번 중 하나를 골라 알려 주세요", sent)                      # --ask=할 일 한 줄
        show, _ = self.card("show", i)
        self.assertIn("사장님차례", show)
        self.assertIn("👉", show)

    def test_6_notify_needs_decision_and_summary(self):
        self.card("new", "시험", "--title", "t", "--by", "마야")
        out, rc = self.card("ask-boss", self.cid(), "--by", "마야", "--need", "골라 주세요", "--notify")
        self.assertEqual(rc, 2)
        self.assertFalse(self.fake_log.exists())

    def test_7_block_and_done_and_show_durations(self):
        self.card("new", "시험", "--title", "시험 글", "--by", "마야", "--next", "헤르메스")
        i = self.cid()
        self.card("advance", i, "--stage", "수집", "--by", "헤르메스", "--out", "reports/a.md")
        self.card("block", i, "--by", "헤르메스", "--reason", "열람 실패")
        out, _ = self.card("show", i)
        self.assertIn("막힘: 열람 실패", out)
        self.card("done", i, "--by", "헤르메스")
        out, _ = self.card("show", i)
        self.assertIn("완료", out)
        self.assertRegex(out, r"전체 \d+초, 산출물 1건")
        listing, _ = self.card("show")
        self.assertIn(i, listing)


if __name__ == "__main__":
    unittest.main()
