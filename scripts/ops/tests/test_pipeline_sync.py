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
        other = LINE.replace('성공 기록 없음', '마지막 성공 2026-10-06 22:39 (96.3시간 전)')
        self.assertEqual(ps.parse_stale('신선도 기준을 넘긴 파이프라인 2개\n' + LINE + '\n' + other),
                         [('dynamic-quota', 'fn:dynamic-quota', True), ('dynamic-quota', 'fn:dynamic-quota', False)])

    def test_evidence(self):
        ok, note, at = ps.evidence({'id': 'a', 'status': 'ok', 'detail': '마지막 실행 10-11 07:14 (x)', 'checked': '2026-10-11T07:38:00.123456+09:00'})
        self.assertTrue(ok)
        self.assertEqual(at, '2026-10-11T07:14:00+09:00')
        self.assertIn('10-11 07:14', note)
        self.assertFalse(ps.evidence({'id': 'a', 'status': 'fail', 'detail': ''})[0])
        self.assertIsNone(ps.evidence({'id': 'a', 'status': 'warn'}))

    def test_pick_evidence_prefers_github_for_gh_watch(self):
        state = {'gh:site:X': {'id': 'gh:site:X', 'status': 'ok', 'detail': '마지막 성공 10-15 23:19', 'checked': '2026-10-16T02:38:00+09:00'},
                 'fn:a': {'id': 'fn:a', 'status': 'ok', 'detail': '마지막 실행 10-16 07:00', 'checked': '2026-10-16T07:38:00+09:00'}}
        live = (True, 'gh live', '2026-10-15T21:40:41Z')
        self.assertEqual(ps.pick_evidence('gh:site:X', state, gh=lambda w: live), live)
        self.assertEqual(ps.pick_evidence('gh:site:X', state, gh=lambda w: None)[2], '2026-10-15T23:19:00+09:00')
        self.assertEqual(ps.pick_evidence('fn:a', state, gh=lambda w: live)[2], '2026-10-16T07:00:00+09:00')
        self.assertIsNone(ps.pick_evidence(None, state, gh=lambda w: live))

    # ---- eager 동기화(10/18): 대장이 현실보다 낡으면 옮기고, 옮긴 뒤엔 다시 옮기지 않는다 ----
    STATE = {'fn:a': {'id': 'fn:a', 'status': 'ok', 'detail': '마지막 실행 10-18 07:00', 'checked': '2026-10-18T07:30:00+09:00'}}

    def test_stale_ledger_becomes_target(self):
        ledger = ps.parse_last_success('a\t2026-10-17T20:00:00+00:00\tfn:a\n')  # 대장: 10-18 05:00 KST, 근거: 07:00 KST
        todo, _ = ps.plan([], ledger, self.STATE)
        self.assertEqual([t[0] for t in todo], ['a'])

    def test_up_to_date_ledger_not_target(self):
        ledger = ps.parse_last_success('a\t2026-10-17T22:00:00+00:00\tfn:a\n')  # 대장 == 근거(07:00 KST)
        self.assertEqual(ps.plan([], ledger, self.STATE)[0], [])
        ledger = ps.parse_last_success('a\t2026-10-18T01:00:00+00:00\tfn:a\n')  # 대장이 더 새것
        self.assertEqual(ps.plan([], ledger, self.STATE)[0], [])

    def test_sequential_rerun_adds_no_new_row(self):
        """옮긴 add-run 의 --at 을 대장 last_success 로 반영하는 가짜 DB 로 두 번 돌린다: 첫 회 1건, 둘째 회 0건."""
        db = {'a': None}
        rows = []

        def once():
            led = {k: (ps.to_dt(v) if v else None, 'fn:a') for k, v in db.items()}
            todo, _ = ps.plan([], led, self.STATE)
            for slug, (ok, note, at) in todo:
                rows.append((slug, at))
                db[slug] = at
            return len(todo)
        self.assertEqual((once(), once(), once()), (1, 0, 0))
        self.assertEqual(len(rows), 1)

    def test_stale_line_with_fresh_ledger_is_skipped(self):
        """기준을 넘긴 줄이어도 대장이 이미 근거 시각 이상이면 다시 쓰지 않는다."""
        ledger = {'a': (ps.to_dt('2026-10-18T07:00:00+09:00'), 'fn:a')}
        todo, none = ps.plan([('a', 'fn:a', False)], ledger, self.STATE)
        self.assertEqual(todo, [])
        self.assertIn('이미 최신', none[0])

    def test_check_time_evidence_not_eager(self):
        """실제 실행 시각이 없는 근거(감시 점검 시각)는 점검마다 새 값이라 eager 대상이 아니다."""
        st = {'fn:a': {'id': 'fn:a', 'status': 'ok', 'detail': '', 'checked': '2026-10-18T07:30:00+09:00'}}
        self.assertEqual(ps.plan([], {'a': (None, 'fn:a')}, st)[0], [])

    def test_failure_evidence_only_for_stale_rows(self):
        st = {'fn:a': {'id': 'fn:a', 'status': 'fail', 'detail': '', 'checked': '2026-10-18T07:30:00+09:00'}}
        self.assertEqual(ps.plan([], {'a': (None, 'fn:a')}, st)[0], [])
        self.assertEqual([t[0] for t in ps.plan([('a', 'fn:a', True)], {'a': (None, 'fn:a')}, st)[0]], ['a'])


if __name__ == '__main__':
    unittest.main()
