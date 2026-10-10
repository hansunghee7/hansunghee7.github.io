# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_sync as ps  # noqa: E402

LINE = 'dynamic-quota  다이나믹 한도  [작동]  기준 48시간  성공 기록 없음  대장 credit-ledger  감시 fn:dynamic-quota'


class T(unittest.TestCase):
    def test_line(self):
        self.assertEqual(ps.parse_stale_line(LINE), ('dynamic-quota', 'fn:dynamic-quota', True))

    def test_watch_with_spaces_and_none(self):
        r = ps.parse_stale_line('ink-queue  접수함  [작동]  기준 4시간  성공 기록 없음  대장 x  감시 gh:site:Fetch ink queue')
        self.assertEqual(r[1], 'gh:site:Fetch ink queue')
        self.assertIsNone(ps.parse_stale_line('a  b  [부분]  기준 1시간  성공 기록 없음  대장 x  감시 -')[1])

    def test_parse_stale_skips_header(self):
        self.assertEqual(len(ps.parse_stale('신선도 기준을 넘긴 파이프라인 1개\n' + LINE)), 1)

    def test_evidence(self):
        ok, note = ps.evidence({'id': 'a', 'status': 'ok', 'detail': '마지막 실행 10-11 07:14 (x)', 'checked': '2026-10-11T07:38:00'})
        self.assertTrue(ok)
        self.assertIn('10-11 07:14', note)
        self.assertFalse(ps.evidence({'id': 'a', 'status': 'fail', 'detail': ''})[0])
        self.assertIsNone(ps.evidence({'id': 'a', 'status': 'warn'}))


if __name__ == '__main__':
    unittest.main()
