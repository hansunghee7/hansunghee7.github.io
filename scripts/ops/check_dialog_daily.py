"""다이얼로그 실사용 합성 점검(B41, 2026-10-02 탐).

고객이 쓰는 경로와 같게 질문 하나를 실제로 보내고, 답 글자와 근거 글이 돌아오는지 본다.
워커 무료 한도 때문에 하루 1회만 돈다(감시 대장 fn:dialog-worker는 405 응답만 본다).
성공: exit 0, 실패: exit 1(무엇이 비었는지 한 줄 출력). 답 본문은 출력하지 않는다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ask_dialog import ask  # noqa: E402

QUESTION = "1인 회사에서 AI 에이전트에게 일을 맡길 때 가장 먼저 정해야 할 것은 무엇인가요?"
MIN_TEXT = 80


def main():
    out = ask(QUESTION)
    n_text, n_src = len(out["text"]), len(out["sources"])
    top = max((s.get("similarity", 0) for s in out["sources"]), default=0)
    print(f"text={n_text}자 sources={n_src} top_similarity={top:.2f} error={out['error']}")
    if out["error"] or n_text < MIN_TEXT or n_src == 0:
        print("FAIL: 답이 비었거나 근거 글이 없음")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
