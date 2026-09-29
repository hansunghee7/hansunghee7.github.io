"""Actor-Critic 무한 훈육 루프.

Actor(헤르메스, hx.sh ask-pure)가 린트 에러를 고치고, Critic(ruff 종료코드)이 채점한다.
합격(종료코드 0)하면 종료, 불합격이면 오답 노트를 붙여 재시도, MAX_RETRIES 초과 시 에스컬레이션한다.
종료 시 지표 3개(Iterations / Status / Escalate)를 반드시 출력한다.

모드(--mode):
  format: 포맷 전용. ruff format + ruff check 둘 다 0이어야 하고, 수정본은 원본과 AST·주석이 100% 같아야 한다.
  logic : 논리 린트 수정(미사용 import·변수 등). ruff check 0이 PASS 기준이고 AST 변경을 허용한다.
          대신 문법(ast.parse)과 최상위 def/class 이름 보존만 검사한다(코드가 통째로 날아가는 것 방지).

안전장치: 헤르메스 응답은 파일에 바로 쓰지 않는다.
  ① 코드 펜스 사이만 추출(마지막 정상 블록, 펜스가 없으면 응답 전체) → ② ast.parse 통과 → ③ 모드별 불변량 검사 후에만 덮어쓰기.
  실패로 끝나면 원본을 복원한다. 헤르메스는 도구 없는 순수 텍스트 모드(ask-pure)로만 부른다.

훈련 데이터: PASS한 회차의 (오류 로그+원본 코드, 순수 수정 코드)를 .hermes/data/lora_raw/<mode>.jsonl에 추가한다.
  .hermes/data/는 .gitignore 대상이다(공개 저장소 유출 금지).

사용: python actor_critic_loop.py [--mode format|logic] <대상.py>
"""
import argparse
import ast
import io
import json
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
DATA_DIR = os.path.join(ROOT, ".hermes", "data", "lora_raw")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows 팝업 금지(CLAUDE.md)
# PATH의 bash는 WSL(System32)일 수 있어 Git Bash를 우선 쓴다
BASH = next((b for b in ("C:/Program Files/Git/bin/bash.exe",) if os.path.exists(b)), "bash")
FENCE = re.compile(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", re.DOTALL)
NOISE = re.compile(r"(?m)^(session_id: |Warning: Unknown toolsets).*\n?")  # hermes CLI 노이즈 줄
MODES = ("format", "logic")
LOGIC_NOTE = (
    "## 이번 모드: 논리 린트 수정(줄 번호 삭제 방식)\n"
    "코드를 다시 쓰지 마라. 위 린트 오류를 해결하려면 삭제해야 하는 원본 코드의 줄 번호만 JSON 배열로 출력하라. "
    "예: [12, 14]. 배열 외에는 아무것도 출력하지 마라. 줄 번호는 아래 '소스 코드'의 왼쪽 번호를 그대로 쓴다."
)
JSON_ARRAY = re.compile(r"\[[\d,\s]*\]")
# 삭제를 허용하는 줄: 미사용 import(F401)·미사용 변수(F841)로 지적된 줄만. F821(미정의) 등의 줄은 대상 아님
# (실측: 다중 이름 import 줄을 통째로 지운 뒤 생긴 F821 사용 줄 11개를 헤르메스가 연쇄로 지우려 했다).
FLAGGED = re.compile(r"(?m)^F(?:401|841)\b[^\n]*\n\s*-->\s.*?:(\d+):\d+")

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


def top_names(src: str) -> set[str]:
    """최상위 함수·클래스 이름(논리 모드에서 코드가 통째로 사라지지 않았는지 보는 최소 불변량)."""
    return {n.name for n in ast.parse(src).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def acceptable(code: str, ref: str, mode: str) -> bool:
    """모드별로 후보 코드를 파일에 써도 되는지 판정한다(code는 이미 문법 검사를 통과한 상태)."""
    if mode == "format":
        return fingerprint(code) == fingerprint(ref)
    return top_names(code) >= top_names(ref)


def extract_code(reply: str, ref: str | None = None, mode: str = "format") -> str | None:
    """헤르메스 응답에서 순수 코드만 뽑는다. 문법이 안 맞거나 ref(원본) 대비 모드별 불변량을 어기면 None(파일을 건드리지 않는다).
    펜스 블록 전부를 모아 뒤에서부터 '문법 정상 + 불변량 통과'인 첫 블록을 채택한다.
    실측: '가장 긴 블록'은 주석 많은 예시 블록에 져서 실패, 도구 차단 후에도 docstring·shebang을 지운 응답이 ruff를 통과했다."""
    blocks = FENCE.findall(reply) or [NOISE.sub("", reply)]
    for block in reversed(blocks):
        code = block.strip("\n") + "\n"
        try:
            ast.parse(code)
        except SyntaxError:
            continue
        if ref is not None and not acceptable(code, ref, mode):
            continue
        return code
    return None


def critic(path: str, mode: str = "format", select: str | None = None) -> tuple[bool, str]:
    """ruff 종료코드로 채점. format 모드는 format+check, logic 모드는 check만. 실패 시 출력 전체가 오답 노트.
    select: logic 모드에서 검사할 규칙군(기본 F=pyflakes: 미사용·미정의). 기본 규칙 전체는 스타일 오류가 많아 삭제로는 못 풀린다."""
    check = ["check"] + (["--select", select] if select else [])
    gates = (["format", "--check", "--diff"], check) if mode == "format" else (check,)
    logs = []
    for args in gates:
        r = run([sys.executable, "-m", "ruff", *args, path])
        if r.returncode != 0:
            logs.append(f"$ ruff {' '.join(args)}\n{r.stdout}{r.stderr}")
    return (not logs), "\n".join(logs)


def log_sample(mode: str, prompt: str, completion: str) -> None:
    """검증(PASS)된 회차만 JSONL로 추가한다. 실패 회차는 정답이 아니므로 학습 데이터에 넣지 않는다."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, f"{mode}.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"prompt": prompt, "completion": completion}, ensure_ascii=False) + "\n")


def delete_lines(src: str, reply: str, feedback: str) -> tuple[str | None, str]:
    """logic 모드: 헤르메스가 답한 줄 번호 배열을 읽어 해당 줄을 지운다. (새 소스 또는 None, 실패 사유).
    ① 응답의 마지막 JSON 배열만 읽고 ② 번호는 린트가 지적한 줄에 속해야 하며 ③ 큰 번호부터(역순) 지워 번호가 밀리지 않게 한다."""
    arrays = JSON_ARRAY.findall(NOISE.sub("", reply))
    if not arrays:
        return None, "응답에서 줄 번호 JSON 배열을 찾지 못함. [12, 14] 형태의 배열만 출력할 것"
    nums = json.loads(arrays[-1])
    lines = src.splitlines(keepends=True)
    flagged = {int(n) for n in FLAGGED.findall(feedback)}
    if not nums or len(set(nums)) != len(nums) or any(n < 1 or n > len(lines) for n in nums):
        return None, f"줄 번호가 비었거나 중복·범위 밖: {nums}"
    if not set(nums) <= flagged:
        return None, f"린트가 지적하지 않은 줄({sorted(set(nums) - flagged)})은 지울 수 없음. 지적된 줄: {sorted(flagged)}"
    for n in sorted(nums, reverse=True):
        del lines[n - 1]
    return "".join(lines), ""


def actor(path: str, feedback: str, mode: str = "format") -> tuple[bool, str, tuple[str, str] | None]:
    """헤르메스에게 가드레일+린트 로그+소스를 넘기고, 걸러낸 결과만 파일에 쓴다. (성공 여부, 실패 사유, (프롬프트, 응답))."""
    with open(REVIEWER, encoding="utf-8") as f:
        guard = f.read()
    with open(path, encoding="utf-8") as f:
        src = f.read()
    shown = "".join(f"{i:>4}| {ln}" for i, ln in enumerate(src.splitlines(keepends=True), 1)) if mode == "logic" else src
    sample_prompt = f"## 린트 에러 로그\n{feedback}\n\n## 소스 코드\n{shown}"
    mode_note = f"\n\n{LOGIC_NOTE}" if mode == "logic" else ""
    r = run([BASH, HX, "ask-pure"], stdin=f"{guard}{mode_note}\n\n{sample_prompt}")  # 도구 차단: 기본 ask는 파일을 직접 고쳐 파서를 우회한다
    if r.returncode != 0:
        return False, f"헤르메스 호출 실패(exit {r.returncode}): {r.stderr.strip()[:300]}", None
    if os.environ.get("ACL_DUMP"):  # 디버그: 헤르메스 원문 응답 보관(스트레스 테스트용)
        with open(os.environ["ACL_DUMP"], "a", encoding="utf-8") as f:
            f.write(r.stdout + "\n=====\n")
    if mode == "logic":
        code, why = delete_lines(src, r.stdout, feedback)
        try:
            if code is not None:
                ast.parse(code)
                if not top_names(code) >= top_names(src):
                    code, why = None, "삭제 결과 최상위 함수·클래스가 사라짐"
        except SyntaxError:
            code, why = None, "삭제 결과 문법이 깨짐"
        if code is None:
            return False, why, None
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(code)
        return True, "", (sample_prompt, JSON_ARRAY.findall(NOISE.sub("", r.stdout))[-1])
    code = extract_code(r.stdout, ref=src, mode=mode)
    if code is None:
        need = "원본과 로직·주석(docstring, shebang 포함)이 같은" if mode == "format" else "원본의 함수·클래스를 모두 유지한"
        return False, f"헤르메스 응답에서 문법이 맞고 {need} 코드를 추출하지 못함(파일은 그대로 둠). 코드 전체를 빠짐없이 다시 출력할 것", None
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    return True, "", (sample_prompt, code)


def escalate(path: str, last_log: str) -> None:
    """연결점(더미): 3회 실패 시 FAILOVER 순서의 상위 모델/대법관 API로 분석을 이관한다. TODO: 실제 호출 연결."""
    print(f"[escalate] {path} -> 분석 이관 대상 순서: {' > '.join(FAILOVER)} (더미, 미연결)")
    print(f"[escalate] 마지막 오답 노트:\n{last_log[:500]}")


def run_loop(path: str, mode: str = "format", select: str | None = None) -> dict:
    backup = path + ".orig"
    shutil.copyfile(path, backup)
    iterations, passed, feedback = 0, False, ""
    select = select or ("F" if mode == "logic" else None)
    try:
        passed, feedback = critic(path, mode, select)  # 처음부터 합격이면 Actor 호출 없이 0회로 끝
        while not passed and iterations < MAX_RETRIES:
            iterations += 1
            ok, note, sample = actor(path, feedback, mode)
            if not ok:
                feedback = f"{feedback}\n\n[직전 시도 실패] {note}"  # 린트 로그를 잃지 않고 덧붙인다
                continue
            passed, feedback = critic(path, mode, select)
            if passed and sample:
                log_sample("logic_lines" if mode == "logic" else mode, *sample)
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
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--mode", choices=MODES, default="format")
    ap.add_argument("--select", help="logic 모드 ruff 규칙군(기본 F=pyflakes)")
    args = ap.parse_args()
    sys.exit(0 if run_loop(args.target, args.mode, args.select)["Status"] == "PASS" else 1)
