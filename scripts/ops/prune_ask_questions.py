"""추천 질문 풀(ask-questions.json)을 다이얼로그 질의 경로로 한 번씩 질의해 거절된 질문을 제거한다.

호출은 scripts/ask_dialog.py의 ask()를 그대로 쓴다(키는 코드가 ask.html에서 읽고 출력하지 않음).
한도 분당 3회라 호출 사이 21초 이상 간격. 429(한도)가 나오면 즉시 멈추고 PROGRESS에 남긴다.
재개 가능: 결과는 STATE 파일에 질문마다 저장하고, 이미 판정된 질문은 건너뛴다.
"""
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import ask_dialog  # noqa: E402

POOL = REPO / "insight-7b3e9f2c" / "ask-questions.json"
STATE = Path("C:/work/_ops/burn_1020/prune_state.json")
PROGRESS = Path("C:/work/_ops/burn_1020/PROGRESS_G.md")
GAP = 21.5


def note(msg):
    with PROGRESS.open("a", encoding="utf-8") as f:
        f.write("- " + msg + "\n")


def main():
    data = json.loads(POOL.read_text(encoding="utf-8"))
    qs = data["questions"]
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    for i, q in enumerate(qs):
        if q in state:
            continue
        out = ask_dialog.ask(q)
        code = ask_dialog.classify(out)
        if code == ask_dialog.EXIT_LIMIT:
            note("질의 중 429/한도 -> 중단 (판정 %d/%d). 재실행하면 이어서 진행" % (len(state), len(qs)))
            return 3
        if code != ask_dialog.EXIT_OK:
            state[q] = {"verdict": "error", "code": code, "err": (out.get("error") or "")[:120]}
        else:
            refused = "답할 수 없" in out["text"]
            state[q] = {"verdict": "refused" if refused else "ok"}
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        if i % 10 == 0:
            note("진행 %d/%d (거절 %d, 오류 %d)" % (len(state), len(qs),
                 sum(v["verdict"] == "refused" for v in state.values()),
                 sum(v["verdict"] == "error" for v in state.values())))
        time.sleep(GAP)
    refused = [q for q in qs if state.get(q, {}).get("verdict") == "refused"]
    errors = [q for q in qs if state.get(q, {}).get("verdict") == "error"]
    data["questions"] = [q for q in qs if q not in refused]
    data["updated"] = time.strftime("%Y-%m-%d")
    POOL.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    note("완료: 제거 %d개, 오류(유지) %d개, 남은 %d개" % (len(refused), len(errors), len(data["questions"])))
    note("제거 목록: " + " | ".join(refused))
    return 0


if __name__ == "__main__":
    sys.exit(main())
