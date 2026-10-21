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
        f = content("r", "pol.md", n=3, hit_lines={2: 1, 10: 1, 11: 1}, sections={"변경 기록": [9, 10, 11]})
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
        rep = ns.build_report([res], self.cfg, TODAY, "t", {"date": "d", "violation_keys": []}, (1,))
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
        ]
        for argv in bad:
            with self.assertRaises(ns.ForbiddenCommand, msg=" ".join(argv)):
                ns.check_readonly(argv)

    def test_read_commands_allowed(self):
        good = [
            ["git", "ls-files", "-z"], ["git", "for-each-ref", "--format=%(refname:short)", "refs/tags"],
            ["gh", "repo", "list", "o", "--limit", "300", "--json", "name", "--jq", ".[].name"],
            ["gh", "secret", "list", "-R", "o/r", "--json", "name"], ["gh", "api", "repos/o/r/contents/.github/workflows", "--jq", ".[].name"],
            ["gcloud", "projects", "list", "--format=value(projectId)"], ["gcloud", "run", "services", "list", "--project", "p"],
            ["gcloud", "iam", "service-accounts", "list", "--project", "p"], ["gcloud", "secrets", "list", "--project", "p"],
            ["schtasks", "/query", "/fo", "csv", "/nh"], ["powershell", "-NoProfile", "-Command", ns.PS_PROCESSES],
        ]
        for argv in good:
            ns.check_readonly(argv)

    def test_run_cmd_checks_before_running(self):
        called = []
        with self.assertRaises(ns.ForbiddenCommand):
            ns.run_cmd(["gh", "repo", "delete", "x"], runner=lambda *a: called.append(a))
        self.assertEqual(called, [])


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


if __name__ == "__main__":
    unittest.main()
