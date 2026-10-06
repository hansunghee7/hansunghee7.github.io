"""ledger_lint.py(업무대장 모순 점검)와 delegate_lint.py(위임 결과 독립 확인)의 판정 로직 시험(외부 호출 없음).
- ledger_lint: 대장 경로(LEDGER)·저장소 루트(ROOT)를 임시 폴더의 가짜 md로 바꿔 통과·실패 사례를 확인한다.
- delegate_lint: ruff·로컬 모델 루프·py_compile 호출(subprocess)은 mock으로 대체하고 저장소 루트(ROOT)는 임시 폴더로 바꾼다.
  jsonschema가 설치돼 있지 않으면 봉투 스키마 시험만 건너뛴다."""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).parent
# ledger_lint.blocks()는 대장 파일을 열고 닫지 않는다(소스 쪽 관찰). 시험 출력이 경고로 어지럽지 않게 이 경고만 끈다.
warnings.filterwarnings("ignore", category=ResourceWarning)
HAVE_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
if not HAVE_JSONSCHEMA:  # import만 통과시키는 대역(스키마 시험은 건너뜀)
    sys.modules.setdefault("jsonschema", SimpleNamespace(validate=lambda *a, **k: None, ValidationError=type("ValidationError", (Exception,), {})))


class Out(io.StringIO):
    def reconfigure(self, **kw):  # ledger_lint는 import할 때 표준출력 인코딩을 바꾼다
        pass


def load(name):
    spec = importlib.util.spec_from_file_location(name + "_under_test", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "stdout", Out()):
        spec.loader.exec_module(mod)
    return mod


ll = load("ledger_lint")
dl = load("delegate_lint")


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


# ---------------------------------------------------------------- ledger_lint
CLEAN = """# 탐 업무대장

### [사장님] N10: 결정 대기 안건
- 사장님 할 일: 방안 선택

### [진행] N11: 정상 진행
- 다음: 계속
"""

STALE = """### [사장님] N10: 유료 전환
- 현재: 선택 대기
- 사장님 할 일: 방안 선택
- 10/2 사장님 결정: 직접 전환
- 정리: 끝
"""


class LedgerBase(TempDir):
    def setUp(self):
        super().setUp()
        (self.dir / "docs").mkdir()
        for name, val in (("ROOT", str(self.dir)), ("LEDGER", str(self.dir / "docs" / "탐_업무대장.md"))):
            p = mock.patch.object(ll, name, val)
            p.start()
            self.addCleanup(p.stop)

    def ledger(self, text):
        return self.write("docs/탐_업무대장.md", text)

    def run_main(self, *argv):
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["ledger_lint.py", *argv]), contextlib.redirect_stdout(buf):
            rc = ll.main()
        return rc, buf.getvalue()


class Regexes(unittest.TestCase):
    def test_decided_matches_boss_decision_wording(self):
        for s in ("사장님 결정: B안", "사장님이 10/2 결정", "사장님 지시 2026-10-03", "사장님 확정", "사장님 승인", "사장님 합의", "사장님 정정", "사장님 판단", "사장님 제안"):
            with self.subTest(s=s):
                self.assertTrue(ll.DECIDED.search(s))

    def test_decided_rejects_other_text(self):
        for s in ("사장님 말씀", "탐이 결정", "결정만 있음", "사장님" + "가" * 13 + "결정"):  # 사이 글자가 12자를 넘으면 불일치
            with self.subTest(s=s):
                self.assertFalse(ll.DECIDED.search(s))

    def test_waiting_matches(self):
        for s in ("선택 대기", "결정 대기 중", "결정 필요", "선택 필요", "사장님 할 일: 방안 선택", "사장님 할 일: 이걸 결정"):
            with self.subTest(s=s):
                self.assertTrue(ll.WAITING.search(s))

    def test_waiting_rejects_other_text(self):
        for s in ("사장님 할 일: 없음", "대기 중", "선택", "결정이 끝남"):
            with self.subTest(s=s):
                self.assertFalse(ll.WAITING.search(s))


