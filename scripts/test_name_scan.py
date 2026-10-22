"""scripts/ops/name_scan.py 시험. 실행: python -m unittest scripts.test_name_scan  (또는 python scripts/test_name_scan.py)
[옛이름 허용: 옛 이름 스캐너 시험이라 검색 패턴과 옛 이름 예시를 인용해야 함]
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "ops"))
import name_scan as ns  # noqa: E402

TODAY = "2026-10-21"
OLD = "saeg" + "im"  # 이 파일 자체가 걸리지 않게 쪼갠 예시 이름


def cfg_base():
    c = ns.load_config()
    return copy.deepcopy(c)


def content(repo, rel, n=2, **kw):
    return ns.finding(1, "content", rel, repo, count=n, **kw)


class ClassifyTest(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "history_rules": [
                {"id": "H1", "repo": "r", "dated_glob": "arc/*.md", "frozen_through": "2026-10-20", "expires": "2027-01-01"},
                {"id": "H2", "repo": "r", "file": "old/log.md", "expires": "2026-01-01"},
                {"id": "H3", "repo": "r", "section_file": "pol.md", "section_heading": "변경 기록", "expires": "2027-01-01"},
            ],
            "explain_files": [{"repo": "r", "file": "tools/scan.py"}],
            "planned": [{"id": "P1", "kinds": ["env"], "match": "^X_", "step": "P4", "deadline": "2026-12-31", "owner": "탐"},
                        {"id": "P2", "kinds": ["env"], "match": "^OLD_", "step": "P4", "deadline": "2026-10-01", "owner": "탐"}],
            "external": [{"id": "E1", "kinds": ["ghrepo"], "match": "thirdparty"}],
            "ratchet": {"history_rules": 3, "explain_files": 1, "external": 1},
        }

    def cat(self, f):
        return [(c, rid, n) for c, rid, n, _ in ns.classify(f, self.cfg, TODAY)]

    def test_planned_before_deadline_is_planned(self):
        self.assertEqual(self.cat(ns.finding(2, "env", "X_RUNNER")), [("planned", "P1", 1)])

    def test_planned_past_deadline_becomes_violation(self):
        out = ns.classify(ns.finding(2, "env", "OLD_VAR"), self.cfg, TODAY)
        self.assertEqual(out[0][0], "violation")
        self.assertIn("기한 초과", out[0][3])

    def test_explain_only_fixed_files(self):
        self.assertEqual(self.cat(content("r", "tools/scan.py"))[0][0], "explain")
        self.assertEqual(self.cat(content("r", "tools/other.py"))[0][0], "violation")
        self.assertEqual(self.cat(content("r2", "tools/scan.py"))[0][0], "violation")  # 다른 저장소 같은 경로는 설명 아님

    def test_history_dated_glob_does_not_exclude_new_files(self):
        self.assertEqual(self.cat(content("r", "arc/2026-10-20.md"))[0][0], "history")
        self.assertEqual(self.cat(content("r", "arc/2026-10-21.md"))[0][0], "violation")
        self.assertEqual(self.cat(content("r", "arc/notes.md"))[0][0], "violation")

    def test_expired_history_rule_inactive(self):
        self.assertEqual(self.cat(content("r", "old/log.md"))[0][0], "violation")

    def test_section_rule_splits_hits(self):
        f = content("r", "pol.md", n=3, hit_lines={2: 1, 10: 1, 11: 1}, sections={"H3": [9, 10, 11]})
        got = self.cat(f)
        self.assertIn(("history", "H3", 2), got)
        self.assertIn(("violation", "", 1), got)

    def test_external(self):
        self.assertEqual(self.cat(ns.finding(3, "ghrepo", "o/thirdparty-x"))[0][0], "external")

    def test_unverified_is_not_violation(self):
        res = ns.new_result(3, "gcp")
        ns.add_unverified(res, "프로젝트 목록", "인증 필요(재로그인)")
        rep = ns.build_report([res], self.cfg, TODAY, "t", None, (3,))
        self.assertEqual(rep["totals"]["violation"], 0)
        self.assertEqual(rep["totals"]["unverified"], 1)
        self.assertEqual(rep["exit_code"], 0)  # 종료 코드는 위반 기준
        self.assertFalse(rep["complete"])  # 하지만 완료 불가
        self.assertIn("완료 불가", ns.render_md(rep))

    def test_violation_exit_code_and_new_violation_diff(self):
        res = ns.new_result(1, "files:r")
        res["findings"].append(content("r", "a.py"))
        prev0 = {"date": "d", "baseline_ok": True, "layers_run": [1], "violation_counts": {}}
        rep = ns.build_report([res], self.cfg, TODAY, "t", prev0, (1,))
        self.assertEqual(rep["exit_code"], 1)
        self.assertEqual(len(rep["new_violations"]), 1)
        rep2 = ns.build_report([res], self.cfg, TODAY, "t", rep, (1,))
        self.assertEqual(rep2["new_violations"], [])

    def test_ratchet_growth_is_violation(self):
        self.cfg["external"].append({"id": "E2", "kinds": ["ghrepo"], "match": "zzz"})
        rep = ns.build_report([], self.cfg, TODAY, "t", None, (1,))
        self.assertEqual(rep["summary"]["0"]["violation"], 1)
        self.assertEqual(rep["exit_code"], 1)

    def test_shipped_config_is_consistent(self):
        c = cfg_base()
        self.assertEqual(ns.ratchet_violations(c), [])
        for r in c["planned"]:
            self.assertEqual(r["deadline"], "2026-12-31")
            self.assertIn(r["step"], ("C", "D", "P4"))
            self.assertEqual(r["owner"], "탐")
        for r in c["history_rules"]:
            self.assertTrue(r.get("owner") and r.get("reason") and r.get("expires"))
        self.assertFalse(ns.matches(c["output_dir"]))


class NoValueCollectionTest(unittest.TestCase):
    def test_env_values_never_kept(self):
        secret = "S3CR3T-VALUE-123"

        def fake(argv, timeout, cwd=None):
            # 혹시 값이 딸려 와도(이름→값 딕셔너리) 이름만 남아야 한다
            return 0, json.dumps({"user": {OLD.upper() + "_KEY": secret, "PATH": "x"}, "machine": [OLD.upper() + "_M", "TEMP"]}).encode(), b""

        res = ns.collect_env_names(runner=fake)
        blob = json.dumps(res, ensure_ascii=False)
        self.assertNotIn(secret, blob)
        self.assertEqual(sorted(f["subject"] for f in res["findings"]), [OLD.upper() + "_KEY", OLD.upper() + "_M"])

    def test_process_args_never_kept(self):
        secret = "--token=TOP-SECRET-ARG"

        def fake(argv, timeout, cwd=None):
            return 0, json.dumps([{"Name": "py.exe", "ExecutablePath": "C:\\work\\%s-pass-dev\\x.exe" % OLD, "CommandLine": secret}]).encode(), b""

        res = ns.collect_processes(runner=fake)
        self.assertNotIn(secret, json.dumps(res, ensure_ascii=False))
        self.assertEqual(len(res["findings"]), 1)

    def test_process_script_does_not_request_command_line(self):
        self.assertNotIn("commandline", ns.PS_PROCESSES.lower())
        self.assertNotIn("commandline", ns.PS_ENV_NAMES.lower())

    def test_mcp_names_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            p.write_text(json.dumps({"mcpServers": {OLD: {"url": "https://x/?token=ZZZ-SECRET"}}, "projects": {"p": {"mcpServers": {"other": {}}}}}), encoding="utf-8")
            res = ns.collect_mcp([p])
            self.assertNotIn("ZZZ-SECRET", json.dumps(res))
            self.assertEqual([f["subject"] for f in res["findings"]], [OLD])
            bad = Path(d) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            self.assertEqual(len(ns.collect_mcp([bad])["unverified"]), 1)  # 실패하면 미확인


class OutputPathTest(unittest.TestCase):
    def test_old_name_in_path_rejected(self):
        with self.assertRaises(SystemExit):
            ns.assert_clean_path("C:/work/_ops/" + OLD + "_removal/scan")
        with self.assertRaises(SystemExit):
            ns.assert_clean_path("C:/work/_ops/새김/out")
        ns.assert_clean_path("C:/work/_ops/name_scan")

    def test_main_writes_clean_named_files(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out"
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                rc = ns.main(["--layers", "2", "--out", str(out), "--repos"])
            self.assertIn(rc, (0, 1))
            names = [p.name for p in out.iterdir()]
            self.assertEqual(sorted(names), [ns.today_str() + ".json", ns.today_str() + ".md"])
            for n in names:
                self.assertFalse(ns.matches(n))

    def test_main_refuses_dirty_out(self):
        with self.assertRaises(SystemExit):
            ns.main(["--out", "C:/tmp/" + OLD + "_scan", "--no-write"])


class CollectorIsolationTest(unittest.TestCase):
    def test_failed_and_hung_collectors_do_not_block_others(self):
        def ok():
            r = ns.new_result(1, "ok")
            r["ok"] = 1
            r["findings"].append(ns.finding(1, "content", "a.py", "r"))
            return r

        def boom():
            raise RuntimeError("터짐")

        def hang():
            time.sleep(5)

        t0 = time.monotonic()
        out = ns.run_collectors([(1, "ok", ok), (2, "boom", boom), (3, "hang", hang)], timeout=0.5)
        self.assertLess(time.monotonic() - t0, 3)
        by = {r["collector"]: r for r in out}
        self.assertEqual(len(by["ok"]["findings"]), 1)
        self.assertTrue(by["boom"]["crashed"] and by["boom"]["unverified"])
        self.assertTrue(by["hang"]["crashed"] and "시간 초과" in by["hang"]["unverified"][0]["reason"])
        rep = ns.build_report(out, {"ratchet": {}}, TODAY, "t", None, (1, 2, 3))
        self.assertEqual(rep["totals"]["unverified"], 2)
        self.assertFalse(rep["baseline_ok"])  # 죽은 수집기가 있으면 기준선으로 쓰지 않는다

    def test_gcp_auth_failure_counts_as_unverified(self):
        def fake(argv, timeout, cwd=None):
            return 1, b"", b"ERROR: (gcloud.projects.list) There was a problem refreshing your current auth tokens: Reauthentication failed."

        res = ns.collect_gcp(runner=fake)
        self.assertEqual(len(res["unverified"]), 4)
        self.assertEqual(res["findings"], [])
        self.assertEqual(res["ok"], 0)

    def test_github_partial_failure_continues(self):
        calls = []

        def fake(argv, timeout, cwd=None):
            calls.append(argv)
            if argv[:3] == ["gh", "variable", "list"]:
                return 1, b"", b"HTTP 404: Not Found"
            if argv[:3] == ["gh", "repo", "list"]:
                return 0, ("x\n%s-pass-dev\n" % OLD).encode(), b""
            return 0, b"", b""

        cfg = {"github_owner": "o", "github_target_repos": ["a", "b"]}
        res = ns.collect_github(cfg, runner=fake)
        self.assertEqual(len(res["unverified"]), 2)
        self.assertEqual([f["kind"] for f in res["findings"]], ["ghrepo"])
        self.assertGreater(res["ok"], 3)


class ReadOnlyGuardTest(unittest.TestCase):
    def test_write_commands_blocked(self):
        bad = [
            ["gh", "repo", "delete", "o/r"], ["gh", "secret", "set", "X"], ["gh", "variable", "set", "X"],
            ["gh", "api", "repos/o/r", "-X", "DELETE"], ["gh", "api", "repos/o/r", "--method", "POST"], ["gh", "api", "repos/o/r", "-f", "a=b"],
            ["gh", "api", "user"], ["gh", "repo", "list", "o", "delete"],
            ["gcloud", "projects", "delete", "p"], ["gcloud", "run", "services", "delete", "s"], ["gcloud", "secrets", "versions", "access", "latest"],
            ["gcloud", "secrets", "list", "set"], ["schtasks", "/delete", "/tn", "x"], ["schtasks", "/query", "/v"],
            ["powershell", "-Command", "Remove-Item C:\\x"], ["git", "push"], ["git", "ls-files", "commit"], ["curl", "http://x"],
            # 리뷰 지적: gh api 는 GET만, -f/-F/--input 거부
            ["gh", "api", "repos/o/r", "--method", "DELETE"], ["gh", "api", "repos/o/r", "-X", "PATCH"], ["gh", "api", "repos/o/r", "--method=DELETE"],
            ["gh", "api", "repos/o/r", "-F", "a=b"], ["gh", "api", "repos/o/r", "--input", "x.json"], ["gh", "api", "repos/o/r", "--field", "a=b"],
            ["gh", "api", "repos/o/r", "--raw-field", "a=b"],
            # git 전역 옵션 우회·추가 인자
            ["git", "-c", "core.pager=evil", "ls-files", "-z"], ["git", "--exec-path=/x", "ls-files", "-z"], ["git", "ls-files", "-z", "--other"],
            ["git", "-C", "/x", "for-each-ref", "--format=%(refname:short)", "refs/tags"],
            # 파워셸 중간 인자 주입
            ns.PS_HEAD + ["Remove-Item x", "-Command", ns.PS_PROCESSES], ns.PS_HEAD[:3] + ["-EncodedCommand", "AAAA", "-Command", ns.PS_PROCESSES],
            ["powershell", "-Command", "Remove-Item x", "-NoProfile", "-NonInteractive", "-Command", ns.PS_PROCESSES],
            ns.PS_HEAD + [ns.PS_PROCESSES, "extra"], ns.PS_HEAD + [ns.PS_PROCESSES + "; Remove-Item x"],
        ]
        for argv in bad:
            with self.assertRaises(ns.ForbiddenCommand, msg=" ".join(argv)):
                ns.check_readonly(argv)

    def test_read_commands_allowed(self):
        good = [
            ["git", "ls-files", "-z"], ["git", "for-each-ref", "--format=%(refname:short)", "refs/tags"],
            ["gh", "repo", "list", "o", "--limit", "300", "--json", "name", "--jq", ".[].name"],
            ["gh", "secret", "list", "-R", "o/r", "--json", "name"], ["gh", "api", "repos/o/r/contents/.github/workflows", "--jq", ".[].name"],
            ["gh", "api", "repos/o/r", "--method", "GET"], ["gh", "api", "repos/o/r", "-X", "get"],            ["gcloud", "projects", "list", "--format=value(projectId)"], ["gcloud", "run", "services", "list", "--project", "p"],
            ["gcloud", "iam", "service-accounts", "list", "--project", "p"], ["gcloud", "secrets", "list", "--project", "p"],
            ["schtasks", "/query", "/fo", "csv", "/nh"], ns.PS_HEAD + [ns.PS_PROCESSES],
        ]
        for argv in good:
            ns.check_readonly(argv)

    def test_run_cmd_checks_before_running(self):
        called = []
        with self.assertRaises(ns.ForbiddenCommand):
            ns.run_cmd(["gh", "repo", "delete", "x"], runner=lambda *a: called.append(a))
        self.assertEqual(called, [])


class ReviewFixTest(unittest.TestCase):
    def test_stderr_raw_text_never_stored(self):
        secret = "ghp_SECRETTOKEN123 something broke"

        def fake(argv, timeout, cwd=None):
            return 1, b"", ("fatal: " + secret).encode()

        res = ns.collect_github({"github_owner": "o", "github_target_repos": ["a"]}, runner=fake)
        rep = ns.build_report([res], {"ratchet": {}}, TODAY, "t", None, (3,))
        blob = json.dumps(rep, ensure_ascii=False) + ns.render_md(rep)
        self.assertNotIn("ghp_SECRETTOKEN123", blob)
        self.assertNotIn("something broke", blob)
        self.assertEqual({u["reason"] for u in res["unverified"]}, {"기타"})
        self.assertEqual(ns.short_reason(b"HTTP 404: Not Found"), "없음(404)")
        self.assertEqual(ns.short_reason(b"Reauthentication failed"), "인증 필요")
        self.assertEqual(ns.short_reason(b"operation timed out"), "시간 초과")

        def boom():
            raise RuntimeError(secret)

        out = ns.run_collectors([(3, "x", boom)], timeout=1)
        self.assertNotIn("SECRETTOKEN", json.dumps(out, ensure_ascii=False))

    def test_multiple_section_rules_same_file(self):
        cfg = {"history_rules": [
            {"id": "HA", "repo": "r", "section_file": "p.md", "section_heading": "변경 기록", "expires": "2027-01-01"},
            {"id": "HB", "repo": "r", "section_file": "p.md", "section_heading": "사고 이력", "expires": "2027-01-01"}],
            "planned": [], "external": [], "explain_files": []}
        with tempfile.TemporaryDirectory() as d:
            def git(*a):
                subprocess.run(["git", *a], cwd=d, check=True, capture_output=True)
            git("init", "-q")
            body = "# 정책\n%s 본문\n## 변경 기록\n%s a\n## 중간\n%s 중간\n## 사고 이력\n%s b\n%s c\n" % ((OLD,) * 5)
            (Path(d) / "p.md").write_text(body, encoding="utf-8")
            git("add", "p.md")
            repo = os.path.basename(os.path.abspath(d))
            for r in cfg["history_rules"]:
                r["repo"] = repo
            res = ns.collect_repo(d, cfg)
        f = [x for x in res["findings"] if x["kind"] == "content"][0]
        self.assertEqual(set(f["sections"]), {"HA", "HB"})
        got = {(c, rid): n for c, rid, n, _ in ns.classify(f, cfg, TODAY)}
        self.assertEqual(got, {("history", "HA"): 1, ("history", "HB"): 2, ("violation", ""): 2})

    def _res(self, layer, fail=0, crashed=False, hits=None):
        r = ns.new_result(layer, "c%d" % layer)
        r["fail"] = fail
        r["crashed"] = crashed
        for rel, n in (hits or {}).items():
            r["findings"].append(content("r", rel, n))
        return r

    def test_baseline_requires_all_layers_ok(self):
        cfg = {"ratchet": {}}
        ok = ns.build_report([self._res(1), self._res(2), self._res(3)], cfg, TODAY, "t", None, (1, 2, 3))
        self.assertTrue(ok["baseline_ok"])
        bad = ns.build_report([self._res(1), self._res(2), self._res(3, fail=1)], cfg, TODAY, "t", None, (1, 2, 3))
        self.assertFalse(bad["baseline_ok"])  # 층 1이 성공해도 다른 층 실패면 기준선 아님
        crash = ns.build_report([self._res(1, crashed=True)], cfg, TODAY, "t", None, (1,))
        self.assertFalse(crash["baseline_ok"])

    def test_count_increase_is_new_violation(self):
        cfg = {"ratchet": {}}
        first = ns.build_report([self._res(1, hits={"a.py": 2, "b.py": 1})], cfg, TODAY, "t", None, (1,))
        again = ns.build_report([self._res(1, hits={"a.py": 2, "b.py": 1})], cfg, TODAY, "t", first, (1,))
        self.assertEqual(again["new_violations"], [])
        grown = ns.build_report([self._res(1, hits={"a.py": 5, "b.py": 1})], cfg, TODAY, "t", first, (1,))
        self.assertEqual(grown["new_violations"], ["1|content|r|a.py"])
        shrunk = ns.build_report([self._res(1, hits={"a.py": 1})], cfg, TODAY, "t", first, (1,))
        self.assertEqual(shrunk["new_violations"], [])
        self.assertEqual(shrunk["resolved_violations"], ["1|content|r|b.py"])

    def test_compare_only_same_layer_combination(self):
        cfg = {"ratchet": {}}
        first = ns.build_report([self._res(1, hits={"a.py": 1})], cfg, TODAY, "t", None, (1,))
        other = ns.build_report([self._res(1, hits={"a.py": 1, "z.py": 1}), self._res(2)], cfg, TODAY, "t", first, (1, 2))
        self.assertIsNone(other["prev_date"])
        self.assertEqual(other["new_violations"], [])
        # 정상이 아닌 이전 스캔은 기준선이 아니다
        bad_prev = dict(first, baseline_ok=False)
        self.assertEqual(ns.build_report([self._res(1, hits={"a.py": 9})], cfg, TODAY, "t", bad_prev, (1,))["new_violations"], [])

    def test_output_dir_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            (repo / "sub").mkdir(parents=True)
            with self.assertRaises(SystemExit):
                ns.check_out_dir(repo / "sub" / "out", [repo])  # 저장소 안
            with self.assertRaises(SystemExit):
                ns.check_out_dir(repo, [repo])  # 같은 폴더
            with self.assertRaises(SystemExit):
                ns.check_out_dir(Path(d), [repo])  # 출력 폴더가 저장소를 품음
            ns.check_out_dir(Path(d) / "elsewhere", [repo])
            with self.assertRaises(SystemExit):
                ns.main(["--layers", "1", "--out", str(repo / "out"), "--repos", str(repo), "--no-write"])

    def test_results_dir_always_excluded_from_scan(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*a):
                subprocess.run(["git", *a], cwd=d, check=True, capture_output=True)
            git("init", "-q")
            (Path(d) / "res").mkdir()
            (Path(d) / "res" / "x.md").write_text(OLD, encoding="utf-8")
            (Path(d) / "keep.md").write_text(OLD, encoding="utf-8")
            git("add", "res", "keep.md")
            res = ns.collect_repo(d, {"history_rules": [], "_exclude_dirs": [str(Path(d) / "res")]})
            self.assertEqual([f["subject"] for f in res["findings"] if f["kind"] == "content"], ["keep.md"])

    def test_summary_separates_records_and_hits(self):
        cfg = {"ratchet": {}}
        r = self._res(1, hits={"a.py": 7})
        r["findings"].append(ns.finding(1, "path", "%s_x.md" % OLD, "r"))
        rep = ns.build_report([r], cfg, TODAY, "t", None, (1,))
        s1 = rep["summary"]["1"]
        self.assertEqual(s1["violation"], 2)  # 발견 레코드 수
        self.assertEqual(s1["hits_by_cat"]["violation"], 8)  # 적중 횟수
        self.assertEqual(s1["by_kind"]["violation"], {"content": [1, 7], "path": [1, 1]})
        md = ns.render_md(rep)
        self.assertIn("2 (8)", md)
        self.assertIn("내용 적중 1레코드/7적중", md)
        self.assertIn("파일·폴더 이름 적중 1레코드/1적중", md)

    def test_exit_codes_and_strict(self):
        cfg = {"ratchet": {}, "manual_checks": [{"layer": 3, "what": "수동"}]}
        unv = self._res(3)
        rep = ns.build_report([unv], cfg, TODAY, "t", None, (3,))
        self.assertEqual(rep["totals"]["violation"], 0)
        self.assertFalse(rep["complete"])
        self.assertEqual(rep["exit_code"], 0)  # 기본: 미확인 때문에 막지 않는다
        self.assertIn("complete=false", ns.render_md(rep))
        self.assertEqual(ns.build_report([unv], cfg, TODAY, "t", None, (3,), strict=True)["exit_code"], 2)
        viol = ns.build_report([self._res(1, hits={"a.py": 1})], cfg, TODAY, "t", None, (1,), strict=True)
        self.assertEqual(viol["exit_code"], 1)  # 위반이 우선
        clean = ns.build_report([self._res(1)], {"ratchet": {}}, TODAY, "t", None, (1,), strict=True)
        self.assertTrue(clean["complete"])
        self.assertEqual(clean["exit_code"], 0)

    def test_main_strict_exit_code(self):
        import contextlib
        import io
        from unittest import mock
        fake = [(2, "x", lambda: ns.new_result(2, "x"))]  # 실제 PC 상태에 기대지 않는다(수동 확인 항목이 남아 complete=false)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ns, "build_collectors", return_value=fake):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ns.main(["--layers", "2", "--out", str(Path(d) / "o1"), "--no-write"]), 0)
                self.assertEqual(ns.main(["--layers", "2", "--out", str(Path(d) / "o2"), "--no-write", "--strict"]), 2)


class RepoCollectorTest(unittest.TestCase):
    def test_collect_repo_skips_secrets_binary_large(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*a):
                subprocess.run(["git", *a], cwd=d, check=True, capture_output=True)

            git("init", "-q")
            (Path(d) / "a.py").write_text("x = '%s'\n# 새김\n" % OLD, encoding="utf-8")
            (Path(d) / ("%s_notes.md" % OLD)).write_text("hi\n", encoding="utf-8")
            (Path(d) / ".env").write_text("%s=SUPERSECRET\n" % OLD.upper(), encoding="utf-8")
            (Path(d) / "my_vault").mkdir()
            (Path(d) / "my_vault" / "k.txt").write_text(OLD + " SUPERSECRET", encoding="utf-8")
            (Path(d) / "bin.dat").write_bytes(b"\0\1" + OLD.encode())
            (Path(d) / "big.txt").write_text(OLD * 10, encoding="utf-8")
            git("add", "a.py", "bin.dat", "big.txt", ".env", "my_vault")
            cfg = {"max_file_bytes": 50, "history_rules": []}
            res = ns.collect_repo(d, cfg)
            blob = json.dumps(res, ensure_ascii=False)
            self.assertNotIn("SUPERSECRET", blob)
            st = res["stats"]
            self.assertEqual(st["skipped_secret"], 2)
            self.assertEqual(st["skipped_binary"], 1)
            self.assertEqual(st["skipped_large"], 1)
            kinds = sorted((f["kind"], f["subject"]) for f in res["findings"])
            self.assertIn(("content", "a.py"), kinds)
            self.assertIn(("path", "%s_notes.md" % OLD), kinds)  # 추적되지 않은 새 파일도 본다
            self.assertEqual([f["count"] for f in res["findings"] if f["subject"] == "a.py"], [2])


class RemoteHostTest(unittest.TestCase):
    CFG = {"name": "구PC", "host": "h1", "roots": ["$HOME/ops", "$HOME/player-bt-*"]}

    def test_remote_collects_paths_and_counts_only(self):
        def fake(argv, timeout, cwd=None):
            if argv[-1] == ns.REMOTE_CRON_SCRIPT:
                return 0, b"2\n", b""
            return 0, "/home/u/ops/jobs.toml:3\n/home/u/ops/b.py:0\n/home/u/x/a:1\n".encode(), b""

        res = ns.collect_remote(self.CFG, runner=fake)
        subj = sorted((f["kind"], f["subject"], f["count"]) for f in res["findings"])
        self.assertEqual(subj, [("remote_cron", "구PC crontab", 2), ("remote_file", "구PC:/home/u/ops/jobs.toml", 3), ("remote_file", "구PC:/home/u/x/a", 1)])
        self.assertEqual(res["unverified"], [])

    def test_remote_zero_hits_and_ssh_failure(self):
        ok = ns.collect_remote(self.CFG, runner=lambda a, t, cwd=None: (1, b"0\n", b""))
        self.assertEqual((ok["findings"], ok["unverified"]), ([], []))
        bad = ns.collect_remote(self.CFG, runner=lambda a, t, cwd=None: (255, b"", b"ssh: connect to host timed out"))
        self.assertEqual(len(bad["unverified"]), 2)
        self.assertEqual(bad["findings"], [])

    def test_remote_findings_are_violations_unless_planned(self):
        f = ns.finding(2, "remote_file", "구PC:/home/u/ops/jobs.toml", None, count=3)
        self.assertEqual(ns.classify(f, {}, TODAY)[0][0], "violation")

    def test_ssh_gate_accepts_only_fixed_forms(self):
        h = ns.SSH_HEAD + ["h1"]
        ns.check_readonly(h + [ns.REMOTE_CRON_SCRIPT])
        ns.check_readonly(h + [ns.remote_files_script(self.CFG["roots"])])
        for bad in (["ssh", "h1", "ls"], h + ["rm -rf ~"], h + [ns.REMOTE_CRON_SCRIPT + "; rm x"], h + [ns.remote_files_script(["/etc"])],
                    ns.SSH_HEAD + ["h 1", ns.REMOTE_CRON_SCRIPT], ns.SSH_HEAD[:3] + ["h1", ns.REMOTE_CRON_SCRIPT]):
            with self.assertRaises(ns.ForbiddenCommand):
                ns.check_readonly(bad)

    def test_build_collectors_adds_remote_hosts(self):
        cs = ns.build_collectors({"remote_hosts": [self.CFG]}, (2,), [], None, 5)
        self.assertIn("remote:구PC", [c[1] for c in cs])


if __name__ == "__main__":
    unittest.main()
