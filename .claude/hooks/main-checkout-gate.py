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

2026-10-18 G-23 수정: 판정 기준을 CLAUDE_PROJECT_DIR(항상 메인 폴더)이 아니라 "명령이 실제로
겨누는 저장소"로 바꿨다. 훅 입력의 cwd에서 시작해 명령을 `; && || | 줄바꿈`으로 나눠 `cd`를
순서대로 따라가고, `git -C <경로>`가 있으면 그 경로를 쓴다. 그 위치에서 위로 `.git`을 찾아
디렉터리면 메인 폴더(차단 대상), 파일이면 전용 워크트리(통과)다. 경로를 알 수 없으면
($변수, 백틱, ~ 등) 안전하게 막는 쪽(fail closed)이다. `git checkout -- 파일`, `git checkout .`
같은 파일 복원은 대상이 아니다.
"""
import json
import os
import re
import sys

SAFE_TARGETS = {"main", "-", ".", "--"}
CD_WORDS = {"cd", "pushd", "set-location", "sl", "chdir"}
UNKNOWN = object()  # 경로를 정적으로 알 수 없음 -> fail closed


def project_dir():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def split_segments(cmd):
    """따옴표 밖의 ; & | 줄바꿈으로 나눈다."""
    segs, cur, q = [], [], None
    for ch in cmd:
        if q:
            cur.append(ch)
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            cur.append(ch)
        elif ch in ";&|" + chr(10) + chr(13):
            segs.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    segs.append("".join(cur))
    return [x.strip().lstrip("({ ").rstrip(")} ") for x in segs if x.strip()]


def tokenize(seg):
    toks = re.findall(r"\"[^\"]*\"|'[^']*'|[^\s]+", seg)
    return [t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" else t for t in toks]


def resolve(base, path):
    if any(c in path for c in "$`%") or path.startswith("~") or "*" in path or "?" in path:
        return UNKNOWN
    if base is UNKNOWN:
        return UNKNOWN
    try:
        return os.path.realpath(os.path.join(base, path))
    except Exception:
        return UNKNOWN


def find_git_root(path):
    """path(없으면 존재하는 가장 가까운 상위)에서 위로 .git을 찾는다. (root, is_dir) 또는 None."""
    cur = path
    while True:
        if os.path.exists(cur):
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
    while True:
        g = os.path.join(cur, ".git")
        if os.path.isdir(g):
            return cur, True
        if os.path.isfile(g):
            return cur, False
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def primary_roots(pdir):
    """보호할 메인 폴더 집합: 프로젝트 폴더가 메인이면 그것, 워크트리면 .git 파일이 가리키는 메인."""
    roots = set()
    r = find_git_root(os.path.realpath(pdir))
    if r:
        root, is_dir = r
        if is_dir:
            roots.add(os.path.normcase(root))
        else:
            try:
                line = open(os.path.join(root, ".git"), encoding="utf-8").read().strip()
                gd = line.split(":", 1)[1].strip()
                gd = os.path.realpath(os.path.join(root, gd))
                m = re.search(r"^(.*)[\\/]\.git[\\/]worktrees[\\/]", gd)
                if m:
                    roots.add(os.path.normcase(os.path.realpath(m.group(1))))
            except Exception:
                pass
    return roots


def targets_primary(path, roots):
    """path가 보호 대상 메인 폴더 안이면 True. 알 수 없으면 True(fail closed)."""
    if path is UNKNOWN:
        return True
    r = find_git_root(path)
    if not r:
        return False
    root, is_dir = r
    return is_dir and os.path.normcase(root) in roots


def parse_git(toks):
    """['git', ...] -> (C경로 또는 None, 서브명령, 나머지 인자). git이 아니면 None."""
    if not toks or toks[0].lower() not in ("git", "git.exe"):
        return None
    i, cdir = 1, None
    while i < len(toks):
        t = toks[i]
        if t == "-C" and i + 1 < len(toks):
            cdir = toks[i + 1] if cdir is None else cdir + "/" + toks[i + 1]
            i += 2
        elif t.startswith("-C") and len(t) > 2:
            cdir = t[2:]
            i += 1
        elif t == "-c" and i + 1 < len(toks):
            i += 2
        elif t.startswith("-"):
            i += 1
        else:
            return cdir, t, toks[i + 1:]
    return cdir, "", []


def checkout_target(args):
    if "--" in args:
        return None
    flags = None
    if args and args[0] in ("-b", "-c", "-B") and len(args) > 1:
        flags, args = args[0], args[1:]
    if not args:
        return None
    t = args[0].strip("\"'")
    if t in SAFE_TARGETS:
        return None
    if t.startswith("-") and not flags:
        return None
    return t


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    cmd = str((data.get("tool_input") or {}).get("command", ""))
    if "git" not in cmd:
        return 0

    pdir = project_dir()
    roots = primary_roots(pdir)
    cwd = data.get("cwd") or pdir
    cwd = os.path.realpath(cwd)

    for seg in split_segments(cmd):
        toks = tokenize(seg)
        if not toks:
            continue
        if toks[0].lower() in CD_WORDS:
            args = [t for t in toks[1:] if not t.startswith("-") or t == "-"]
            if not args:
                continue
            cwd = resolve(cwd, args[0]) if args[0] != "-" else UNKNOWN
            continue
        g = parse_git(toks)
        if not g:
            continue
        cdir, sub, args = g
        if sub == "commit":
            kind, tgt = "commit", None
        elif sub in ("checkout", "switch"):
            tgt = checkout_target(args)
            if not tgt:
                continue
            kind = "checkout"
        else:
            continue
        where = cwd if cdir is None else resolve(cwd, cdir)
        if not targets_primary(where, roots):
            continue
        shown = "알 수 없는 경로" if where is UNKNOWN else where
        if kind == "commit":
            sys.stderr.write(
                f"[main-checkout-gate] 공용 메인 폴더({shown})에서는 커밋하지 않습니다. main에 직접 push가 막혀 있어 "
                "커밋이 로컬에만 쌓입니다(2026-09-29 미푸시 커밋 8건 사고). 전용 워크트리에서 작업하세요: "
                "git worktree add <새 폴더 경로> -b claude/<작업이름> origin/main"
            )
        else:
            sys.stderr.write(
                f"[main-checkout-gate] 공용 메인 폴더({shown})는 항상 main 고정입니다. "
                f"'{tgt}'로 브랜치를 바꾸는 작업은 전용 워크트리에서 하세요: "
                f"git worktree add <새 폴더 경로> -b {tgt} origin/main"
            )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
