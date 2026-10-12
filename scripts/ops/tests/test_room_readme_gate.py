"""room_readme_gate.py 시험. 가짜 입력만 쓰고 외부 호출 없음. 실행: python -m unittest scripts/ops/tests/test_room_readme_gate.py"""
import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

OPS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("room_readme_gate_under_test", OPS / "room_readme_gate.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

GOOD = """# 교신방 안내

## 하실 일
약 5분, 3단계입니다.
1. 저장소 초대를 수락합니다.
2. 아래 문장을 에이전트에게 붙여 넣습니다.
3. 승인 전에는 아무것도 안 올라갑니다.

```
이 저장소 README를 읽고 교신을 시작해 주세요.
```
"""
BAD = "# 교신방 안내\n\n에이전트용 규약만 있음.\n" + "\n".join(["줄"] * 50) + "\n## 하실 일\n5분 1. 붙여넣기\n```\nx\n```\n"


def run(text):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "README.md"
        p.write_text(text, encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = g.main(["x", str(p)])
    return code, out.getvalue()


class Gate(unittest.TestCase):
    def test_pass(self):
        code, out = run(GOOD)
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("통과"))

    def test_fail_heading_beyond_40_lines(self):
        code, out = run(BAD)
        self.assertEqual(code, 2)
        self.assertTrue(out.startswith("실패"))

    def test_fail_no_code_block(self):
        code, out = run(GOOD.split("```")[0])
        self.assertEqual(code, 2)
        self.assertIn("코드 블록", out)

    def test_missing_file(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(g.main(["x", "/nonexistent/README.md"]), 2)


if __name__ == "__main__":
    unittest.main()
