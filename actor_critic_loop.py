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
    "## 이번 모드: 논리 린트 수정(줄 단위 치환 방식)\n"
    "코드를 다시 쓰지 마라. 위 린트 오류를 해결하려고 고쳐야 하는 줄만 JSON 객체 배열로 출력하라. "
    '형식: [{"line": 5, "replace": "import os, sys"}]. line은 아래 \'소스 코드\' 왼쪽 번호, '
    'replace는 그 줄을 대체할 코드 한 줄 전체(들여쓰기 포함)다. 줄을 통째로 지우려면 "replace": "" 로 쓴다. '
    "린트가 지적한 줄만 고치고, 원래 줄에 없던 새 이름·코드를 만들지 마라. 배열 외에는 아무것도 출력하지 마라.\n"
    "여러 줄 블록(함수 전체)을 지워야 할 때만 범위 형식을 쓴다: "
    '[{"start_line": 1, "end_line": 2, "replace": ""}]. 범위는 함수 정의 하나를 데코레이터 없이 처음부터 끝까지 정확히 덮어야 하고 replace는 "" 만 허용한다. '
    "F811(중복 정의)은 나중(아래) 정의는 그대로 두고, 'from line N'이 가리키는 앞선(위) 정의 블록을 범위로 지운다."
)
WORD = re.compile(r"\w+")
DUP_FROM = re.compile(r"(?m)^F811\b[^\n]*from line (\d+)")
# 삭제를 허용하는 줄: 미사용 import(F401)·미사용 변수(F841)로 지적된 줄만. F821(미정의) 등의 줄은 대상 아님
# (실측: 다중 이름 import 줄을 통째로 지운 뒤 생긴 F821 사용 줄 11개를 헤르메스가 연쇄로 지우려 했다).
FLAGGED = re.compile(r"(?m)^F(?:401|811|841)\b[^\n]*\n\s*-->\s.*?:(\d+):\d+")  # F811: 중복 정의 줄(단, def 한 줄만 지우면 문법 검사가 거부)

# 에스컬레이션 페일오버 순서(AI_ROUTING_POLICY): 솔라 프로 -> 제미나이 -> 네모트론 -> Qwen
FAILOVER = ["solar-pro", "gemini", "nemotron", "qwen"]


def run(cmd: list[str], stdin: str | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, creationflags=NOWIN, check=False)


def ask_backend(prompt: str) -> subprocess.CompletedProcess:
    """Actor 모델 선택. 기본은 로컬 헤르메스(도구 차단 ask-pure: 기본 ask는 파일을 직접 고쳐 파서를 우회한다).
    ACL_BACKEND=openrouter:<모델 id>이면 scripts/ops/or_ask.py로 호출한다(키는 OPENROUTER_API_KEY 환경변수, ACL_PYTHON=litellm 설치된 python)."""
    backend = os.environ.get("ACL_BACKEND", "hermes")
    if backend.startswith("openrouter:"):
        script = os.path.join(ROOT, "scripts", "ops", "or_ask.py")
        return run([os.environ.get("ACL_PYTHON", sys.executable), script, backend.split(":", 1)[1]], stdin=prompt)
    return run([BASH, HX, "ask-pure"], stdin=prompt)


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


def model_tag() -> str:
    """생성 주체 태그. ACL_MODEL_TAG가 우선, 아니면 백엔드에서 유도한다.
    로컬 헤르메스의 실제 모델은 `hermes status` 기준 solar-pro4(Upstage Solar)다(8B가 아님)."""
    if os.environ.get("ACL_MODEL_TAG"):
        return os.environ["ACL_MODEL_TAG"]
    b = os.environ.get("ACL_BACKEND", "hermes")
    if b.startswith("openrouter:"):
        return b.split(":", 1)[1].split("/")[-1].removesuffix("-instruct")
    return "hermes-solar-pro4"


