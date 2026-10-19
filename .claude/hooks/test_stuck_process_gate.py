"""stuck-process-gate.py 시험: 막혔다는 답변은 절차 기록을 열어 봤을 때만 통과한다."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("sg", Path(__file__).parent / "stuck-process-gate.py")
sg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sg)

READ = [("Read", {"file_path": "C:/work/hansunghee7.github.io/docs/핏_프로세스표.md"})]
OTHER = [("Bash", {"command": "ls /tmp"})]


class StuckGateTest(unittest.TestCase):
    def test_stuck_without_lookup_is_blocked(self):
        self.assertEqual(sg.check("Vids 내려받기가 안 됩니다.", OTHER), "no-process-lookup")
        self.assertEqual(sg.check("다운로드에서 막혔습니다.", []), "no-process-lookup")

    def test_stuck_with_process_lookup_passes(self):
        self.assertIsNone(sg.check("Vids 내려받기가 안 됩니다.", READ))
        self.assertIsNone(sg.check("막혔습니다.", [("Grep", {"pattern": "삽입", "path": "GENERATION_PIPELINES.md"})]))

    def test_money_talk_needs_record_lookup(self):
        # 2026-10-16 사장님 승인(카드 탐#106): 돈 이야기는 같은 턴 기록 검색 필수
        self.assertEqual(sg.check("Actions 상한을 20달러로 올리세요.", OTHER, False), "money-without-record-lookup")
        self.assertEqual(sg.check("월 $5 결제가 필요합니다.", [], False), "money-without-record-lookup")
        self.assertIsNone(sg.check("Actions 상한을 20달러로 올리세요.", [("Bash", {"command": "python scripts/ops/recall.py 예산"})], False))
        self.assertIsNone(sg.check("배포를 마쳤습니다.", OTHER, False))
        self.assertIsNone(sg.check("코드 `budget = 상한` 만 보입니다.", OTHER, False))

    def test_negated_or_clean_text_passes(self):
        self.assertIsNone(sg.check("막힘 없이 통과했습니다.", []))
        self.assertIsNone(sg.check("결과를 기록했습니다.", []))

    def test_error_gating(self):
        T = "Vids 내려받기가 안 됩니다."
        self.assertEqual(sg.check(T, OTHER, True), "no-process-lookup")  # 막힘+오류+열람 없음
        self.assertIsNone(sg.check(T, OTHER, False))  # 오류 없음
        self.assertIsNone(sg.check(T, READ, True))  # 열람 있음
        self.assertIsNone(sg.check("결과를 기록했습니다.", OTHER, True))  # 막힘 표현 없음

    def _run(self, events, raw=None):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "t.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(raw if raw is not None else chr(10).join(json.dumps(e) for e in events) + chr(10))
        self.logpath = os.path.join(d, "gate_log.jsonl")
        r = subprocess.run([sys.executable, str(Path(__file__).parent / "stuck-process-gate.py")],
                           input=json.dumps({"transcript_path": p}), capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "STUCK_GATE_LOG": self.logpath})
        return r.returncode

    def test_bt_claim_needs_vertex_check(self):
        # 2026-10-19 노트 요청(cxo-db #490): 비티 없음·막힘 보고는 같은 턴 Vertex 경로 확인 흔적 필요
        for t in ("비티는 지금 한도로 막혀 있습니다.", "비티 없음, 소넷으로 대신합니다.", "비티 막힘 때문에 보류합니다."):
            self.assertEqual(sg.check(t, OTHER, False), "bt-claim-without-vertex-check", t)
        V = [("Bash", {"command": "BT_MODEL=vertex bash scripts/ops/ask_bt.sh q.md out.md"})]
        C = [("Bash", {"command": "tail -3 C:/work/_ops/agent_calls.csv"})]
        self.assertIsNone(sg.check("비티는 지금 한도로 막혀 있습니다.", V, False))
        self.assertIsNone(sg.check("비티 막힘 때문에 보류합니다.", C, False))
        self.assertIsNone(sg.check("비티(GCP 풀)로 답을 받았습니다.", OTHER, False))
        self.assertIsNone(sg.check("비티는 막히지 않았습니다.", OTHER, False))

    def test_firing_is_logged_without_text(self):
        u = {"type": "user", "message": {"content": [{"type": "text", "text": "해줘"}]}}
        fin = {"type": "assistant", "message": {"content": [{"type": "text", "text": "월 $5 결제가 필요합니다."}]}}
        self.assertEqual(self._run([u, fin]), 2)
        rec = json.loads(open(self.logpath, encoding="utf-8").read().splitlines()[0])
        self.assertEqual(rec["verdict"], "money-without-record-lookup")
        self.assertNotIn("결제", json.dumps(rec, ensure_ascii=False))

    def test_transcript_end_to_end(self):
        u = {"type": "user", "message": {"content": [{"type": "text", "text": "해줘"}]}}
        a = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "1", "name": "Bash", "input": {"command": "ls"}}]}}
        fin = {"type": "assistant", "message": {"content": [{"type": "text", "text": "내려받기가 안 됩니다."}]}}
        bad = {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "1", "is_error": True, "content": "Exit code 1 boom"}]}}
        ok = {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "1", "content": "fine"}]}}
        self.assertEqual(self._run([u, a, bad, fin]), 2)
        self.assertEqual(self._run([u, a, ok, fin]), 0)
        self.assertEqual(self._run([], raw="not json at all {broken"), 0)  # 파싱 실패는 통과


if __name__ == "__main__":
    unittest.main()