class Blocks(LedgerBase):
    def test_parses_status_id_title_and_body(self):
        self.ledger("앞부분은 무시\n\n### [진행] N5: 제목 하나\n- 줄1\n- 줄2\n\n### [완료] N6 콜론 없음\n- 줄3\n")
        got = list(ll.blocks())
        self.assertEqual([(s, i, t) for s, i, t, _ in got], [("진행", "N5", "제목 하나"), ("완료", "N6", "콜론 없음")])
        self.assertEqual(got[0][3][:2], ["- 줄1", "- 줄2"])  # 머리줄은 본문에 없다

    def test_crlf_and_headers_without_id_are_handled(self):
        self.ledger("### [진행] N1: 가\r\n- a\r\n### [진행] \r\n- b\r\n")
        got = list(ll.blocks())
        self.assertEqual([i for _, i, _, _ in got], ["N1"])  # id가 없는 머리줄은 건너뜀
        self.assertEqual(got[0][3][0], "- a")

    def test_env_var_overrides_default_ledger_path(self):
        with mock.patch.dict(os.environ, {"LEDGER_FILE": "/x/y.md"}), mock.patch.object(sys, "stdout", Out()):
            spec = importlib.util.spec_from_file_location("ledger_lint_env", HERE / "ledger_lint.py")
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
        self.assertEqual(m.LEDGER, "/x/y.md")


class StaleDetection(LedgerBase):
    def test_clean_ledger_passes(self):
        self.ledger(CLEAN)
        rc, out = self.run_main()
        self.assertEqual((rc, out.strip()), (0, "모순 칸 없음"))

    def test_waiting_before_decision_is_flagged(self):
        self.ledger(STALE)
        rc, out = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn("⚠ N10 [사장님] 유료 전환: 낡았을 수 있는 대기 문구 2줄", out)
        self.assertIn("- 현재: 선택 대기", out)
        self.assertIn("모순 1건", out)

    def test_waiting_after_decision_is_fine(self):
        self.ledger("### [사장님] N1: 안건\n- 사장님 결정: A로\n- 새 질문: 결정 필요\n")
        rc, out = self.run_main()
        self.assertEqual((rc, out.strip()), (0, "모순 칸 없음"))

    def test_corrected_lines_are_excluded(self):
        for fixed in ("선택 대기 정정: 이미 정함", "결정 완료 (선택 대기 해소)", "결정됨, 선택 대기 아님", "결정 대기 없음", "결정 예정: 없음 (결정 대기)"):
            with self.subTest(fixed=fixed):
                self.ledger(f"### [사장님] N1: 안건\n- {fixed}\n- 사장님 결정: A\n")
                self.assertEqual(self.run_main()[0], 0)

    def test_done_and_dropped_are_skipped(self):
        for status in ("완료", "드랍"):
            with self.subTest(status=status):
                self.ledger(STALE.replace("[사장님]", f"[{status}]"))
                self.assertEqual(self.run_main()[0], 0)

    def test_other_open_statuses_are_checked(self):
        self.ledger(STALE.replace("[사장님]", "[확인필요]"))
        self.assertEqual(self.run_main()[0], 1)

    def test_only_two_stale_lines_are_printed_but_all_counted(self):
        text = "### [사장님] N1: 안건\n- 선택 대기 1\n- 선택 대기 2\n- 선택 대기 3\n- 사장님 결정: 끝\n"
        self.ledger(text)
        _, out = self.run_main()
        self.assertIn("낡았을 수 있는 대기 문구 3줄", out)
        self.assertIn("선택 대기 1", out)
        self.assertIn("선택 대기 2", out)
        self.assertNotIn("선택 대기 3", out)

    def test_each_block_is_judged_separately(self):
        self.ledger("### [사장님] N1: 가\n- 선택 대기\n\n### [사장님] N2: 나\n- 사장님 결정: A\n")  # 결정은 다른 칸에 있다
        self.assertEqual(self.run_main()[0], 0)

    def test_multiple_bad_blocks_counted(self):
        self.ledger(STALE + "\n" + STALE.replace("N10", "N12"))
        rc, out = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn("모순 2건", out)


