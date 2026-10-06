"""md_table_inventory.py(표 탐지·파일 훑기)와 token_trend.py(토큰 집계)의 시험(외부 호출 없음).
임시 폴더에 가짜 md·csv·jsonl을 만들어 확인한다. 실제 홈 폴더(~/.claude/projects)나 C:\\work 쪽 기록은 읽지 않는다
(ROOT·ROOTS·OUT 경로 상수를 임시 폴더로 바꿔 시험)."""
import contextlib
import csv
import datetime as dt
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).parent


def load(name):
    spec = importlib.util.spec_from_file_location(name + "_under_test", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


inv = load("md_table_inventory")
tt = load("token_trend")


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, rel, text):
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p


# ---------------------------------------------------------------- md_table_inventory
class ScanMd(TempDir):
    def test_missing_file_and_no_table(self):
        self.assertEqual(inv.scan_md(self.dir / "없음.md"), [])
        self.assertEqual(inv.scan_md(self.write("a.md", "# 제목\n본문만 있다\n- 불릿\n")), [])

    def test_one_table_fields(self):
        p = self.write("a.md", "# 제목\n\n| 번호 | 안건 | 상태 |\n|---|---|---|\n| 1 | 가 | 진행 |\n| 2 | 나 | 완료 |\n\n끝\n")
        (t,) = inv.scan_md(p)
        self.assertEqual((t["kind"], t["line"], t["cols"], t["rows"]), ("md-table", 3, 3, 2))  # line은 머리줄(1부터)
        self.assertEqual(t["headers"], ["번호", "안건", "상태"])
        self.assertEqual(t["file"], str(p))

    def test_header_only_table_has_zero_rows(self):
        (t,) = inv.scan_md(self.write("a.md", "| a | b |\n|---|---|\n"))
        self.assertEqual(t["rows"], 0)

    def test_table_at_end_of_file_without_newline(self):
        (t,) = inv.scan_md(self.write("a.md", "| a |\n|---|\n| 1 |\n| 2 |"))
        self.assertEqual(t["rows"], 2)

    def test_multiple_tables_with_lines(self):
        p = self.write("a.md", "| a |\n|---|\n| 1 |\n\n문장\n\n| x | y |\n|:--|--:|\n| 1 | 2 |\n| 3 | 4 |\n")
        tables = inv.scan_md(p)
        self.assertEqual([(t["line"], t["cols"], t["rows"]) for t in tables], [(1, 1, 1), (7, 2, 2)])

    def test_alignment_markers_and_indentation(self):
        (t,) = inv.scan_md(self.write("a.md", "  | a | b |\n  | :---: | ---: |\n  | 1 | 2 |\n"))
        self.assertEqual((t["cols"], t["rows"]), (2, 1))

    def test_pipe_lines_without_separator_are_not_tables(self):
        self.assertEqual(inv.scan_md(self.write("a.md", "| 그냥 | 줄 |\n| 이어서 | 줄 |\n\n본문\n")), [])

    def test_single_dash_separator_is_not_recognised(self):
        # 현재 동작 기록: 구분선 칸은 하이픈 2개 이상이어야 한다
        self.assertEqual(inv.scan_md(self.write("a.md", "| a | b |\n|:-:|:-:|\n| 1 | 2 |\n")), [])

    def test_table_without_leading_pipe_is_not_detected(self):
        # 현재 동작 기록: 머리줄이 '|'로 시작하지 않으면 표로 보지 않는다
        self.assertEqual(inv.scan_md(self.write("a.md", "a | b\n--- | ---\n1 | 2\n")), [])

    def test_headers_split_and_trimmed(self):
        (t,) = inv.scan_md(self.write("a.md", "|  번호  |  안건 |\n|---|---|\n"))
        self.assertEqual(t["headers"], ["번호", "안건"])

    def test_utf8_errors_do_not_crash(self):
        p = self.dir / "bad.md"
        p.write_bytes("| 가 |\n|---|\n| 1 |\n".encode("utf-8") + b"\xff\xfe\n")
        (t,) = inv.scan_md(p)
        self.assertEqual(t["rows"], 1)


