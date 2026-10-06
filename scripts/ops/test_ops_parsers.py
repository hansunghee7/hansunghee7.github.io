"""proc.py·import_ops_tables.py의 순수 파싱·정리 함수 시험(외부 호출 없음).
DB(opsdb)·네트워크에는 접속하지 않고, 파일을 읽는 함수는 임시 폴더에 가짜 md·csv를 만들어 확인한다.
비밀값 모양 문자열은 소스에 그대로 적지 않고 실행 중에 조립한다(유출 검사 오탐 방지)."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))


def load(name):
    spec = importlib.util.spec_from_file_location(name + "_under_test", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


proc = load("proc")
imp = load("import_ops_tables")
FAKE_SECRETS = ["sk-" + "a" * 12, "AI" + "za" + "b" * 22, "sb_" + "secret_x", "gh" + "p_" + "c" * 8, "-----" + "BEGIN KEY"]


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, name, text):
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return p


class ProcClean(unittest.TestCase):
    def test_ordinary_and_empty_text_pass(self):
        proc.clean()
        proc.clean(None, "", "자막은 한 번에 10글자 이내", "sk-짧음")
        proc.clean("토큰 사용량 설명", "ghp 라는 단어만")  # 접두어 모양이 아니면 통과

    def test_secret_shapes_exit(self):
        for s in FAKE_SECRETS:
            with self.subTest(s=s[:6]), self.assertRaises(SystemExit):
                proc.clean("정상 문장", s)

    def test_secret_check_is_case_insensitive(self):
        with self.assertRaises(SystemExit):
            proc.clean(("sk-" + "A" * 12).upper())


class ProcRow(unittest.TestCase):
    def test_all_columns_default_to_none(self):
        r = proc.row()
        self.assertEqual(set(r), set(proc.COLS))
        self.assertTrue(all(v is None for v in r.values()))

    def test_overrides(self):
        r = proc.row(owner="핏", section="step", no="3", raw={"boss": "x"})
        self.assertEqual((r["owner"], r["section"], r["no"], r["raw"], r["title"]), ("핏", "step", "3", {"boss": "x"}, None))

    def test_now_format(self):
        import re
        self.assertRegex(proc.now(), r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


class ProcSteps(unittest.TestCase):
    def rows(self):
        return [
            {"id": 3, "owner": "핏", "no": "10", "title": "열 번째", "status": "사용", "raw": {}},
            {"id": 1, "owner": "핏", "no": "2", "title": "두 번째", "status": "사용", "raw": {}},
            {"id": 2, "owner": "핏", "no": "1", "title": "숨긴 것", "status": "숨김", "raw": {}},
            {"id": 4, "owner": "핏", "no": "1", "title": "첫 번째", "status": "사용", "raw": {}},
        ]

    def test_hides_retired_and_sorts_numerically(self):
        with mock.patch.object(proc.opsdb, "select", return_value=self.rows()) as sel:
            rs = proc.steps_of("핏")
        self.assertEqual([r["title"] for r in rs], ["첫 번째", "두 번째", "열 번째"])  # 문자열 정렬이면 10이 2보다 앞선다
        args, kw = sel.call_args
        self.assertEqual(args[0], "tasks")
        self.assertEqual(kw["where"], {"section": "eq.step", "owner": "eq.핏"})

    def test_empty(self):
        with mock.patch.object(proc.opsdb, "select", return_value=[]):
            self.assertEqual(proc.steps_of("없는공정"), [])


class ProcFmtStep(unittest.TestCase):
    def test_title_only(self):
        self.assertEqual(proc.fmt_step({"no": "1", "title": "자막", "raw": {}}), "[1] 자막")

    def test_all_parts_and_brief(self):
        r = {"no": "2", "title": "조립", "next_action": "build.py 실행", "raw": {"boss": "10글자 이내", "tool": "build.py"}}
        full = proc.fmt_step(r).split("\n")
        self.assertEqual(full, ["[2] 조립", "    할 일: build.py 실행", "    ★ 사장님: 10글자 이내", "    도구: build.py"])
        self.assertNotIn("도구", proc.fmt_step(r, brief=True))

    def test_long_text_is_truncated(self):
        r = {"no": "3", "title": "긴", "next_action": "가" * 400, "raw": {"boss": "나" * 400}}
        out = proc.fmt_step(r)
        self.assertIn("가" * 250, out)
        self.assertNotIn("가" * 251, out)
        self.assertIn("나" * 300, out)
        self.assertNotIn("나" * 301, out)


class TsNum(unittest.TestCase):
    def test_ts(self):
        self.assertEqual(imp.ts("2026-10-05 09:30:00"), "2026-10-05T09:30:00+09:00")
        self.assertEqual(imp.ts("  2026-10-05 09:30:00 "), "2026-10-05T09:30:00+09:00")
        for bad in ("", None, "2026-10-05", "어제", "2026-13-40 00:00:00"):
            with self.subTest(bad=bad):
                self.assertIsNone(imp.ts(bad))

    def test_num_strips_formatting(self):
        self.assertEqual(imp.num("1,234"), 1234.0)
        self.assertEqual(imp.num("50%"), 50.0)
        self.assertEqual(imp.num("12,000원"), 12000.0)
        self.assertEqual(imp.num(" 3.5 "), 3.5)
        self.assertEqual(imp.num("-5"), -5.0)

    def test_num_cast_and_failures(self):
        self.assertEqual(imp.num("1,234", int), 1234)
        self.assertIsNone(imp.num("1.5", int))  # int("1.5")는 실패 -> None
        for bad in ("", None, "abc", "12abc", "%"):
            with self.subTest(bad=bad):
                self.assertIsNone(imp.num(bad))


class Pick(unittest.TestCase):
    def test_first_nonempty_wins(self):
        d = {"a": "", "b": "값", "c": "다른"}
        self.assertEqual(imp.pick(d, "a", "b", "c"), "값")
        self.assertEqual(imp.pick(d, "c", "b"), "다른")

    def test_missing_or_empty_is_none(self):
        self.assertIsNone(imp.pick({"a": ""}, "a", "z"))
        self.assertIsNone(imp.pick({}, "a"))


class ReadCsv(TempDir):
    def test_reads_rows_as_dicts(self):
        p = self.write("a.csv", "time,who\n2026-10-05 09:00:00,핏\n2026-10-05 10:00:00,탐\n")
        rows = imp.read_csv(p)
        self.assertEqual(rows, [{"time": "2026-10-05 09:00:00", "who": "핏"}, {"time": "2026-10-05 10:00:00", "who": "탐"}])

    def test_header_only(self):
        self.assertEqual(imp.read_csv(self.write("b.csv", "time,who\n")), [])


class MdTables(TempDir):
    def test_missing_file(self):
        self.assertEqual(imp.md_tables(self.dir / "없음.md"), [])

    def test_simple_table(self):
        p = self.write("t.md", "# 제목\n\n| 번호 | 안건 |\n|---|---|\n| 1 | 첫째 |\n| 2 | 둘째 |\n\n끝\n")
        (hdr, rows), = imp.md_tables(p)
        self.assertEqual(hdr, ["번호", "안건"])
        self.assertEqual(rows, [{"번호": "1", "안건": "첫째"}, {"번호": "2", "안건": "둘째"}])

    def test_alignment_separators_recognised(self):
        p = self.write("t.md", "|x|y|\n|:--:|:--:|\n|3|4|\n\n| a | b |\n| :--- | ---: |\n| 1 | 2 |\n")
        tables = imp.md_tables(p)
        self.assertEqual(tables[0], (["x", "y"], [{"x": "3", "y": "4"}]))
        self.assertEqual(tables[1], (["a", "b"], [{"a": "1", "b": "2"}]))

    def test_single_dash_separator_is_not_detected(self):
        # 현재 동작 기록: 구분선 칸은 하이픈 2개 이상이어야 한다(GFM은 1개도 허용하지만 이 파서는 `|:-:|`를 구분선으로 보지 않는다)
        self.assertEqual(imp.md_tables(self.write("t.md", "|x|y|\n|:-:|:-:|\n|3|4|\n")), [])

    def test_table_without_leading_pipe_is_not_detected(self):
        # 현재 동작 기록: 헤더 줄이 '|'로 시작하지 않으면(바깥 파이프 없는 GFM 표) 표로 보지 않는다
        self.assertEqual(imp.md_tables(self.write("t.md", "a | b\n--- | ---\n1 | 2\n")), [])

    def test_short_rows_padded_and_long_rows_trimmed(self):
        p = self.write("t.md", "| a | b | c |\n|---|---|---|\n| 1 |\n| 1 | 2 | 3 | 4 |\n")
        (_, rows), = imp.md_tables(p)
        self.assertEqual(rows[0], {"a": "1", "b": "", "c": ""})
        self.assertEqual(rows[1], {"a": "1", "b": "2", "c": "3"})

    def test_pipe_line_without_separator_is_not_a_table(self):
        p = self.write("t.md", "| 그냥 | 줄 |\n| 이어서 | 줄 |\n\n본문\n")
        self.assertEqual(imp.md_tables(p), [])

    def test_two_tables_and_table_at_end_of_file(self):
        p = self.write("t.md", "| a |\n|---|\n| 1 |\n\n문장\n\n| b |\n|---|\n| 2 |")
        tables = imp.md_tables(p)
        self.assertEqual([t[0] for t in tables], [["a"], ["b"]])
        self.assertEqual(tables[1][1], [{"b": "2"}])

    def test_empty_cells_kept(self):
        p = self.write("t.md", "| a | b |\n|---|---|\n|  | x |\n")
        (_, rows), = imp.md_tables(p)
        self.assertEqual(rows, [{"a": "", "b": "x"}])


LEDGER = """# 탐 업무대장

