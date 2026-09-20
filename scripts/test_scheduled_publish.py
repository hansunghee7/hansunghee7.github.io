#!/usr/bin/env python3
"""scheduled_publish.py 단위 테스트 (표준 라이브러리 unittest, 임시 폴더만 씀).

실행:  python scripts/test_scheduled_publish.py -v
저장소의 log_assets/ 는 읽지도 쓰지도 않는다. 케이스마다 임시 폴더에 가짜 글을
만들고, 스크립트를 실제로 돌린 뒤 전/후 front matter 를 출력한다.
"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "scheduled_publish.py")

BODY = "본문 첫 줄 한글\n\n<div>html   공백  유지</div>\n---\n본문 안의 구분선은 front matter 가 아님\npublished: false\n끝"


def make_post(published, publish_at=None, eol="\n", extra_before=""):
    fm = ["---", "layout: default", 'title: "테스트 글"']
    if extra_before:
        fm.append(extra_before)
    if publish_at is not None:
        fm.append("publish_at: " + publish_at)
    fm += ["date: 2026-09-01", "published: " + published, "---"]
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


class ScheduledPublishTest(unittest.TestCase):
    NOW_KST_AFTER = "2026-09-24T10:00:01+09:00"

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

    def run_real(self, now_dir_name=None):
        # 실제 반영 모드는 --now 를 못 쓰므로, 시각 의존 케이스는 '아주 먼 과거/미래'로 만든다.
        return run(self.dir, None, dry=False)

    # (1) 과거 + false -> true
    def test1_past_publish_at_flips(self):
        before = make_post("false", '"2020-01-01T10:00:00+09:00"')
        self.write("a.md", before)
        r = self.run_real()
        after = self.read("a.md")
        self.show("1 publish_at 과거 + published:false", before, after)
        print(r.stdout)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(after, before.replace(b"date: 2026-09-01\npublished: false", b"date: 2026-09-01\npublished: true"))
        self.assertIn(b"publish_at:", after)  # 기록용으로 남김
        self.assertIn(b"published: true", after)
        # 본문 안의 'published: false' 줄은 그대로여야 한다
        self.assertTrue(after.endswith(BODY.encode("utf-8")))

    # (2) 미래 -> 안 바뀜
    def test2_future_untouched(self):
        before = make_post("false", "2099-01-01T10:00:00+09:00")
        self.write("a.md", before)
        r = self.run_real()
        self.show("2 publish_at 미래", before, self.read("a.md"))
        print(r.stdout)
        self.assertEqual(self.read("a.md"), before)

    # (3) publish_at 없음 -> 안 바뀜
    def test3_no_publish_at_untouched(self):
        before = make_post("false", None)
        self.write("a.md", before)
        r = self.run_real()
        self.show("3 publish_at 없음 + published:false", before, self.read("a.md"))
        print(r.stdout)
        self.assertEqual(self.read("a.md"), before)

    # (4) published:true -> 안 바뀜 (publish_at 과거여도), 두 번 돌려도 같음(멱등)
    def test4_already_true_untouched_and_idempotent(self):
        before = make_post("true", "2020-01-01T10:00:00+09:00")
        self.write("a.md", before)
        self.run_real()
        self.assertEqual(self.read("a.md"), before)
        # 멱등: (1)의 결과에 다시 돌려도 결과가 같다
        self.write("b.md", make_post("false", "2020-01-01T10:00:00+09:00"))
        self.run_real()
        once = self.read("b.md")
        self.run_real()
        twice = self.read("b.md")
        self.show("4 published:true 는 그대로 / 두 번 실행 멱등(b.md)", before, twice)
        self.assertEqual(once, twice)

    # (5) 잘못된 형식 -> 건너뜀 + 경고, 다른 글은 정상 발행, 종료코드 0
    def test5_invalid_format_skipped_others_still_publish(self):
        bad_cases = {
            "bad1.md": "내일 오전 10시",
            "bad2.md": "2020-01-01",  # 날짜만: 모호하므로 거부
            "bad3.md": "2020-13-45T10:00:00+09:00",
            "bad4.md": '"2020-01-01T10:00:00+09:00',  # 따옴표 안 닫힘
            "bad5.md": "2020-01-01T25:00:00+09:00",  # 존재하지 않는 시각
        }
        for name, val in bad_cases.items():
            self.write(name, make_post("false", val))
        self.write("good.md", make_post("false", "2020-01-01T10:00:00+09:00"))
        r = self.run_real()
        print("\n=== 5 잘못된 형식 ===")
        print(r.stdout)
        self.assertEqual(r.returncode, 0)
        for name in bad_cases:
            self.assertEqual(self.read(name), make_post("false", bad_cases[name]), name)
            self.assertIn("::warning file=", r.stdout)
            self.assertIn(name, r.stdout)
        self.assertIn(b"published: true", self.read("good.md"))
        self.assertIn("형식 오류로 건너뜀: 5건", r.stdout)

    # (6) CRLF: 본문/줄바꿈 바이트 보존, 바뀐 건 false->true 한 단어(5바이트->4바이트)뿐
    def test6_crlf_preserved_bytewise(self):
        before = make_post("false", '"2020-01-01T10:00:00+09:00"', eol="\r\n")
        self.write("a.md", before)
        r = self.run_real()
        after = self.read("a.md")
        self.show("6 CRLF 파일", before, after)
        self.assertEqual(after, before.replace(b"published: false\r\n---", b"published: true\r\n---", 1))
        # 바이트 diff: 다른 위치가 정확히 한 군데(false->true)인지
        self.assertEqual(after.count(b"\r\n"), before.count(b"\r\n"))
        self.assertNotIn(b"\n", after.replace(b"\r\n", b""))  # LF 단독이 섞이지 않음
        i = before.index(b"published: false\r\n---")
        self.assertEqual(before[:i + 11], after[:i + 11])
        self.assertEqual(before[i + 16:], after[i + 15:])
        print("CRLF 바이트 대조: 바뀐 위치 1곳(published 값), 나머지 %d바이트 동일" % (len(before) - 5))

    # BOM 유지
    def test6b_bom_preserved(self):
        before = b"\xef\xbb\xbf" + make_post("false", '"2020-01-01T10:00:00+09:00"')
        self.write("a.md", before)
        self.run_real()
        after = self.read("a.md")
        self.assertTrue(after.startswith(b"\xef\xbb\xbf---"))
        self.assertIn(b"published: true", after)

    # 시간대 경계: 10:00+09:00 == 01:00 UTC. now=00:59:59Z 는 미발행, 01:00:00Z 는 발행
    def test7_timezone_boundary(self):
        self.write("a.md", make_post("false", '"2026-09-24T10:00:00+09:00"'))
        r1 = run(self.dir, "2026-09-24T00:59:59Z", dry=True)
        r2 = run(self.dir, "2026-09-24T01:00:00Z", dry=True)
        r3 = run(self.dir, "2026-09-24T09:59:59", dry=True)   # 오프셋 없는 now = KST 로 해석 -> 미발행
        r4 = run(self.dir, "2026-09-24T10:00:00", dry=True)   # KST 10:00:00 -> 발행
        print("\n=== 7 시간대 경계 (publish_at = 2026-09-24T10:00:00+09:00 = 01:00:00Z) ===")
        for label, r in (("now=00:59:59Z", r1), ("now=01:00:00Z", r2), ("now=09:59:59(KST 가정)", r3), ("now=10:00:00(KST 가정)", r4)):
            line = [l for l in r.stdout.splitlines() if "공개 예정" in l and "요약" not in l and l.startswith("공개 예정")]
            print("%s -> %s" % (label, line[0] if line else "공개 예정: (없음)"))
        self.assertIn("공개 예정: 0건", r1.stdout)
        self.assertIn("공개 예정: 1건", r2.stdout)
        self.assertIn("공개 예정: 0건", r3.stdout)
        self.assertIn("공개 예정: 1건", r4.stdout)
        # dry-run 은 파일을 안 바꾼다
        self.assertIn(b"published: false", self.read("a.md"))

    # publish_at 오프셋이 없으면 KST 로 해석 (UTC 서버에서도 동일)
    def test8_naive_publish_at_is_kst(self):
        self.write("a.md", make_post("false", "2026-09-24T10:00:00"))
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

    # CMS 에서 칸을 비워 저장한 경우: 빈 값은 "예약 없음". 안 건드리고 경고도 없다
    def test11_blank_publish_at_is_no_schedule(self):
        blanks = {
            "b1.md": "",
            "b2.md": '""',
            "b3.md": "''",
            "b4.md": "null",
            "b5.md": "~",
            "b6.md": "  # 사장님 미정",
        }
        for name, val in blanks.items():
            self.write(name, make_post("false", val))
        self.write("good.md", make_post("false", "2020-01-01T10:00:00+09:00"))
        r = self.run_real()
        print("\n=== 11 빈 publish_at ===")
        print(r.stdout)
        self.assertEqual(r.returncode, 0)
        for name, val in blanks.items():
            self.assertEqual(self.read(name), make_post("false", val), name)
        self.assertNotIn("::warning", r.stdout)
        self.assertIn("형식 오류로 건너뜀: 0건", r.stdout)
        self.assertIn("publish_at 없음(안 건드림): 6건", r.stdout)
        self.assertIn(b"published: true", self.read("good.md"))

    # 형식이 틀린 값은 여전히 경고 대상(빈 값과 구분)
    def test12_garbage_is_still_invalid_not_blank(self):
        self.write("a.md", make_post("false", "미정"))
        r = self.run_real()
        self.assertIn("::warning file=", r.stdout)
        self.assertIn("형식 오류로 건너뜀: 1건", r.stdout)

    # 따옴표 없는 값 + 줄 끝 주석
    def test10_unquoted_with_comment(self):
        self.write("a.md", make_post("false", "2020-01-01T10:00:00+09:00  # 사장님 컨펌 9/19"))
        self.run_real()
        self.assertIn(b"published: true", self.read("a.md"))


if __name__ == "__main__":
    unittest.main()