class ScanCsv(TempDir):
    def test_counts_rows_without_header(self):
        (t,) = inv.scan_csv(self.write("a.csv", "time,who\n1,핏\n2,탐\n3,마야\n"))
        self.assertEqual((t["kind"], t["line"], t["cols"], t["rows"], t["headers"]), ("csv", 1, 2, 3, ["time", "who"]))

    def test_header_only_empty_and_missing(self):
        self.assertEqual(inv.scan_csv(self.write("h.csv", "a,b,c\n"))[0]["rows"], 0)
        self.assertEqual(inv.scan_csv(self.write("e.csv", "")), [])
        self.assertEqual(inv.scan_csv(self.dir / "없음.csv"), [])

    def test_quoted_newline_is_one_row(self):
        (t,) = inv.scan_csv(self.write("q.csv", 'a,b\n"줄\n바꿈",x\n'))
        self.assertEqual(t["rows"], 1)


class Walk(TempDir):
    def names(self):
        return sorted(str(p.relative_to(self.dir)).replace(os.sep, "/") for p in inv.walk(self.dir))

    def test_picks_md_and_csv_only(self):
        for n in ("a.md", "b.CSV", "c.txt", "d.json", "sub/e.md", "sub/deep/f.csv", "G.MD"):
            self.write(n, "x")
        self.assertEqual(self.names(), ["G.MD", "a.md", "b.CSV", "sub/deep/f.csv", "sub/e.md"])

    def test_skip_folders_are_excluded_at_any_depth(self):
        for n in (".git/a.md", "node_modules/b.md", "x/__pycache__/c.md", "log_assets/d.md", "_site/e.md", "a/backup/f.md", "ok/g.md"):
            self.write(n, "x")
        self.assertEqual(self.names(), ["ok/g.md"])

    def test_size_limit(self):
        self.write("small.md", "x")
        with (self.dir / "big.md").open("wb") as f:
            f.write(b"x" * 3_000_000)  # 정확히 3,000,000바이트는 상한 미만이 아니므로 제외
        with (self.dir / "just_under.md").open("wb") as f:
            f.write(b"x" * 2_999_999)
        self.assertEqual(self.names(), ["just_under.md", "small.md"])

    def test_directories_named_like_md_are_not_yielded(self):
        (self.dir / "dir.md").mkdir()
        self.assertEqual(self.names(), [])


class InventoryMain(TempDir):
    def test_main_writes_sorted_json_and_csv(self):
        root, out = self.dir / "root", self.dir / "out"
        root.mkdir()
        small = self.write("root/small.md", "| a |\n|---|\n| 1 |\n")
        big = self.write("root/sub/big.md", "| 가 | 나 |\n|---|---|\n" + "| 1 | 2 |\n" * 12)
        self.write("root/data.csv", "t,w\n1,x\n2,y\n")
        self.write("root/.git/skip.md", "| a |\n|---|\n| 1 |\n")
        stamp = dt.datetime(2026, 9, 15, 12, 0).timestamp()  # 낮 12시(어느 시간대든 같은 날짜)
        for p in (small, big):
            os.utime(p, (stamp, stamp))
        buf = io.StringIO()
        with mock.patch.object(inv, "ROOTS", [str(root), str(self.dir / "없는폴더")]), mock.patch.object(inv, "OUT", out), contextlib.redirect_stdout(buf):
            inv.main()
        found = json.loads((out / "tables.json").read_text(encoding="utf-8"))
        self.assertEqual([f["rows"] for f in found], [12, 2, 1])  # 행 수 내림차순
        self.assertEqual(found[0]["file"], str(big))
        self.assertEqual(found[0]["mtime"], "2026-09-15")
        self.assertEqual(found[1]["kind"], "csv")
        self.assertNotIn(".git", json.dumps(found))
        with (out / "tables.csv").open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0], ["rows", "cols", "kind", "mtime", "file", "line", "headers"])
        self.assertEqual(rows[1][0], "12")
        self.assertEqual(rows[1][6], "가 | 나")
        self.assertIn("파일 3개 훑음, 표 3개 발견(행 10개 이상 1개)", buf.getvalue())

    def test_headers_cell_is_cut_to_160_chars(self):
        out = self.dir / "out"
        self.write("root/w.md", "| " + " | ".join("h" * 30 for _ in range(10)) + " |\n|" + "---|" * 10 + "\n| " + " | ".join("1" for _ in range(10)) + " |\n")
        with mock.patch.object(inv, "ROOTS", [str(self.dir / "root")]), mock.patch.object(inv, "OUT", out), contextlib.redirect_stdout(io.StringIO()):
            inv.main()
        with (out / "tables.csv").open(encoding="utf-8-sig", newline="") as f:
            self.assertEqual(len(list(csv.reader(f))[1][6]), 160)


