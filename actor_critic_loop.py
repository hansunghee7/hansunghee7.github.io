"""Actor-Critic 무한 훈육 루프 뼈대.

Actor(헤르메스)가 작업하고 Critic(통제자)이 검증한다. 합격하면 종료,
불합격이면 피드백을 붙여 재시도하며 MAX_RETRIES를 넘으면 에스컬레이션한다.
종료 시 측정 지표 3개(Iterations / Status / Escalate)를 반드시 출력한다.
"""
import sys

MAX_RETRIES = 3


def actor(task: str, feedback: str | None) -> str:
    """헤르메스가 작업을 수행한다. TODO: hx.sh 호출로 교체."""
    raise NotImplementedError("Actor(헤르메스) 호출 연결 필요")


def critic(task: str, output: str) -> tuple[bool, str]:
    """통제자가 결과를 검증한다. (합격 여부, 피드백)을 돌려준다.
    TODO: .hermes/roles/reviewer.md 기준으로 검증 연결."""
    raise NotImplementedError("Critic 검증 연결 필요")


def run_loop(task: str) -> dict:
    iterations, passed, feedback = 0, False, None
    try:
        while iterations < MAX_RETRIES and not passed:
            iterations += 1
            output = actor(task, feedback)
            passed, feedback = critic(task, output)
    finally:
        # 예외로 끝나도 지표는 반드시 남긴다 (미완료는 FAIL로 기록)
        result = {
            "Iterations": iterations,
            "Status": "PASS" if passed else "FAIL",
            "Escalate": (not passed) and iterations >= MAX_RETRIES,
        }
        for k, v in result.items():
            print(f"[metric] {k}: {v}")
    return result


if __name__ == "__main__":
    run_loop(" ".join(sys.argv[1:]) or "sample task")
