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

    def test_proposal_needs_record_lookup(self):
        # 2026-10-20 사장님 지시: 제안·추천·"정하실 것: (없음 아님)"은 같은 턴 기록 검색 필수
        self.assertEqual(sg.check("정하실 것: A안으로 갈지 정해 주세요.", OTHER, False), "propose-without-record-lookup")
        self.assertEqual(sg.check("제 추천은 B안입니다.", [], False), "propose-without-record-lookup")
        self.assertEqual(sg.check("이렇게 제안합니다.", OTHER, False), "propose-without-record-lookup")
        rec = [("Bash", {"command": "python scripts/ops/recall.py 로그인 방식"})]
        self.assertIsNone(sg.check("정하실 것: A안으로 갈지 정해 주세요.", rec, False))
        self.assertIsNone(sg.check("제 추천은 B안입니다.", [("Bash", {"command": "python scripts/ops/proc.py list"})], False))
        # 10/20 리뷰 반영: 띄어쓰기·변형 표현도 잡는다
        for t in ("이렇게 제안 합니다.", "B안을 추천드립니다.", "이 방식을 권장합니다.", "한도 유지를 제안드립니다.", "그렇게 제의합니다."):
            self.assertEqual(sg.check(t, OTHER, False), "propose-without-record-lookup", t)
        # 정하실 것: 없음, 제안이 아닌 보고, 코드 안 문구는 통과
        self.assertIsNone(sg.check("정하실 것: 없음.", OTHER, False))
        self.assertIsNone(sg.check("정하실 것: 없음", [], False))
        self.assertIsNone(sg.check("배포를 마쳤습니다.", OTHER, False))
        self.assertIsNone(sg.check("코드 `제 추천은` 문자열만 보입니다.", OTHER, False))

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
        self.assertEqual(sg.check("비티는 지금 쓸 수 없습니다.", OTHER, False), "bt-claim-without-vertex-check")
        # 파일 이름만 언급한 명령(ls)은 증거가 아니다(덱스 리뷰 10/19)
        self.assertEqual(sg.check("비티 막힘입니다.", [("Bash", {"command": "ls C:/work/_ops/agent_calls.csv.bak"})], False), "bt-claim-without-vertex-check")
        self.assertIsNone(sg.check("비티 막힘입니다.", [("Read", {"file_path": "C:/work/_ops/agent_calls.csv"})], False))
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
