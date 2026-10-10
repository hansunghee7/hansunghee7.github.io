"""delegation-gate.py 시험: 가짜 전사 JSONL로 임계·위임 리셋·1회 경고·fail-open을 확인한다."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GATE = str(Path(__file__).parent / "delegation-gate.py")


def use(i, name="Bash", **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": f"t{i}", "name": name, "input": inp}]}}


def res(i, text="ok"):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": text}]}}


class GateTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.state = os.path.join(self.d, "state.json")

    def transcript(self, events, raw=None):
        p = os.path.join(self.d, "t.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(raw if raw is not None else "\n".join(json.dumps(e) for e in events) + "\n")
        return p

    def run_gate(self, path, mode="warn", sid="s1", **env):
        e = dict(os.environ, DELEGATION_STATE_PATH=self.state, DELEGATION_GATE_MODE=mode)
        e.pop("DELEGATION_GATE_PERSONAS", None)
        e.update(env)
        inp = json.dumps({"transcript_path": path, "session_id": sid})
        return subprocess.run([sys.executable, GATE], input=inp, capture_output=True, text=True, encoding="utf-8", env=e)

    def calls(self, n, start=0):
        ev = []
        for i in range(start, start + n):
            ev += [use(i, command=f"echo {i}"), res(i)]
        return ev

    def test_1_calls_over_threshold(self):
        p = self.transcript(self.calls(120))
        r = self.run_gate(p, "warn")
        self.assertEqual(r.returncode, 0)
        self.assertIn("직접 손일이 120회", r.stderr)
        os.remove(self.state)
        r = self.run_gate(p, "block")
        self.assertEqual(r.returncode, 2)
        self.assertIn("위임 기록", r.stderr)

    def test_2_agent_in_middle_resets(self):
        ev = self.calls(60) + [use(900, "Agent", prompt="x"), res(900)] + self.calls(50, 100)
        r = self.run_gate(self.transcript(ev), "block")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stderr, "")

    def test_3_chars_threshold(self):
        ev = []
        for i in range(30):
            ev += [use(i, command="cat big"), res(i, "가" * 7000)]
        r = self.run_gate(self.transcript(ev), "block")
        self.assertEqual(r.returncode, 2)

    def test_4_second_call_same_segment_silent(self):
        p = self.transcript(self.calls(120))
        self.assertEqual(self.run_gate(p, "block").returncode, 2)
        r = self.run_gate(p, "block")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        # 위임 뒤 새 구간에서 다시 임계를 넘으면 다시 경고
        ev = self.calls(120) + [use(901, "Monitor", command="x")] + self.calls(120, 200)
        self.assertEqual(self.run_gate(self.transcript(ev), "block").returncode, 2)

    def test_5_missing_or_broken_passes(self):
        self.assertEqual(self.run_gate(os.path.join(self.d, "nope.jsonl"), "block").returncode, 0)
        self.assertEqual(self.run_gate(self.transcript(None, raw="{깨짐\nnot json\n"), "block").returncode, 0)
        r = subprocess.run([sys.executable, GATE], input="not json", capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)

    def test_6_below_threshold_passes(self):
        r = self.run_gate(self.transcript(self.calls(99)), "block")
        self.assertEqual(r.returncode, 0)

    def test_7_background_bash_and_env_override(self):
        ev = self.calls(60) + [use(950, command="x", run_in_background=True)] + self.calls(60, 100)
        self.assertEqual(self.run_gate(self.transcript(ev), "block").returncode, 0)
        r = self.run_gate(self.transcript(self.calls(10)), "block", DELEGATION_CALLS="5")
        self.assertEqual(r.returncode, 2)

    def test_9_extended_delegation_commands(self):
        for cmd in ("python scripts/ops/ask_vertex.py q", "python vertex_research.py x", "python gemini_route.py x",
                    "python api_run.py x", "python credit_run.py x", "python orch_wait.py x",
                    "claude -p 'hi'", "python session_brief.py --cloud"):
            ev = self.calls(60) + [use(950, command=cmd)] + self.calls(60, 100)
            r = self.run_gate(self.transcript(ev), "block")
            self.assertEqual(r.returncode, 0, cmd)
            if os.path.exists(self.state):
                os.remove(self.state)

    def test_8_persona_scope(self):
        p = self.transcript(self.calls(120))
        r = self.run_gate(p, "block", DELEGATION_GATE_PERSONAS="zzzz-nomatch")
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