## 진행

### [진행] N151: DB 조회 도구
- 다음: 설계 문서 작성
- 결론: 읽기 전용으로
- 기타 줄

### [완료 10/5] N150: 정리
- [완료 10/5] 증거: 로그 a.txt
- 다음(없음)

### [대기] 번호 없는 제목
본문 한 줄

#### [소제목] 은 새 건이 아니다
- 이어지는 본문

# 다른 큰 제목
- 이 줄은 어느 건에도 속하지 않는다
"""


class ParseTamLedger(TempDir):
    def test_missing_file(self):
        self.assertEqual(imp.parse_tam_ledger(self.dir / "없음.md"), [])

    def test_blocks_status_numbers_and_sections(self):
        out = imp.parse_tam_ledger(self.write("l.md", LEDGER))
        self.assertEqual([(o["no"], o["status"], o["section"]) for o in out],
                         [("N151", "진행", "open"), ("N150", "완료 10/5", "closed"), (None, "대기", "open")])
        self.assertEqual(out[0]["title"], "DB 조회 도구")
        self.assertEqual(out[2]["title"], "번호 없는 제목")
        self.assertTrue(all(o["owner"] == "탐" for o in out))

    def test_bullets_extracted(self):
        a, b, _ = imp.parse_tam_ledger(self.write("l.md", LEDGER))
        self.assertEqual(a["next_action"], "다음: 설계 문서 작성")
        self.assertEqual(a["result"], "결론: 읽기 전용으로")
        self.assertIsNone(a["evidence"])
        self.assertEqual(b["evidence"], "[완료 10/5] 증거: 로그 a.txt")

    def test_body_preserved_and_subheading_stays_in_body(self):
        out = imp.parse_tam_ledger(self.write("l.md", LEDGER))
        self.assertIn("기타 줄", out[0]["raw"]["body"])
        self.assertEqual(out[0]["raw"]["head"], "N151: DB 조회 도구")
        self.assertIn("#### [소제목] 은 새 건이 아니다", out[2]["raw"]["body"])
        self.assertNotIn("어느 건에도", out[2]["raw"]["body"])  # 큰 제목(#) 뒤는 끊김

    def test_fullwidth_colon_and_title_truncation(self):
        p = self.write("l.md", "### [진행] N7：전각 콜론\n- 본문\n### [진행] N8: " + "가" * 400 + "\n")
        a, b = imp.parse_tam_ledger(p)
        self.assertEqual((a["no"], a["title"]), ("N7", "전각 콜론"))
        self.assertEqual(len(b["title"]), 300)

    def test_long_bullet_truncated_to_1500(self):
        p = self.write("l.md", "### [진행] N9: x\n- 다음: " + "나" * 2000 + "\n")
        self.assertEqual(len(imp.parse_tam_ledger(p)[0]["next_action"]), 1500)

    def test_source_is_persona_path(self):
        out = imp.parse_tam_ledger(self.write("l.md", "### [진행] N1: x\n"))
        self.assertEqual(out[0]["source"], imp.PERSONAS["탐"])


PROGRESS = """# 진행상황

