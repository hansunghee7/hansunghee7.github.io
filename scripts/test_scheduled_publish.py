#!/usr/bin/env python3
"""scheduled_publish.py 단위 테스트 (표준 라이브러리 unittest, 임시 폴더만 씀).

실행:  python scripts/test_scheduled_publish.py -v
저장소의 log_assets/ 는 읽지도 쓰지도 않는다. 케이스마다 임시 폴더에 가짜 글을
만들고, 스크립트를 실제로 돌린 뒤 전/후 front matter 를 출력한다.

모델: 글이 공개되려면 published: false + scheduled: true + date(노출용 발행일)
시각 경과, 이 세 가지가 모두 맞아야 한다. scheduled 가 없거나 false 인 글은
(비노출 글, 컨펌 전 초안) date 가 과거든 미래든 절대 안 건드린다.
"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "scheduled_publish.py")

BODY = "본문 첫 줄 한글\n\n<div>html   공백  유지</div>\n---\n본문 안의 구분선은 front matter 가 아님\npublished: false\n끝"


def make_post(published, date="2026-09-01", scheduled=None, eol="\n", extra_before=""):
    fm = ["---", "layout: default", 'title: "테스트 글"']
    if extra_before:
        fm.append(extra_before)
    fm.append("date: " + date)
    if scheduled is not None:
        fm.append("scheduled: " + scheduled)
    fm += ["published: " + published, "---"]
    return (eol.join(fm) + eol + BODY.replace("\n", eol)).encode("utf-8")


def run(dirpath, now, dry=False):
    cmd = [sys.executable, SCRIPT, "--dir", dirpath, "--now", now, "--dry-run"] if dry else [
        sys.executable, SCRIPT, "--dir", dirpath]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    env.pop("GITHUB_OUTPUT", None)
    return subprocess.run(cmd, capture_output=True, env=env, encoding="utf-8")


def fm_of(raw):
    text = raw.decode("utf-8")
    end = text.index("---", 4)
    return text[:end + 3]


PAST = "2020-01-01T10:00:00+09:00"


class ScheduledPublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, raw):
        with open(os.path.join(self.dir, name), "wb") as f:
            f.write(raw)

    def read(self, name):
        with open(os.path.join(self.dir, name), "rb") as f:
            return f.read()

    def show(self, label, before, after):
        print("\n=== %s ===" % label)
        print("[전] " + fm_of(before).replace("\r", "\\r").replace("\n", "\n     "))
        print("[후] " + fm_of(after).replace("\r", "\\r").replace("\n", "\n     "))

    def run_real(self):
        # 실제 반영 모드는 --now 를 못 쓰므로, 시각 의존 케이스는 '아주 먼 과거/미래'로 만든다.
        return run(self.dir, None, dry=False)

    # (1) 예약 켬 + 발행일 과거 + published:false -> true
    def test1_due_flips(self):
        before = make_post("false", PAST, scheduled="true")
        self.write("a.md", before)
        r = self.run_real()
        after = self.read("a.md")
        self.show("1 예약 켬 + 발행일 과거 + published:false", before, after)
        print(r.stdout)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(after, before.replace(b"scheduled: true\npublished: false", b"scheduled: true\npublished: true"))
        self.assertIn(b"scheduled: true", after)  # 기록용으로 남김
        # 본문 안의 'published: false' 줄은 그대로여야 한다
        self.assertTrue(after.endswith(BODY.encode("utf-8")))

    # (2) 예약 켬 + 발행일 미래 -> 안 바뀜
    def test2_future_untouched(self):
        before = make_post("false", "2099-01-01T10:00:00+09:00", scheduled="true")
        self.write("a.md", before)
        r = self.run_real()
        self.show("2 발행일 미래", before, self.read("a.md"))
        print(r.stdout)
        self.assertEqual(self.read("a.md"), before)

    # (3) 예약 스위치 없음(비노출 글) -> 발행일이 과거여도 안 바뀜, 경고도 없음
    def test3_not_scheduled_untouched(self):
        before = make_post("false", PAST)  # scheduled 줄 없음
        self.write("a.md", before)
        r = self.run_real()
        self.show("3 예약 스위치 없음 + 발행일 과거 + published:false", before, self.read("a.md"))
        print(r.stdout)
        self.assertEqual(self.read("a.md"), before)
        self.assertNotIn("::warning", r.stdout)
        self.assertIn("예약 아님(안 건드림): 1건", r.stdout)

    # (3b) 날짜만 있는 옛 비노출 글, 예약 스위치 없음 -> 안 바뀜, 경고 없음
    def test3b_legacy_date_only_hidden_untouched(self):
        before = make_post("false", "2024-09-01")
        self.write("a.md", before)
        r = self.run_real()
        self.assertEqual(self.read("a.md"), before)
        self.assertNotIn("::warning", r.stdout)

    # (4) published:true -> 안 바뀜, 두 번 돌려도 같음(멱등)
    def test4_already_true_untouched_and_idempotent(self):
        before = make_post("true", PAST, scheduled="true")
        self.write("a.md", before)
        self.run_real()
        self.assertEqual(self.read("a.md"), before)
        self.write("b.md", make_post("false", PAST, scheduled="true"))
        self.run_real()
        once = self.read("b.md")
        self.run_real()
        twice = self.read("b.md")
        self.show("4 published:true 는 그대로 / 두 번 실행 멱등(b.md)", before, twice)
        self.assertEqual(once, twice)

    # (5) 예약을 켰는데 발행일 형식이 잘못됨 -> 건너뜀 + 경고, 다른 글은 정상 발행, 종료코드 0
    def test5_invalid_date_skipped_others_still_publish(self):
        bad_cases = {
            "bad1.md": "내일 오전 10시",
            "bad2.md": "2020-01-01",  # 날짜만: 시각을 모르므로 거부
            "bad3.md": "2020-13-45T10:00:00+09:00",
            "bad4.md": '"2020-01-01T10:00:00+09:00',  # 따옴표 안 닫힘
            "bad5.md": "2020-01-01T25:00:00+09:00",  # 존재하지 않는 시각
        }
        for name, val in bad_cases.items():
            self.write(name, make_post("false", val, scheduled="true"))
        self.write("good.md", make_post("false", PAST, scheduled="true"))
        r = self.run_real()
        print("\n=== 5 잘못된 발행일 ===")
        print(r.stdout)
        self.assertEqual(r.returncode, 0)
        for name in bad_cases:
            self.assertEqual(self.read(name), make_post("false", bad_cases[name], scheduled="true"), name)
            self.assertIn("::warning file=", r.stdout)
            self.assertIn(name, r.stdout)
        self.assertIn(b"published: true", self.read("good.md"))
        self.assertIn("형식 오류로 건너뜀: 5건", r.stdout)

    # (6) CRLF: 본문/줄바꿈 바이트 보존, 바뀐 건 false->true 한 단어뿐
    def test6_crlf_preserved_bytewise(self):
        before = make_post("false", PAST, scheduled="true", eol="\r\n")
        self.write("a.md", before)
        self.run_real()
        after = self.read("a.md")
        diffs = [i for i in range(min(len(before), len(after))) if before[i] != after[i]]
        print("\n=== 6 CRLF 바이트 대조: 처음 다른 위치 %s, 길이 %d -> %d ===" % (diffs[:1], len(before), len(after)))
        self.assertEqual(after, before.replace(b"published: false", b"published: true", 1))
        self.assertIn(b"\r\n", after)
        self.assertNotIn(b"\r\r", after)

    def test6b_bom_preserved(self):
        raw = b"\xef\xbb\xbf" + make_post("false", PAST, scheduled="true")
        self.write("a.md", raw)
        self.run_real()
        after = self.read("a.md")
        self.assertTrue(after.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"published: true", after)

    # (7) 시간대 경계: 발행일 = 2026-09-24T10:00:00+09:00 = 01:00:00Z
    def test7_timezone_boundary(self):
        self.write("a.md", make_post("false", "2026-09-24T10:00:00+09:00", scheduled="true"))
        cases = [
            ("2026-09-24T00:59:59Z", 0),
            ("2026-09-24T01:00:00Z", 1),
            ("2026-09-24T09:59:59+09:00", 0),
            ("2026-09-24T10:00:00+09:00", 1),
        ]
        print("\n=== 7 시간대 경계 ===")
        for now, expect in cases:
            r = run(self.dir, now, dry=True)
            print("now=%s -> %s" % (now, [l for l in r.stdout.splitlines() if "공개 예정:" in l and "건" in l]))
            self.assertIn("공개 예정: %d건" % expect, r.stdout, now)

    # 발행일 오프셋이 없으면 KST 로 해석 (UTC 서버에서도 동일)
    def test8_naive_date_is_kst(self):
        self.write("a.md", make_post("false", "2026-09-24T10:00:00", scheduled="true"))
        r1 = run(self.dir, "2026-09-24T00:59:59Z", dry=True)
        r2 = run(self.dir, "2026-09-24T01:00:00Z", dry=True)
        self.assertIn("공개 예정: 0건", r1.stdout)
        self.assertIn("공개 예정: 1건", r2.stdout)

    # 안전장치: --now 는 --dry-run 없이 쓸 수 없다
    def test9_now_requires_dry_run(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([sys.executable, SCRIPT, "--dir", self.dir, "--now", "2099-01-01T00:00:00+09:00"],
                           capture_output=True, encoding="utf-8", env=env)
        self.assertEqual(r.returncode, 2)

    # 따옴표 없는 값 + 줄 끝 주석
    def test10_unquoted_date_with_comment(self):
        self.write("a.md", make_post("false", "2020-01-01T10:00:00+09:00  # 사장님 컨펌 9/19", scheduled="true"))
        self.run_real()
        self.assertIn(b"published: true", self.read("a.md"))

    # 예약 스위치 값 표기: true 계열만 켜짐, false/빈 값/null 은 예약 아님
    def test11_scheduled_value_variants(self):
        on = {"on1.md": "true", "on2.md": '"true"', "on3.md": "True", "on4.md": "true  # 컨펌"}
        off = {"off1.md": "false", "off2.md": "", "off3.md": "null", "off4.md": '""', "off5.md": "yes-please"}
        for name, v in on.items():
            self.write(name, make_post("false", PAST, scheduled=v))
        for name, v in off.items():
            self.write(name, make_post("false", PAST, scheduled=v))
        r = self.run_real()
        print("\n=== 11 예약 스위치 표기 ===")
        print(r.stdout)
        for name in on:
            self.assertIn(b"published: true", self.read(name), name)
        for name, v in off.items():
            self.assertEqual(self.read(name), make_post("false", PAST, scheduled=v), name)
        self.assertNotIn("::warning", r.stdout)

    # 발행일을 못 읽어도 예약 스위치가 꺼진 글이면 경고하지 않는다(옛 글 보호)
    def test12_off_switch_bad_date_no_warning(self):
        self.write("a.md", make_post("false", "내일", scheduled="false"))
        r = self.run_real()
        self.assertNotIn("::warning", r.stdout)

    # (13) 지나간 시각으로 건 예약: 발행일이 마지막 저장 시각보다 앞이면 공개하지 않고 경고
    def _git_commit(self, name, when):
        env = dict(os.environ, GIT_COMMITTER_DATE=when, GIT_AUTHOR_DATE=when,
                   GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
        base = ["git", "-C", self.dir, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
        if not os.path.isdir(os.path.join(self.dir, ".git")):
            subprocess.run(["git", "-C", self.dir, "init", "-q"], check=True, env=env)
        subprocess.run(base + ["add", name], check=True, env=env)
        subprocess.run(base + ["commit", "-q", "-m", "save", "--", name], check=True, env=env)

    def test13_past_schedule_is_rejected(self):
        # 9/25 에 저장했는데 발행일이 9/24 10:00 -> 지나간 시각 예약
        self.write("past.md", make_post("false", "2026-09-24T10:00:00+09:00", scheduled="true"))
        self._git_commit("past.md", "2026-09-25T09:00:00+09:00")
        # 9/20 에 저장했고 발행일이 9/24 10:00 -> 정상 예약
        self.write("ok.md", make_post("false", "2026-09-24T10:00:00+09:00", scheduled="true"))
        self._git_commit("ok.md", "2026-09-20T09:00:00+09:00")
        r = run(self.dir, "2026-09-26T00:00:00+09:00", dry=True)
        print("\n=== 13 지나간 시각 예약 ===")
        print(r.stdout)
        self.assertIn("공개 예정: 1건", r.stdout)
        self.assertIn("past.md", r.stdout)
        self.assertIn("::warning file=", r.stdout)
        self.assertIn("지나간 시각은 예약할 수 없음", r.stdout)
        self.assertIn("형식 오류로 건너뜀: 1건", r.stdout)
        # 정상 예약 글만 공개 예정
        self.assertRegex(r.stdout, r"\[DRY-RUN\] 공개 예정: ok\.md")
        self.assertNotRegex(r.stdout, r"\[DRY-RUN\] 공개 예정: past\.md")


if __name__ == "__main__":
    unittest.main()
