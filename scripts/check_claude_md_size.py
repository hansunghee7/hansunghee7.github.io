#!/usr/bin/env python3
"""CLAUDE.md 줄 수 검사. 사장님 결정(2026-09-20): 상한 250줄(초과 PR은 병합 차단), 목표는 200줄 이하.

목표 200줄은 이 검사가 아니라 **격주 폴리싱**(docs/폴리싱_기록.md)으로 지킨다. 그 폴리싱이 실제로 도는지는 감시(scripts/ops)가
14일 주기로 확인한다. 이 검사가 있는 이유: 200줄 목표가 문서에만 있을 때 CLAUDE.md는 3.5주 만에 45줄에서 604줄이 됐다.
한계: 사장님 본인의 직접 커밋과 자동화는 병합 규칙을 우회하므로 이 검사가 못 잡는다(그 경우는 감시가 줄 수로 잡는다).
"""
import glob
import os
import re
import sys

WARN, LIMIT = 200, 250
NOTE_LIMIT = 80  # 역할 노트 상한(CLAUDE.md 다이어트 기준, 2026-10-02 F1 E5로 검사 추가)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    rc = check_claude_md()
    rc += check_role_notes()
    check_dead_refs()
    return 1 if rc else 0


def check_claude_md():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "CLAUDE.md")
    n = len(open(path, encoding="utf-8").read().splitlines())
    if n > LIMIT:
        print(f"::error file=CLAUDE.md::CLAUDE.md가 {n}줄로 상한 {LIMIT}줄을 넘었습니다. 넣으려면 같은 PR에서 스킬, rule, docs로 옮겨 줄이세요(절차: docs/폴리싱_기록.md).")
        return 1
    if n > WARN:
        print(f"::warning file=CLAUDE.md::CLAUDE.md가 {n}줄로 목표 {WARN}줄을 넘었습니다(상한 {LIMIT}줄). 격주 폴리싱 때 줄이세요.")
    else:
        print(f"CLAUDE.md {n}줄(목표 {WARN}, 상한 {LIMIT})")
    return 0


def check_role_notes():
    """역할 노트가 80줄을 넘으면 실패. 반환값은 실패 수."""
    bad = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "docs", "역할노트-*.md"))):
        n = len(open(f, encoding="utf-8").read().splitlines())
        name = os.path.basename(f)
        if n > NOTE_LIMIT:
            print(f"::error file=docs/{name}::{name}이 {n}줄로 역할 노트 상한 {NOTE_LIMIT}줄을 넘었습니다. 스킬, rule, docs로 옮겨 줄이세요.")
            bad += 1
        else:
            print(f"{name} {n}줄(상한 {NOTE_LIMIT})")
    return bad


def check_dead_refs():
    """CLAUDE.md, 역할노트, SKILL.md가 가리키는 docs/...md 경로와 `이름` 스킬이 실제로 있는지 본다. 경고만 한다(실패 아님)."""
    files = [os.path.join(ROOT, "CLAUDE.md")]
    files += sorted(glob.glob(os.path.join(ROOT, "docs", "역할노트-*.md")))
    files += sorted(glob.glob(os.path.join(ROOT, ".claude", "skills", "*", "SKILL.md")))
    skills = {os.path.basename(os.path.dirname(f)) for f in glob.glob(os.path.join(ROOT, ".claude", "skills", "*", "SKILL.md"))}
    n = 0
    for f in files:
        rel = os.path.relpath(f, ROOT).replace(os.sep, "/")
        text = open(f, encoding="utf-8").read()
        for ref in sorted(set(re.findall(r"(?<![\w/.-])(docs/[^\s`()\[\]<>\"'|,]+?\.md)", text))):
            if "*" in ref or "..." in ref or "<" in ref:
                continue
            if not os.path.exists(os.path.join(ROOT, ref)):
                print(f"::warning file={rel}::죽은 참조 의심: {ref}가 없습니다.")
                n += 1
        for name in sorted(set(re.findall(r"`([a-z0-9][a-z0-9-]*)`\s*스킬", text))):
            if name not in skills:
                print(f"::warning file={rel}::죽은 참조 의심: `{name}` 스킬이 .claude/skills/에 없습니다.")
                n += 1
    print(f"죽은 참조 의심 {n}건(경고만, 병합은 막지 않음)")


if __name__ == "__main__":
    sys.exit(main())