class MeasureRule(LedgerBase):
    def check(self, header, body="- 다음: 설계\n"):
        self.ledger(f"### {header}\n{body}")
        return self.run_main()

    def test_n160_in_progress_without_measure_line_fails(self):
        rc, out = self.check("[진행] N160: 새 설계")
        self.assertEqual(rc, 1)
        self.assertIn("⚠ N160 [진행]", out)
        self.assertIn("측정 기준(정답지 출처)이 적혀 있지 않음", out)

    def test_measure_or_answer_key_word_passes(self):
        self.assertEqual(self.check("[진행] N160: 설계", "- 측정: 일일 조회 수\n")[0], 0)
        self.assertEqual(self.check("[진행] N200: 설계", "- 정답지: 로그 100건\n")[0], 0)

    def test_exempt_cases(self):
        self.assertEqual(self.check("[진행] N159: 옛 번호")[0], 0)
        self.assertEqual(self.check("[대기] N160: 대기 상태")[0], 0)
        self.assertEqual(self.check("[진행] B50: 다른 번호 체계")[0], 0)
        self.assertEqual(self.check("[완료] N170: 끝난 일")[0], 0)

    def test_measure_rule_still_applies_in_boss_mode(self):
        self.ledger("### [진행] N161: 설계\n- 다음: x\n")
        rc, out = self.run_main("--boss")
        self.assertEqual(rc, 1)  # 현재 동작 기록: --boss에서도 측정 규칙 위반은 종료 코드 1
        self.assertIn("⚠ N161", out)
        self.assertNotIn("모순 칸 없음", out)


class BossMode(LedgerBase):
    def test_prints_decision_and_waiting_lines_of_boss_blocks_only(self):
        self.ledger(STALE + "\n### [진행] N11: 다른 칸\n- 사장님 결정: 이 줄은 출력 안 됨\n")
        rc, out = self.run_main("--boss")
        self.assertEqual(rc, 0)
        self.assertIn("## N10 [사장님] 유료 전환", out)
        self.assertIn("  - 10/2 사장님 결정: 직접 전환", out)
        self.assertIn("- 현재: 선택 대기", out)
        self.assertNotIn("정리: 끝", out)  # 결정·대기 줄만
        self.assertNotIn("N11", out)
        self.assertNotIn("낡았을 수 있는", out)  # --boss에서는 모순 경고를 따로 내지 않는다
        self.assertNotIn("모순 칸 없음", out)

    def test_long_lines_are_not_cut(self):
        self.ledger("### [사장님] N1: 안건\n- 사장님 결정: " + "가" * 700 + "\n")
        _, out = self.run_main("--boss")
        self.assertIn("가" * 700, out)


class Find(LedgerBase):
    def test_finds_only_decision_lines_with_keyword_across_files(self):
        self.ledger("### [진행] N1: 가\n- 사장님 결정: 유료 전환은 직접\n- 유료 전환 메모(결정 아님)\n")
        self.write("docs/탐_업무대장_히스토리.md", "사장님 지시: 유료 플랜 검토\n")
        self.write("docs/진행상황.md", "x\n사장님 승인: 유료 전환 진행\n")
        self.write("docs/역할노트-탐.md", "관계없는 줄\n")
        self.write("docs/진행상황_아카이브/2026-09-01.md", "사장님 합의: 유료 전환 보류\n")
        rc, out = self.run_main("--find", "유료 전환")
        lines = out.strip().splitlines()
        self.assertEqual(rc, 0)
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith(os.path.join("docs", "탐_업무대장.md") + ":2: "))
        self.assertTrue(lines[1].startswith(os.path.join("docs", "진행상황.md") + ":2: "))
        self.assertIn("2026-09-01.md:1: 사장님 합의: 유료 전환 보류", lines[2])
        self.assertNotIn("메모(결정 아님)", out)

    def test_missing_files_and_no_match_are_silent(self):
        self.ledger("### [진행] N1: 가\n- 사장님 결정: A\n")
        rc, out = self.run_main("--find", "없는키워드")
        self.assertEqual((rc, out), (0, ""))

    def test_matched_line_is_cut_to_400_chars(self):
        self.ledger("### [진행] N1: 가\n- 사장님 결정: 키워드 " + "나" * 600 + "\n")
        _, out = self.run_main("--find", "키워드")
        self.assertLessEqual(len(out.strip().split(": ", 1)[1]), 400)


# ---------------------------------------------------------------- delegate_lint
GOOD = {"file": "scripts/x.py", "status": "PASS", "iterations": 2, "guard_rejects": 0, "findings_before": 2, "findings_after": 0, "_work": "/tmp/x.py"}


