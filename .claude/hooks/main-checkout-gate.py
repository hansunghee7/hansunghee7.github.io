"""PreToolUse 훅(2026-09-27 탐, 사장님 지시): 공용 메인 폴더(`.git`이 디렉터리인 원본
체크아웃, 전용 워크트리가 아닌 곳)에서 `git checkout`/`git switch`로 main이 아닌
브랜치로 옮겨가려는 시도를 막는다.

왜: 2026-09-25 지투 세션이 이 폴더에서 직접 `claude/jitu-ledger-0926d`로 체크아웃해 커밋 1개를
남기고(PR #1118로 이미 병합) 그대로 두고 감. 아무도 폴더를 main으로 되돌리지 않아, 이후 이
폴더에서 열린 여러 "하이~" 세션(9/27 아침 포함)이 132커밋 뒤처진 진행상황.md·업무대장을
그대로 읽고 보고하는 사고가 반복됐다(CLAUDE.md id:77f6 위반이 문서·기억에만 있어 매번
잊혔음 — id:4e7b에 따라 도구 관문으로 옮김). 근거: cxo-db 기록(2026-09-27), 사장님 지시
"못박기".

2026-09-29 확장: 원본 체크아웃에서의 `git commit`도 막는다(로컬 main에 미푸시 커밋이 쌓이는 경로).

범위: 이 저장소(hansunghee7.github.io)의 원본 체크아웃에만 적용된다. 전용 워크트리
(`git worktree add`로 만든 폴더, `.git`이 파일)에서는 어떤 브랜치를 써도 막지 않는다 —
그게 원래 의도된 작업 방식이다(CLAUDE.md id:77f6, 각 세션은 자기 워크트리에서 작업).

한계: 명령에 `cd`가 섞여 있으면(예: `cd ../다른워크트리 && git checkout -b x`) 최종
작업 디렉터리를 신뢰할 수 없어 검사를 건너뛴다(과잉 차단 방지). `git checkout -- 파일`,
`git checkout .`처럼 파일 복원에 쓰는 형태도 대상이 아니다.
"""
import json
import os
import re
import sys

CHECKOUT_RE = re.compile(r"git\s+(checkout|switch)\s+(?P<flags>-[bcB]\s+)?(?P<target>[^\s]+)")
SAFE_TARGETS = {"main", "-", ".", "--"}
# 2026-09-29 추가: 공용 메인 폴더에서 main에 직접 커밋하는 것도 막는다(git -C <다른 폴더>는 대상 아님)
COMMIT_RE = re.compile(r"(^|[;&|(]\s*)git\s+(?!-C\b)(?:-[^\s]+\s+)*commit\b")


def project_dir():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def is_primary_checkout(path):
    """`.git`이 디렉터리면 원본 체크아웃, 파일이면 전용 워크트리다."""
    git_path = os.path.join(path, ".git")
    return os.path.isdir(git_path)


def extract_target(cmd):
    if " -- " in cmd:
        return None
    m = CHECKOUT_RE.search(cmd)
    if not m:
        return None
    target = m.group("target").strip("\"'")
    if target in SAFE_TARGETS:
        return None
    if target.startswith("-") and not m.group("flags"):
        # 알 수 없는 옵션(예: --detach) — 다음 인자가 뭔지 안전하게 못 잡으니 통과시킨다.
        return None
    return target


def has_directory_change(cmd):
    return bool(re.search(r"(^|[;&|]|\b)cd\s+", cmd))


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0

    if data.get("tool_name") not in ("Bash", "PowerShell"):
        return 0

    cmd = str((data.get("tool_input") or {}).get("command", ""))
    if has_directory_change(cmd):
        return 0

    if COMMIT_RE.search(cmd) and is_primary_checkout(project_dir()):
        sys.stderr.write(
            f"[main-checkout-gate] 공용 메인 폴더({project_dir()})에서는 커밋하지 않습니다. main에 직접 push가 막혀 있어 "
            "커밋이 로컬에만 쌓입니다(2026-09-29 미푸시 커밋 8건 사고). 전용 워크트리에서 작업하세요: "
            "git worktree add <새 폴더 경로> -b claude/<작업이름> origin/main"
        )
        return 2

    target = extract_target(cmd)
    if not target:
        return 0

    top = project_dir()
    if not is_primary_checkout(top):
        return 0

    sys.stderr.write(
        f"[main-checkout-gate] 공용 메인 폴더({top})는 항상 main 고정입니다. "
        f"'{target}'로 브랜치를 바꾸는 작업은 전용 워크트리에서 하세요: "
        f"git worktree add <새 폴더 경로> -b {target} origin/main"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
