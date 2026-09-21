"""로컬 LLM 가공 2건의 결정적 부분 시험(LLM·네트워크 호출 없음).

실행: python scripts/ops/test_local_llm.py
"""
import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path

D = Path(__file__).parent / "local_llm"
sys.path.insert(0, str(D))


def load(name):
    spec = importlib.util.spec_from_file_location(name, D / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


arc = load("weekly_archive_candidates")
chg = load("weekly_change_summary")
TODAY = date(2026, 9, 21)

DOC = """# 제목
머리말

## [A] 상태: 오래된 것 (2026-09-01)
끝난 일. 9/2 마감.

## 📥 B → C: 요청 (2026-09-05)
결과 대기 중.
다음 것: 확인

## 최근 절 (9/20)
방금 한 일

## 날짜 없는 절
내용만 있음

```
## 코드블록 안 제목은 절이 아님
```
"""


class ArchiveTest(unittest.TestCase):
    def test_parse_sections_titles_lines_and_fence(self):
        s = arc.parse_sections(DOC)
        self.assertEqual([x["title"] for x in s],
                         ["[A] 상태: 오래된 것 (2026-09-01)", "📥 B → C: 요청 (2026-09-05)",
                          "최근 절 (9/20)", "날짜 없는 절"])
        self.assertEqual(s[0]["start"], 4)
        self.assertEqual(s[0]["line_count"], 3)  # 제목 + 본문 1줄 + 빈 줄

    def test_extract_dates_all_formats(self):
        d = arc.extract_dates("2026-09-01, 9/2, 9월 3일, 12/25", TODAY)
        # 12/25는 오늘보다 14일 넘게 미래라 날짜로 안 침
        self.assertEqual(d, [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)])

    def test_extract_dates_ignores_urls_and_fractions(self):
        self.assertEqual(arc.extract_dates("http://x/9/17 그리고 3/4/5 그리고 13/40", TODAY), [])

    def test_classify_buckets(self):
        by = {s["title"]: arc.classify(s, TODAY) for s in arc.parse_sections(DOC)}
        self.assertEqual(by["[A] 상태: 오래된 것 (2026-09-01)"]["bucket"], "candidate")
        self.assertEqual(by["📥 B → C: 요청 (2026-09-05)"]["bucket"], "ambiguous")
        self.assertIn("대기", by["📥 B → C: 요청 (2026-09-05)"]["markers"])
        self.assertEqual(by["최근 절 (9/20)"]["bucket"], "recent")
        self.assertEqual(by["날짜 없는 절"]["bucket"], "ambiguous")

    def test_stale_boundary_is_strictly_older_than_7_days(self):
        sec = {"title": "t (2026-09-14)", "body": "", "start": 1, "line_count": 1}
        self.assertEqual(arc.classify(sec, TODAY)["bucket"], "recent")   # 7일 전 = 7일 이내
        sec["title"] = "t (2026-09-13)"
        self.assertEqual(arc.classify(sec, TODAY)["bucket"], "candidate")

    def test_parse_verdict(self):
        self.assertEqual(arc.parse_verdict("분류: 유지\n이유: 할 일 남음"), ("유지", "할 일 남음"))
        self.assertEqual(arc.parse_verdict("분류: 아카이브 후보\n이유: 끝남")[0], "아카이브 후보")
        self.assertEqual(arc.parse_verdict("엉뚱한 답")[0], "형식 오류")


class ChangeSummaryTest(unittest.TestCase):
    LINES = [
        "aaaaaaa feat: 기능 추가 (#10)",
        "bbbbbbb fix(ui): 버그 수정 (#11)",
        "ccccccc docs: 문서",
        "ddddddd chore: SNS 인사이트 자동 기록 (linkedin 2026-09-21) [skip ci]",
        "eeeeeee chore: SNS 인사이트 자동 기록 (linkedin 2026-09-20) [skip ci]",
        "fffffff 접두어 없는 제목",
        "1111111 docs: 문서 둘",
    ]

    def test_group_commits_and_bots(self):
        g, bots = chg.group_commits(self.LINES)
        self.assertEqual(list(g.keys())[0], "docs")  # 많은 순
        self.assertEqual({k: len(v) for k, v in g.items()},
                         {"docs": 2, "feat": 1, "fix": 1, "접두어 없음": 1})
        self.assertEqual(len(bots), 2)

    def test_bot_patterns_merge_dates(self):
        _, bots = chg.group_commits(self.LINES)
        self.assertEqual(chg.bot_patterns(bots), [("chore: SNS 인사이트 자동 기록  [skip ci]", 2)])

    def test_scrub_hashes_removes_unknown_only(self):
        out = chg.scrub_hashes("요약 aaaaaaa 와 deadbeef 참고", {"aaaaaaa"})
        self.assertIn("aaaaaaa", out)
        self.assertNotIn("deadbeef", out)

    def test_evidence_lists_hashes_and_prs(self):
        g, _ = chg.group_commits(self.LINES)
        ev = chg.evidence(g["feat"] + g["fix"])
        self.assertEqual(ev, "근거: aaaaaaa bbbbbbb / PR #10, #11")

    def test_korean_prefix_is_a_group(self):
        self.assertEqual(chg.prefix_of("마야: 인수인계 (#1)"), "마야")
        self.assertEqual(chg.prefix_of("CLAUDE.md 구조 최적화 Phase 3: 576줄"), "접두어 없음")

    def test_chunks(self):
        self.assertEqual([len(c) for c in chg.chunks(list(range(60)), 25)], [25, 25, 10])

    def test_parse_status(self):
        t = ("# 상태판 (2026-09-21)\n\n**🔴 문제 1건**\n\n| 상태 | 항목 | 내용 | 시작 |\n|---|---|---|---|\n"
             "| 🔴 | health-check | error | 09-21 |\n| 🟢 | 포트 | ok | 09-21 |\n")
        st = chg.parse_status(t)
        self.assertEqual(st["summary"], "🔴 문제 1건")
        eol = chr(13) + chr(10)  # 윈도우 줄바꿈에서도 ** 가 남지 않아야 함
        crlf = chg.parse_status(eol.join(["# x", "", "**a b**", ""]))
        self.assertEqual(crlf["summary"], "a b")
        self.assertEqual([r[:2] for r in st["rows"]], [("🔴", "health-check"), ("🟢", "포트")])


if __name__ == "__main__":
    unittest.main(verbosity=1)