## [탐] 상태: 최신
본문 A1
### 하위 제목
본문 A2

## [핏] 상태: 핏 최신
핏 본문

## [탐] 상태: 두번째
본문 B

## 일반 제목(대괄호 없음)
이 줄은 어느 블록에도 속하지 않는다

## [탐] 상태: 세번째
본문 C

## [탐] 상태: 네번째
본문 D
"""


class ParseHandoffs(TempDir):
    def test_missing_file(self):
        self.assertEqual(imp.parse_handoffs(self.dir / "없음.md"), [])

    def test_keeps_latest_n_per_owner_in_file_order(self):
        out = imp.parse_handoffs(self.write("p.md", PROGRESS))
        tam = [o for o in out if o["owner"] == "탐"]
        self.assertEqual([(o["no"], o["title"]) for o in tam], [("1", "상태: 최신"), ("2", "상태: 두번째"), ("3", "상태: 세번째")])  # 네번째는 keep=3 밖
        self.assertEqual([o["owner"] for o in out].count("핏"), 1)

    def test_keep_parameter(self):
        out = imp.parse_handoffs(self.write("p.md", PROGRESS), keep=1)
        self.assertEqual(sorted((o["owner"], o["no"]) for o in out), [("탐", "1"), ("핏", "1")])

    def test_body_includes_subheadings_but_not_plain_h2(self):
        out = imp.parse_handoffs(self.write("p.md", PROGRESS))
        first = out[0]["raw"]["body"]
        self.assertIn("본문 A1", first)
        self.assertIn("### 하위 제목", first)
        self.assertIn("본문 A2", first)
        third = [o for o in out if o["raw"]["head"] == "상태: 두번째"][0]["raw"]["body"]
        self.assertEqual(third, "본문 B")  # 일반 ## 제목에서 끊김

    def test_owner_override_and_source(self):
        text = "## [핏(로컬)] 상태: a\nx\n## [핏(로컬)] 상태: b\ny\n"
        out = imp.parse_handoffs(self.write("k.md", text), owner_override="핏", source="shorts-lab 파일")
        self.assertEqual([(o["owner"], o["no"], o["source"]) for o in out], [("핏", "1", "shorts-lab 파일"), ("핏", "2", "shorts-lab 파일")])

    def test_default_source_and_row_shape(self):
        out = imp.parse_handoffs(self.write("p.md", "## [마야] 상태: x\n본문\n"))
        r = out[0]
        self.assertEqual((r["section"], r["source"], r["status"]), ("handoff", "docs/진행상황.md", "상태: x"))
        self.assertIsNone(r["next_action"])

    def test_status_cut_to_40_and_title_to_300(self):
        out = imp.parse_handoffs(self.write("p.md", "## [탐] " + "가" * 500 + "\n"))
        self.assertEqual((len(out[0]["status"]), len(out[0]["title"])), (40, 300))


if __name__ == "__main__":
    unittest.main()