class DelegateBase(TempDir):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(dl, "ROOT", str(self.dir))
        p.start()
        self.addCleanup(p.stop)


@unittest.skipUnless(HAVE_JSONSCHEMA, "jsonschema 없음")
class Envelope(unittest.TestCase):
    def validate(self, env):
        import jsonschema
        jsonschema.validate(env, dl.ENVELOPE)

    def test_valid(self):
        self.validate({k: v for k, v in GOOD.items() if not k.startswith("_")})

    def test_invalid_variants(self):
        import jsonschema
        base = {k: v for k, v in GOOD.items() if not k.startswith("_")}
        bad = [
            {k: v for k, v in base.items() if k != "iterations"},  # 필수 칸 빠짐
            {**base, "extra": 1},  # 모르는 칸
            {**base, "status": "OK"},
            {**base, "iterations": -1},
            {**base, "guard_rejects": -1},
            {**base, "findings_after": "0"},
            {**base, "file": 3},
        ]
        for env in bad:
            with self.subTest(env=env), self.assertRaises(jsonschema.ValidationError):
                self.validate(env)


class IndependentCheck(DelegateBase):
    def run_check(self, env_msg=None, *, orig_other=2, work_other=0, compiled=0):
        env_msg = env_msg or dict(GOOD)
        counts = {os.path.join(str(self.dir), "scripts/x.py"): orig_other, env_msg["_work"]: work_other}
        with mock.patch.object(dl, "ruff_json", side_effect=lambda path, select: [0] * counts[path]) as rj, \
                mock.patch.object(dl.subprocess, "run", return_value=SimpleNamespace(returncode=compiled)) as run:
            why = dl.independent_check("scripts/x.py", env_msg)
        return why, rj, run

    def test_happy_path(self):
        why, rj, _ = self.run_check()
        self.assertEqual(why, "")
        self.assertEqual({c.args[1] for c in rj.call_args_list}, {"F,E9"})

    @unittest.skipUnless(HAVE_JSONSCHEMA, "jsonschema 없음")
    def test_schema_violation_is_rejected_before_anything_else(self):
        why, rj, run = self.run_check({**GOOD, "status": "MAYBE"})
        self.assertTrue(why.startswith("봉투 스키마 위반"))
        rj.assert_not_called()
        run.assert_not_called()

    @unittest.skipUnless(HAVE_JSONSCHEMA, "jsonschema 없음")
    def test_underscore_keys_are_not_part_of_the_schema(self):
        why, _, _ = self.run_check({**GOOD, "_extra": object()})
        self.assertEqual(why, "")  # '_'로 시작하는 칸은 검증에서 뺀다

    def test_not_pass_status_or_remaining_findings(self):
        self.assertEqual(self.run_check({**GOOD, "status": "FAIL"})[0], "루프가 PASS하지 못함")
        self.assertEqual(self.run_check({**GOOD, "findings_after": 1})[0], "루프가 PASS하지 못함")

    def test_py_compile_failure(self):
        why, _, run = self.run_check(compiled=1)
        self.assertEqual(why, "py_compile 실패")
        self.assertIn("py_compile", run.call_args.args[0])

    def test_other_rule_errors_must_not_increase(self):
        # 원본의 F,E9 지적 5건 중 대상 지적 2건을 뺀 3건이 기준선
        self.assertEqual(self.run_check(orig_other=5, work_other=3)[0], "")
        self.assertEqual(self.run_check(orig_other=5, work_other=1)[0], "")
        why = self.run_check(orig_other=5, work_other=4)[0]
        self.assertEqual(why, "다른 규칙 오류가 늘어남(3 -> 4)")

    def test_baseline_cannot_go_below_zero(self):
        # 원본 지적이 대상 지적보다 적게 집계된 경우에도 기준선은 0으로 본다(0건이면 통과, 1건부터 거절)
        self.assertEqual(self.run_check(orig_other=1, work_other=0)[0], "")
        self.assertTrue(self.run_check(orig_other=1, work_other=1)[0].startswith("다른 규칙 오류가 늘어남"))