def log_sample(mode: str, prompt: str, completion: str) -> None:
    """검증(PASS)된 회차만 JSONL로 추가한다. 실패 회차는 정답이 아니므로 학습 데이터에 넣지 않는다. model = 생성 주체 태그."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, f"{mode}.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"prompt": prompt, "completion": completion, "model": model_tag()}, ensure_ascii=False) + "\n")


def has_call(line: str) -> bool:
    """줄이 함수 호출(부작용 가능)을 포함하는지. 지우면 동작이 바뀔 수 있어 삭제 대신 호출을 남기게 한다."""
    try:
        return any(isinstance(n, ast.Call) for n in ast.walk(ast.parse(line.strip())))
    except SyntaxError:
        return False


def parse_edits(reply: str) -> list | None:
    """응답에서 마지막으로 해석되는 JSON 배열(줄 수정 목록)을 찾는다. 중첩 괄호·문자열 안의 대괄호가 있어 정규식 대신 raw_decode."""
    text, dec, found, i = NOISE.sub("", reply), json.JSONDecoder(), None, 0
    while i < len(text):
        if text[i] == "[":
            try:
                obj, end = dec.raw_decode(text, i)
            except ValueError:
                i += 1
                continue
            if isinstance(obj, list):
                found = obj
                i = end  # 해석된 배열 안(문자열 속 'argv[0]' 등)은 다시 보지 않는다: 안쪽 [0]이 진짜 답을 덮어쓰던 버그 수정
                continue
        i += 1
    return found


def apply_edits(src: str, reply: str, feedback: str) -> tuple[str | None, str, list | None]:
    """logic 모드: 헤르메스의 [{"line","replace"}] 배열을 원본 줄에 적용한다. (새 소스 또는 None, 실패 사유, 검증된 수정 목록).
    ① 줄 번호는 F401/F841로 지적된 줄만 ② replace는 한 줄이며 원래 줄에 없던 이름(단어)을 만들 수 없다(환각 주입 방지)
    ③ 줄 수가 변하지 않는 치환은 번호가 밀리지 않고, 삭제("")는 큰 번호부터(역순) 처리한다."""
    edits = parse_edits(reply)
    if not edits:
        return None, '응답에서 수정 목록 JSON 배열을 찾지 못함. [{"line": 5, "replace": "..."}] 형태의 배열만 출력할 것', None
    lines = src.splitlines(keepends=True)
    flagged = {int(n) for n in FLAGGED.findall(feedback)}
    dup_from = {int(n) for n in DUP_FROM.findall(feedback)}  # F811 'from line N': 앞선(죽은) 정의의 시작 줄
    seen: set[int] = set()
    for i, e in enumerate(edits):
        if (isinstance(e, dict) and set(e) == {"start_line", "end_line", "replace"}
                and e["start_line"] == e["end_line"] and isinstance(e["start_line"], int) and e["replace"] == ""):
            edits[i] = e = {"line": e["start_line"], "replace": ""}  # 한 줄짜리 범위는 한 줄 삭제와 같다(같은 가드 적용). 실측: Llama가 import 한 줄을 범위로 답함
        if isinstance(e, dict) and "start_line" in e:  # 범위 삭제: 함수 정의 하나를 통째로
            a, b = e.get("start_line"), e.get("end_line")
            if not (isinstance(a, int) and isinstance(b, int) and e.get("replace") == "" and set(e) == {"start_line", "end_line", "replace"}):
                return None, f'형식 위반: {e!r}. 범위는 {{"start_line": 정수, "end_line": 정수, "replace": ""}}만 허용', None
            if a < 1 or b < a or b > len(lines) or seen & set(range(a, b + 1)):
                return None, f"범위 {a}-{b}가 파일 밖이거나 다른 수정과 겹침", None
            if a not in dup_from:
                return None, f"범위 삭제는 F811이 'from line N'으로 가리킨 앞선 정의({sorted(dup_from)}의 시작 줄)에만 허용됨", None
            node = next((n for n in ast.walk(ast.parse(src))
                         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno == a), None)
            if node is None or node.decorator_list or node.end_lineno != b:
                return None, (f"범위 {a}-{b}가 데코레이터 없는 함수 정의 하나의 처음부터 끝까지와 정확히 일치하지 않음"
                              f"(그 정의는 {a}-{getattr(node, 'end_lineno', '?')}줄)"), None
            seen |= set(range(a, b + 1))
            continue
        if not (isinstance(e, dict) and isinstance(e.get("line"), int) and isinstance(e.get("replace"), str)):
            return None, f'형식 위반: {e!r}. {{"line": 정수, "replace": 문자열}} 또는 범위 객체만 허용', None
        n, new = e["line"], e["replace"]
        if n < 1 or n > len(lines) or n in seen:
            return None, f"줄 번호가 범위 밖이거나 중복: {n}", None
        if n not in flagged:
            return None, f"린트가 지적하지 않은 줄({n})은 고칠 수 없음. 고칠 수 있는 줄: {sorted(flagged)}", None
        if lines[n - 1].rstrip().endswith(":"):
            # 실측: def 줄만 지우면 본문이 위 함수의 죽은 코드로 붙어 문법·ruff를 통과한 채 동작이 바뀌었다(가짜 PASS)
            return None, f"줄 {n}은 블록 머리 줄(def/class/if 등, ':'로 끝남)이라 수정·삭제할 수 없음", None
        if "\n" in new or "\r" in new:
            return None, f"replace는 한 줄이어야 함(줄 {n})", None
        if not set(WORD.findall(new)) - {"_"} <= set(WORD.findall(lines[n - 1])):  # '_ = f()'는 관용 표현이라 허용
            return None, f"줄 {n}: 원래 줄에 없던 이름을 만들 수 없음(치환은 원래 줄의 부분집합만 허용)", None
        if not new.strip() and has_call(lines[n - 1]):
            return None, (f"줄 {n}은 함수 호출을 포함해 통째로 지우면 부작용이 사라짐. "
                          "호출은 남기고 미사용 변수만 떼어라(예: '    f()' 또는 '    _ = f()')"), None
        seen.add(n)
    for e in sorted(edits, key=lambda e: e.get("start_line", e.get("line")), reverse=True):
        if "start_line" in e:
            del lines[e["start_line"] - 1:e["end_line"]]
            continue
        n, new = e["line"], e["replace"]
        if new.strip():
            lines[n - 1] = new.rstrip() + ("\n" if lines[n - 1].endswith("\n") else "")
        else:
            del lines[n - 1]
    return "".join(lines), "", edits


def actor(path: str, feedback: str, mode: str = "format") -> tuple[bool, str, tuple[str, str] | None]:
    """헤르메스에게 가드레일+린트 로그+소스를 넘기고, 걸러낸 결과만 파일에 쓴다. (성공 여부, 실패 사유, (프롬프트, 응답))."""
    with open(REVIEWER, encoding="utf-8") as f:
        guard = f.read()
    with open(path, encoding="utf-8") as f:
        src = f.read()
    shown = "".join(f"{i:>4}| {ln}" for i, ln in enumerate(src.splitlines(keepends=True), 1)) if mode == "logic" else src
    sample_prompt = f"## 린트 에러 로그\n{feedback}\n\n## 소스 코드\n{shown}"
    mode_note = f"\n\n{LOGIC_NOTE}" if mode == "logic" else ""
    r = ask_backend(f"{guard}{mode_note}\n\n{sample_prompt}")
    if r.returncode != 0:
        return False, f"헤르메스 호출 실패(exit {r.returncode}): {r.stderr.strip()[:300]}", None
    if os.environ.get("ACL_DUMP"):  # 디버그: 헤르메스 원문 응답 보관(스트레스 테스트용)
        with open(os.environ["ACL_DUMP"], "a", encoding="utf-8") as f:
            f.write(r.stdout + "\n=====\n")
    if mode == "logic":
        code, why, edits = apply_edits(src, r.stdout, feedback)
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
        return True, "", (sample_prompt, json.dumps(edits, ensure_ascii=False))
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
                log_sample("logic_replace" if mode == "logic" else mode, *sample)
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
