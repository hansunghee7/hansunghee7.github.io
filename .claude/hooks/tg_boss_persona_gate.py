#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tg_boss.py 호출 시 --persona 필수 검증 (CLAUDE.md 재발방지)

배경: 2026-09-29 지투가 tg_boss.py 호출할 때 --persona 옵션 두 번 생략해
메시지가 탐 컨펌방으로 잘못 전송됨(cxo-db#...).

규칙: tg_boss.py 또는 tg_boss 명령어를 보낼 때 --persona 필수.
없으면 즉시 차단.
"""
import sys
import json
from pathlib import Path


def check_tg_boss_persona(command_line: str) -> tuple[bool, str]:
    """tg_boss.py 호출에 --persona가 있는지 검증."""
    # 명령어 파싱
    cmd_parts = command_line.split()

    # tg_boss.py 또는 tg_boss 명령어인지 확인
    is_tg_boss = any(
        'tg_boss' in part
        for part in cmd_parts
    )

    if not is_tg_boss:
        return True, ""  # tg_boss 아님, 검증 불필요

    # --persona가 있는지 확인
    if '--persona' not in cmd_parts:
        return False, (
            "❌ [tg_boss 관문] --persona 필수 옵션 생략\n"
            "사용: python scripts/ops/tg_boss.py text \"메시지\" --persona 지투\n"
            f"가능한 페르소나: 마야, 지투, 노트, 핏, 탐, 클탐\n"
            "\n원인: 2026-09-29 메시지가 잘못된 페르소나로 발송됨(탐 → 지투)\n"
            "재발방지: 페르소나 옵션은 의무화됨"
        )

    # --persona 다음에 값이 있는지 확인
    try:
        persona_idx = cmd_parts.index('--persona')
        if persona_idx + 1 >= len(cmd_parts):
            return False, "❌ --persona 값이 없습니다"
        persona = cmd_parts[persona_idx + 1]
        valid_personas = {"마야", "지투", "노트", "핏", "탐", "클탐"}
        if persona not in valid_personas:
            return False, f"❌ 알 수 없는 페르소나: {persona}\n가능: {', '.join(valid_personas)}"
    except (ValueError, IndexError):
        return False, "❌ --persona 파싱 오류"

    return True, ""


def main():
    """훅 진입점 (settings.json에서 자동 호출)."""
    if len(sys.argv) < 2:
        return 0

    command_line = sys.argv[1]
    is_valid, error_msg = check_tg_boss_persona(command_line)

    if not is_valid:
        print(error_msg, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