# ---------------------------------------------------------------- token_trend
def stamp(delta):
    return (dt.datetime.now(dt.timezone.utc) - delta).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def day_key(ts):
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%m-%d")


def assistant(mid, req, ts, i=0, cw=0, cr=0, o=0, usage=True):
    r = {"type": "assistant", "requestId": req, "timestamp": ts, "message": {"id": mid}}
    if usage:
        r["message"]["usage"] = {"input_tokens": i, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr, "output_tokens": o}
    return r


def user(text, list_form=False):
    content = [{"type": "text", "text": text}] if list_form else text
    return {"type": "user", "message": {"content": content}}


class TrendBase(TempDir):
    def setUp(self):
        super().setUp()
        self.root = self.dir / "projects"
        self.root.mkdir()
        p = mock.patch.object(tt, "ROOT", self.root)  # 실제 홈 폴더 대신 임시 폴더
        p.start()
        self.addCleanup(p.stop)

    def session(self, proj, name, records, raw_lines=()):
        d = self.root / proj
        d.mkdir(parents=True, exist_ok=True)
        f = d / name
        with f.open("w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            for line in raw_lines:
                fh.write(line + "\n")
        return f


class Weighted(unittest.TestCase):
    def test_weights(self):
        a = {"in": 1_000_000, "cw": 1_000_000, "cr": 1_000_000, "out": 1_000_000, "msgs": 4}
        self.assertAlmostEqual(tt.weighted(a), 1e6 * (1.0 + 1.25 + 0.1 + 5.0))

    def test_zero(self):
        self.assertEqual(tt.weighted(dict.fromkeys(("in", "cw", "cr", "out", "msgs"), 0)), 0)


class Scan(TrendBase):
    def test_sums_per_project_and_day(self):
        t = stamp(dt.timedelta(hours=1))
        self.session("projA", "s1.jsonl", [assistant("m1", "r1", t, 10, 20, 300, 4), assistant("m2", "r2", t, 1, 2, 3, 4)])
        agg = tt.scan(8, "")
        a = agg["projA"][day_key(t)]
        self.assertEqual(a, {"in": 11, "cw": 22, "cr": 303, "out": 8, "msgs": 2})

    def test_dedup_by_message_and_request_id_across_files(self):
        t = stamp(dt.timedelta(hours=1))
        rec = assistant("m1", "r1", t, 10, 0, 0, 5)
        self.session("projA", "s1.jsonl", [rec, rec])  # 같은 파일 안 중복
        self.session("projA", "s2.jsonl", [rec, assistant("m1", "r2", t, 1, 0, 0, 1)])  # 다른 requestId는 별개
        a = tt.scan(8, "")["projA"][day_key(t)]
        self.assertEqual((a["in"], a["out"], a["msgs"]), (11, 6, 2))

    def test_ignores_non_assistant_missing_usage_and_bad_lines(self):
        t = stamp(dt.timedelta(hours=1))
        self.session("projA", "s1.jsonl", [user("안녕"), assistant("m0", "r0", t, usage=False), assistant("m1", "r1", t, 5, 0, 0, 5)],
                     raw_lines=["{깨진 json", "", '{"type": "assistant", "timestamp": "시각아님", "message": {"id": "m9", "usage": {"input_tokens": 99}}}'])
        agg = tt.scan(8, "")
        a = agg["projA"][day_key(t)]
        self.assertEqual((a["in"], a["msgs"]), (5, 1))  # 시각이 깨진 줄(99)은 제외

    def test_missing_usage_keys_count_as_zero(self):
        t = stamp(dt.timedelta(hours=1))
        rec = {"type": "assistant", "requestId": "r", "timestamp": t, "message": {"id": "m", "usage": {"output_tokens": 7}}}
        self.session("projA", "s.jsonl", [rec])
        a = tt.scan(8, "")["projA"][day_key(t)]
        self.assertEqual((a["in"], a["cw"], a["cr"], a["out"], a["msgs"]), (0, 0, 0, 7, 1))

    def test_window_filters_old_records_and_old_files(self):
        recent, old = stamp(dt.timedelta(hours=1)), stamp(dt.timedelta(days=30))
        self.session("projA", "mixed.jsonl", [assistant("m1", "r1", recent, 1, 0, 0, 0), assistant("m2", "r2", old, 100, 0, 0, 0)])  # 파일은 최근, 기록 하나는 오래됨
        stale = self.session("projB", "stale.jsonl", [assistant("m3", "r3", recent, 50, 0, 0, 0)])
        past = (dt.datetime.now() - dt.timedelta(days=40)).timestamp()
        os.utime(stale, (past, past))  # 파일 자체가 창 밖이면 읽지도 않는다
        agg = tt.scan(8, "")
        self.assertEqual(sum(a["in"] for a in agg["projA"].values()), 1)
        self.assertNotIn("projB", agg)

    def test_days_argument_changes_window(self):
        three_days = stamp(dt.timedelta(days=3))
        self.session("projA", "s.jsonl", [assistant("m1", "r1", three_days, 4, 0, 0, 0)])
        self.assertNotIn("projA", tt.scan(2, ""))
        self.assertEqual(sum(a["in"] for a in tt.scan(5, "")["projA"].values()), 4)

    def test_separate_days_are_separate_keys(self):
        t1, t2 = stamp(dt.timedelta(hours=1)), stamp(dt.timedelta(days=3))
        self.session("projA", "s.jsonl", [assistant("m1", "r1", t1, 1), assistant("m2", "r2", t2, 2)])
        days = tt.scan(8, "")["projA"]
        self.assertEqual({k: v["in"] for k, v in days.items()}, {day_key(t1): 1, day_key(t2): 2})

    def test_match_filter_on_folder_name(self):
        t = stamp(dt.timedelta(hours=1))
        self.session("work-shorts-lab", "s.jsonl", [assistant("m1", "r1", t, 1)])
        self.session("work-other", "s.jsonl", [assistant("m2", "r2", t, 1)])
        self.assertEqual(sorted(tt.scan(8, "shorts")), ["work-shorts-lab"])
        self.assertEqual(sorted(tt.scan(8, "")), ["work-other", "work-shorts-lab"])

    def test_subagent_files_in_subfolders_are_included_and_stray_files_ignored(self):
        t = stamp(dt.timedelta(hours=1))
        self.session("projA", "s.jsonl", [assistant("m1", "r1", t, 1)])
        sub = self.root / "projA" / "sess" / "subagents"
        sub.mkdir(parents=True)
        (sub / "agent.jsonl").write_text(json.dumps(assistant("m2", "r2", t, 2)) + "\n", encoding="utf-8")
        (self.root / "loose.jsonl").write_text("{}", encoding="utf-8")  # 폴더가 아닌 항목은 건너뜀
        self.assertEqual(tt.scan(8, "")["projA"][day_key(t)]["in"], 3)

    def test_empty_root(self):
        self.assertEqual(dict(tt.scan(8, "")), {})


class PersonaOf(TrendBase):
    def f(self, records, raw=()):
        return self.session("p", f"{len(list(self.root.rglob('*.jsonl')))}.jsonl", records, raw)

    def test_string_and_list_content(self):
        self.assertEqual(tt.persona_of(self.f([user("하이 핏")])), "핏")
        self.assertEqual(tt.persona_of(self.f([user("하이 마야", list_form=True)])), "마야")

    def test_only_first_user_message_counts(self):
        self.assertEqual(tt.persona_of(self.f([user("안녕하세요"), user("하이 탐")])), "기타")

    def test_name_must_be_within_first_40_chars(self):
        self.assertEqual(tt.persona_of(self.f([user("가" * 40 + "탐")])), "기타")
        self.assertEqual(tt.persona_of(self.f([user("가" * 39 + "탐")])), "탐")

    def test_first_match_follows_persona_tuple_order(self):
        self.assertEqual(tt.persona_of(self.f([user("마야 말고 탐")])), "탐")  # 튜플 순서상 탐이 먼저

    def test_no_user_message_empty_content_and_bad_lines(self):
        self.assertEqual(tt.persona_of(self.f([assistant("m", "r", stamp(dt.timedelta(hours=1)))])), "기타")
        self.assertEqual(tt.persona_of(self.f([{"type": "user", "message": {"content": []}}])), "기타")
        self.assertEqual(tt.persona_of(self.f([user("하이 노트")], raw=["{깨짐"])), "노트")
        self.assertEqual(tt.persona_of(self.f([], raw=["{깨짐"])), "기타")


class ScanPersona(TrendBase):
    def test_only_target_projects_and_top_level_files(self):
        t = stamp(dt.timedelta(hours=1))
        self.session("C--work-hansunghee7-github-io", "a.jsonl", [user("하이 탐"), assistant("m1", "r1", t, 10, 0, 0, 1)])
        self.session("C--work-hansunghee7-github-io", "b.jsonl", [user("하이 핏"), assistant("m2", "r2", t, 20, 0, 0, 1)])
        self.session("C--work-shorts-lab", "c.jsonl", [user("하이 핏"), assistant("m3", "r3", t, 5, 0, 0, 1)])
        self.session("C--work-other", "d.jsonl", [user("하이 탐"), assistant("m4", "r4", t, 999)])  # 대상 아닌 프로젝트
        sub = self.root / "C--work-hansunghee7-github-io" / "sess"
        sub.mkdir()
        (sub / "x.jsonl").write_text(json.dumps(assistant("m5", "r5", t, 888)) + "\n", encoding="utf-8")  # 하위 폴더는 제외
        agg = tt.scan_persona(8)
        self.assertEqual(sorted(agg), ["탐", "핏"])
        self.assertEqual(agg["탐"][day_key(t)]["in"], 10)
        self.assertEqual(agg["핏"][day_key(t)]["in"], 25)  # 두 프로젝트의 핏 합산

    def test_unknown_persona_is_other_and_dedup_across_files(self):
        t = stamp(dt.timedelta(hours=1))
        rec = assistant("m1", "r1", t, 7)
        self.session("C--work-hansunghee7-github-io", "a.jsonl", [user("그냥 시작"), rec])
        self.session("C--work-hansunghee7-github-io", "b.jsonl", [user("하이 탐"), rec])  # 같은 기록이 두 파일에 있어도 한 번만
        agg = tt.scan_persona(8)
        self.assertEqual(sum(d["in"] for v in agg.values() for d in v.values()), 7)
        # 먼저 읽힌 파일의 페르소나에 귀속된다. 읽기 순서는 파일시스템마다 달라 합계만 확인한다.

    def test_unknown_persona_is_other(self):
        t = stamp(dt.timedelta(hours=1))
        self.session("C--work-hansunghee7-github-io", "a.jsonl", [user("그냥 시작"), assistant("m1", "r1", t, 7)])
        self.assertEqual(sorted(tt.scan_persona(8)), ["기타"])

    def test_window_by_file_age(self):
        t = stamp(dt.timedelta(hours=1))
        f = self.session("C--work-hansunghee7-github-io", "old.jsonl", [user("하이 탐"), assistant("m1", "r1", t, 7)])
        past = (dt.datetime.now() - dt.timedelta(days=40)).timestamp()
        os.utime(f, (past, past))
        self.assertEqual(dict(tt.scan_persona(8)), {})


class TrendMain(TrendBase):
    def run_main(self, *argv):
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["token_trend.py", *argv]), contextlib.redirect_stdout(buf):
            tt.main()
        return buf.getvalue()

    def seed(self):
        t = stamp(dt.timedelta(hours=1))
        self.session("projBig", "s.jsonl", [assistant("m1", "r1", t, 1_000_000, 0, 0, 0), assistant("m2", "r2", t, 1_000_000, 0, 2_000_000, 100_000)])
        self.session("projSmall", "s.jsonl", [assistant("m3", "r3", t, 10_000)])
        return t

    def test_default_output_lists_projects_by_weight_then_days(self):
        t = self.seed()
        out = self.run_main("--days", "8")
        self.assertLess(out.index("## projBig"), out.index("## projSmall"))
        self.assertIn(day_key(t), out)
        self.assertIn("호출     2", out)

    def test_projects_mode_one_line_per_project(self):
        self.seed()
        lines = [l for l in self.run_main("--projects").splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].endswith("projBig"))
        self.assertIn("환산", lines[0])
        self.assertIn("2.7M환산", lines[0])  # 2M + 0.2M(캐시읽기 0.1배) + 0.5M(출력 5배)

    def test_match_argument(self):
        self.seed()
        out = self.run_main("--match", "Small")
        self.assertIn("projSmall", out)
        self.assertNotIn("projBig", out)

    def test_persona_mode_header_and_rows(self):
        t = stamp(dt.timedelta(hours=1))
        self.session("C--work-hansunghee7-github-io", "a.jsonl", [user("하이 탐"), assistant("m1", "r1", t, 2_000_000)])
        self.session("C--work-hansunghee7-github-io", "b.jsonl", [user("하이 핏"), assistant("m2", "r2", t, 1_000_000)])
        out = self.run_main("--persona").splitlines()
        self.assertTrue(out[0].startswith("페르소나"))
        self.assertIn(day_key(t), out[0])
        self.assertTrue(out[1].startswith("탐"))  # 환산량이 큰 쪽이 먼저
        self.assertIn("2.0", out[1])
        self.assertTrue(out[2].startswith("핏"))
        self.assertIn("1.0", out[2])

    def test_persona_mode_shows_dash_for_missing_days(self):
        t1, t2 = stamp(dt.timedelta(hours=1)), stamp(dt.timedelta(days=3))
        self.session("C--work-hansunghee7-github-io", "a.jsonl", [user("하이 탐"), assistant("m1", "r1", t1, 1_000_000)])
        self.session("C--work-hansunghee7-github-io", "b.jsonl", [user("하이 핏"), assistant("m2", "r2", t2, 1_000_000)])
        out = self.run_main("--persona")
        self.assertIn("-", out.splitlines()[1] + out.splitlines()[2])

    def test_empty_root_prints_nothing_in_default_mode(self):
        self.assertEqual(self.run_main(), "")


if __name__ == "__main__":
    unittest.main()