class RuffJson(unittest.TestCase):
    def call(self, stdout):
        with mock.patch.object(dl.subprocess, "run", return_value=SimpleNamespace(stdout=stdout)) as run:
            return dl.ruff_json("a.py", "F401"), run

    def test_parses_json_and_passes_arguments(self):
        out, run = self.call('[{"filename": "a.py"}]')
        self.assertEqual(out, [{"filename": "a.py"}])
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[1:3], ["-m", "ruff"])
        self.assertIn("F401", cmd)
        self.assertEqual(cmd[-1], "a.py")

    def test_empty_output_is_empty_list(self):
        self.assertEqual(self.call("")[0], [])
        self.assertEqual(self.call(None)[0], [])

    def test_invalid_json_raises(self):
        with self.assertRaises(ValueError):  # 현재 동작 기록: 깨진 출력은 예외로 올라온다
            self.call("not json")


class Candidates(DelegateBase):
    def write_lines(self, rel, n):
        self.write(rel, "x = 1\n" * n)

    def test_relative_sorted_unique_and_line_limit(self):
        for rel, n in (("scripts/b.py", 10), ("scripts/a.py", 300), ("scripts/big.py", 301)):
            self.write_lines(rel, n)
        found = [{"filename": str(self.dir / "scripts" / name)} for name in ("b.py", "a.py", "b.py", "big.py")]
        with mock.patch.object(dl, "ruff_json", return_value=found) as rj:
            ok, skipped = dl.candidates("scripts", 300)
        self.assertEqual((ok, skipped), (["scripts/a.py", "scripts/b.py"], ["scripts/big.py"]))
        self.assertEqual(rj.call_args.args, (os.path.join(str(self.dir), "scripts"), dl.RULES))

    def test_no_findings(self):
        with mock.patch.object(dl, "ruff_json", return_value=[]):
            self.assertEqual(dl.candidates("scripts", 300), ([], []))

    def test_max_lines_boundary_is_inclusive(self):
        self.write_lines("scripts/a.py", 5)
        with mock.patch.object(dl, "ruff_json", return_value=[{"filename": str(self.dir / "scripts" / "a.py")}]):
            self.assertEqual(dl.candidates("scripts", 5)[0], ["scripts/a.py"])
            self.assertEqual(dl.candidates("scripts", 4)[1], ["scripts/a.py"])


class Delegate(DelegateBase):
    def run_delegate(self, stdout, before=3, after=0, env=None):
        self.write("scripts/x.py", "import os\n")
        tmp = self.dir / "work"
        tmp.mkdir(exist_ok=True)
        with mock.patch.object(dl, "ruff_json", side_effect=[[0] * before, [0] * after]), \
                mock.patch.object(dl.subprocess, "run", return_value=SimpleNamespace(stdout=stdout)) as run, \
                mock.patch.dict(os.environ):
            os.environ.pop("ACL_BACKEND", None)  # 시험 환경 값이 새어 들어오지 않게
            os.environ.update(env or {})
            res = dl.delegate("scripts/x.py", str(tmp))
        return res, run, tmp

    def test_reads_metrics_and_counts(self):
        res, run, tmp = self.run_delegate("log\n[metric] Status: PASS\n[metric] Iterations: 4\n[metric] GuardRejects: 2\n")
        self.assertEqual({k: v for k, v in res.items() if k != "_work"},
                         {"file": "scripts/x.py", "status": "PASS", "iterations": 4, "guard_rejects": 2, "findings_before": 3, "findings_after": 0})
        self.assertEqual(res["_work"], os.path.join(str(tmp), "x.py"))
        self.assertTrue(Path(res["_work"]).exists())  # 원본이 아닌 임시 복사본
        self.assertEqual((self.dir / "scripts" / "x.py").read_text(encoding="utf-8"), "import os\n")

    def test_missing_metrics_default_to_fail(self):
        res, _, _ = self.run_delegate("작업자가 아무 것도 출력하지 않음")
        self.assertEqual((res["status"], res["iterations"], res["guard_rejects"]), ("FAIL", 0, 0))

    def test_default_backend_is_set_but_existing_value_is_kept(self):
        _, run, _ = self.run_delegate("")
        self.assertEqual(run.call_args.kwargs["env"]["ACL_BACKEND"], "ollama:qwen2.5-coder:14b")
        self.assertEqual(run.call_args.kwargs["env"]["PYTHONIOENCODING"], "utf-8")
        _, run, _ = self.run_delegate("", env={"ACL_BACKEND": "other:model"})
        self.assertEqual(run.call_args.kwargs["env"]["ACL_BACKEND"], "other:model")

    def test_loop_is_run_on_the_copy_not_the_original(self):
        _, run, tmp = self.run_delegate("")
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[-1], os.path.join(str(tmp), "x.py"))
        self.assertIn("--select", cmd)
        self.assertEqual(cmd[cmd.index("--select") + 1], dl.RULES)


