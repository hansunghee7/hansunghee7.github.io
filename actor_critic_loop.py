"""Actor-Critic 무한 훈육 루프.

Actor(헤르메스, hx.sh ask)가 린트 에러를 고치고, Critic(ruff 종료코드)이 채점한다.
합격(종료코드 0)하면 종료, 불합격이면 오답 노트를 붙여 재시도, MAX_RETRIES 초과 시 에스컬레이션한다.
종료 시 지표 3개(Iterations / Status / Escalate)를 반드시 출력한다.

안전장치: 헤르메스 응답은 파일에 바로 쓰지 않는다.
  ① 코드 펜스(```python ... ```) 사이만 추출(펜스가 없으면 응답 전체를 후보로) → ② ast.parse 통과 시에만 덮어쓰기.
  실패로 끝나면 원본을 복원한다(로컬 LLM 사족으로 파일이 깨지는 것 방지).

사용: python actor_critic_loop.py <대상.py>
"""
import ast
import io
import os
import re
import shutil
import subprocess
import sys
import tokenize

MAX_RETRIES = 3
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
HX = os.path.join(ROOT, "scripts", "hx.sh").replace("\\", "/")  # bash는 역슬래시를 이스케이프로 먹는다
REVIEWER = os.path.join(ROOT, ".hermes", "roles", "reviewer.md")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows 팝업 금지(CLAUDE.md)
# PATH의 bash는 WSL(System32)일 수 있어 Git Bash를 우선 쓴다
BASH = next((b for b in ("C:/Program Files/Git/bin/bash.exe",) if os.path.exists(b)), "bash")
FENCE = re.compile(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", re.DOTALL)

# 에스컬레이션 페일오버 순서(AI_ROUTING_POLICY): 솔라 프로 -> 제미나이 -> 네모트론 -> Qwen
FAILOVER = ["solar-pro", "gemini", "nemotron", "qwen"]


def run(cmd: list[str], stdin: str | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, creationflags=NOWIN, check=False)


def fingerprint(src: str) -> tuple:
    """포맷 전용 모드의 불변량: AST(로직·docstring)와 주석 목록(shebang 포함)이 같아야 한다."""
    comments = tuple(t.string.strip() for t in tokenize.generate_tokens(io.StringIO(src).readline)
                     if t.type == tokenize.COMMENT)
    return ast.dump(ast.parse(src)), comments


def extract_code(reply: str, ref: str | None = None) -> str | None:
    """헤르메스 응답에서 순수 코드만 뽑는다. 문법이 안 맞거나 ref(원본)와 로직·주석이 다르면 None(파일을 건드리지 않는다).
    ref를 주면 '문법 정상 + 원본과 동일 지문'인 마지막 블록만 채택한다(실측: 도구 차단 후에도 헤르메스가 docstring·shebang을
    조용히 지운 채 ruff를 통과시킨 사례가 있었다, 2026-09-30)."""
    # 펜스 블록 전부 수집 후 뒤에서부터 시도해 문법이 맞는 '마지막 블록'을 채택한다(펜스가 없으면 응답 전체가 후보).
    # '가장 긴 블록'은 실측에서 실패: 문제 예시 블록에 주석 해설이 붙어 수정본보다 길어졌다(2026-09-30 스트레스 테스트 2).
    blocks = FENCE.findall(reply) or [re.sub(r"(?m)^(session_id: |Warning: Unknown toolsets).*\n?", "", reply)]  # hermes CLI 노이즈 줄 제거
    for block in reversed(blocks):
        code = block.strip("\n") + "\n"
        try:
            ast.parse(code)
        except SyntaxError:
            continue
        if ref is not None and fingerprint(code) != fingerprint(ref):
            continue
        return code
    return None


def critic(path: str) -> tuple[bool, str]:
    """ruff 두 관문(format, check)의 종료코드로 채점. 실패 시 출력 전체가 오답 노트."""
    logs = []
    for args in (["format", "--check", "--diff"], ["check"]):
        r = run([sys.executable, "-m", "ruff", *args, path])
        if r.returncode != 0:
            logs.append(f"$ ruff {' '.join(args)}\n{r.stdout}{r.stderr}")
    return (not logs), "\n".join(logs)


def actor(path: str, feedback: str) -> tuple[bool, str]:
    """헤르메스에게 가드레일+린트 로그+소스를 넘기고, 걸러낸 코드만 파일에 쓴다."""
    with open(REVIEWER, encoding="utf-8") as f:
        guard = f.read()
    with open(path, encoding="utf-8") as f:
        src = f.read()
    prompt = f"{guard}\n\n## 린트 에러 로그\n{feedback}\n\n## 소스 코드\n{src}"
    r = run([BASH, HX, "ask-pure"], stdin=prompt)  # 도구 차단 모드: 기본 ask는 헤르메스가 파일을 직접 고쳐 파서를 우회한다
    if r.returncode != 0:
        return False, f"헤르메스 호출 실패(exit {r.returncode}): {r.stderr.strip()[:300]}"
    if os.environ.get("ACL_DUMP"):  # 디버그: 헤르메스 원문 응답 보관(스트레스 테스트용)
        with open(os.environ["ACL_DUMP"], "a", encoding="utf-8") as f:
            f.write(r.stdout + "\n=====\n")
    code = extract_code(r.stdout, ref=src)
    if code is None:
        return False, ("헤르메스 응답에서 문법이 맞고 원본과 로직·주석(docstring, shebang 포함)이 같은 코드를 추출하지 못함"
                       "(파일은 그대로 둠). 코드 전체를 빠짐없이 다시 출력할 것")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    return True, ""


def escalate(path: str, last_log: str) -> None:
    """연결점(더미): 3회 실패 시 FAILOVER 순서의 상위 모델/대법관 API로 분석을 이관한다. TODO: 실제 호출 연결."""
    print(f"[escalate] {path} -> 분석 이관 대상 순서: {' > '.join(FAILOVER)} (더미, 미연결)")
    print(f"[escalate] 마지막 오답 노트:\n{last_log[:500]}")


def run_loop(path: str) -> dict:
    backup = path + ".orig"
    shutil.copyfile(path, backup)
    iterations, passed, feedback = 0, False, ""
    try:
        passed, feedback = critic(path)  # 처음부터 합격이면 Actor 호출 없이 0회로 끝
        while not passed and iterations < MAX_RETRIES:
            iterations += 1
            ok, note = actor(path, feedback)
            if not ok:
                feedback = f"{feedback}\n\n[직전 시도 실패] {note}"  # 린트 로그를 잃지 않고 덧붙인다
                continue
            passed, feedback = critic(path)
    finally:
        if not passed:
            shutil.copyfile(backup, path)  # 실패 시 원본 복원
        os.remove(backup)
        result = {
            "Iterations": iterations,
            "Status": "PASS" if passed else "FAIL",
            "Escalate": (not passed) and iterations >= MAX_RETRIES,
        }
        for k, v in result.items():
            print(f"[metric] {k}: {v}")
    if result["Escalate"]:
        escalate(path, feedback)
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("사용: python actor_critic_loop.py <대상.py>")
    sys.exit(0 if run_loop(sys.argv[1])["Status"] == "PASS" else 1)
