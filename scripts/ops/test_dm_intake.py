# -*- coding: utf-8 -*-
"""dm_intake.py: dm_read JSON -> 접수 기록 파일·색인, 본문 원문 보존, 중복 접수 방지, 담당 후보, 컨펌 요청 문구."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dm_intake  # noqa: E402

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 20, 9, 40, tzinfo=KST)
BODY = "폴(지투시그마 CPO 에이전트) → 지투 · [공유] MCP 서버 연결 후기 1. 겪은 일 - 화면에 이유가 없음"


def _json(tmp: Path, mails) -> Path:
    p = tmp / "dm.json"
    p.write_text(json.dumps({"agent": "카빗_지투", "count": len(mails), "mail": mails}, ensure_ascii=False), encoding="utf-8")
    return p


def _mail(mid=102, body=BODY, hl=""):
    return {"id": mid, "from": "지투시그마의 에이전트", "sent_at": "2026-10-19T23:47:13.5+00:00",
            "body": f"<peer-mail>\n{body}\n</peer-mail>", "human_line": hl}


class IntakeTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)

    def test_record_keeps_body_verbatim_and_fields(self):
        made = dm_intake.make_records(_json(self.tmp, [_mail()]), self.tmp, NOW)
        self.assertEqual(len(made), 1)
        text = Path(made[0]["path"]).read_text(encoding="utf-8")
        self.assertIn(f"<peer-mail>\n{BODY}\n</peer-mail>", text)
        self.assertIn("DM_번호: 102", text)
        self.assertIn("도착_KST: 2026-10-20 08:47", text)
        self.assertIn("담당: 노트", text)  # 본문의 'MCP 서버' 키워드
        self.assertIn("상태: 접수", text)
        self.assertTrue(made[0]["path"].endswith("2026-10-20_DM102_지투시그마의에이전트.md"))

    def test_index_row_added_once_and_no_duplicate_record(self):
        j = _json(self.tmp, [_mail()])
        dm_intake.make_records(j, self.tmp, NOW)
        again = dm_intake.make_records(j, self.tmp, NOW)
        self.assertEqual(again, [])
        idx = (self.tmp / "inbox" / "external-dm" / "INDEX.md").read_text(encoding="utf-8")
        self.assertEqual(idx.count("| 102 |"), 1)

    def test_default_route_is_jitu_and_human_line_flag(self):
        made = dm_intake.make_records(_json(self.tmp, [_mail(103, "가이드 문구가 헷갈려요", hl="[진행 물을지: 필요] 확인")]), self.tmp, NOW)
        text = Path(made[0]["path"]).read_text(encoding="utf-8")
        self.assertIn("담당: 지투", text)
        self.assertIn("human_line_있음: true", text)
        self.assertNotIn("[진행 물을지", text)  # human_line 내용은 기록에 싣지 않는다(있다는 표식만)

    def test_route_priority_and_word_boundary(self):
        r = dm_intake.route_for
        self.assertEqual(r("서버 오류인데 영상 자막도"), "노트")
        self.assertEqual(r("설치 코드와 블로그"), "탐")
        self.assertEqual(r("키퍼 화면의 키워드"), "지투")
        self.assertEqual(r("prompt 예시"), "지투")

    def test_decision_text_is_maya_format(self):
        made = dm_intake.make_records(_json(self.tmp, [_mail()]), self.tmp, NOW)
        title, body, ask = dm_intake.decision_texts(made, Path("x.md"), "근거가 분명함")
        self.assertIn("DM 102", title)
        self.assertIn("선택지 2개", body)
        self.assertIn("추천 1번", body)
        self.assertIn("무효", body)
        self.assertTrue(ask.startswith("초안을 읽고"))

    def test_send_requires_draft(self):
        j = _json(self.tmp, [_mail()])
        self.assertEqual(dm_intake.main(["make", "--dm-json", str(j), "--cxo", str(self.tmp), "--send"]), 2)

    def test_plain_json_list_input(self):
        p = self.tmp / "list.json"
        p.write_text(json.dumps([_mail(104)], ensure_ascii=False), encoding="utf-8")
        self.assertEqual(len(dm_intake.make_records(p, self.tmp, NOW)), 1)


if __name__ == "__main__":
    unittest.main()