class Main(DelegateBase):
    def run_main(self, files, skipped, delegates, checks, *argv):
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["delegate_lint.py", *argv]), \
                mock.patch.object(dl, "candidates", return_value=(files, skipped)), \
                mock.patch.object(dl, "delegate", side_effect=delegates), \
                mock.patch.object(dl, "independent_check", side_effect=checks), \
                contextlib.redirect_stdout(buf):
            dl.main()
        return json.loads(buf.getvalue().strip().splitlines()[-1])

    def env_for(self, rel, new_text):
        work = self.dir / ("work_" + rel.replace("/", "_"))
        work.write_text(new_text, encoding="utf-8")
        return {"file": rel, "status": "PASS", "iterations": 3, "guard_rejects": 1, "findings_before": 2, "findings_after": 0, "_work": str(work)}

    def test_passing_file_becomes_diff_proposal(self):
        self.write("scripts/x.py", "import os\nprint(1)\n")
        s = self.run_main(["scripts/x.py"], ["scripts/big.py"], [self.env_for("scripts/x.py", "print(1)\n")], [""])
        self.assertEqual(s["candidates"], 1)
        self.assertEqual(s["skipped_too_long"], ["scripts/big.py"])
        self.assertEqual(s["rejected"], [])
        self.assertEqual(s["proposed"], [{"file": "scripts/x.py", "iterations": 3, "guard_rejects": 1, "findings": "2->0"}])
        diff_path = self.dir / s["out_dir"] / "scripts__x.py.diff"
        diff = diff_path.read_text(encoding="utf-8")
        self.assertIn("--- a/scripts/x.py", diff)
        self.assertIn("+++ b/scripts/x.py", diff)
        self.assertIn("-import os", diff)
        self.assertTrue(s["out_dir"].startswith(".hermes/data/delegations/"))
        self.assertEqual((self.dir / "scripts" / "x.py").read_text(encoding="utf-8"), "import os\nprint(1)\n")  # 저장소 파일은 그대로

    def test_rejected_file_records_reason_and_writes_no_diff(self):
        self.write("scripts/x.py", "import os\n")
        s = self.run_main(["scripts/x.py"], [], [self.env_for("scripts/x.py", "")], ["py_compile 실패"])
        self.assertEqual(s["rejected"], [{"file": "scripts/x.py", "why": "py_compile 실패"}])
        self.assertEqual(s["proposed"], [])
        self.assertEqual(list((self.dir / s["out_dir"]).iterdir()), [])

    def test_max_files_limits_how_many_are_delegated(self):
        for n in "abc":
            self.write(f"scripts/{n}.py", "import os\n")
        envs = [self.env_for(f"scripts/{n}.py", "") for n in "ab"]
        s = self.run_main([f"scripts/{n}.py" for n in "abc"], [], envs, ["", ""], "--max-files", "2")
        self.assertEqual(s["candidates"], 3)  # 후보 수는 제한 전 값
        self.assertEqual([p["file"] for p in s["proposed"]], ["scripts/a.py", "scripts/b.py"])

    def test_mixed_results_and_no_candidates(self):
        self.write("scripts/a.py", "import os\n")
        self.write("scripts/b.py", "import os\n")
        s = self.run_main(["scripts/a.py", "scripts/b.py"], [], [self.env_for("scripts/a.py", ""), self.env_for("scripts/b.py", "")], ["", "다른 규칙 오류가 늘어남(1 -> 2)"])
        self.assertEqual(([p["file"] for p in s["proposed"]], [r["file"] for r in s["rejected"]]), (["scripts/a.py"], ["scripts/b.py"]))
        s = self.run_main([], [], [], [])
        self.assertEqual((s["candidates"], s["proposed"], s["rejected"]), (0, [], []))

    def test_summary_is_one_json_line_with_seconds(self):
        s = self.run_main([], [], [], [])
        self.assertIsInstance(s["seconds"], (int, float))


if __name__ == "__main__":
    unittest.main()
