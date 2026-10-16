# -*- coding: utf-8 -*-
"""슈퍼사서 문서량 점검: 판정 재료에 들어가고, 상한 규칙에 자동 로드 문서가 빠지지 않는다(10/16)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import context_audit as c  # noqa: E402


def test_review_prompt_carries_volume_section():
    p = c.REVIEW.format(first="x", impacts="x", strategy="x", ledger="x", questions="x", volume="- CLAUDE.md: 260줄 / 상한 250 (넘침)", structure="## 3. 같은 사실")
    assert "문서량 점검" in p and "260줄" in p and "⑨" in p and "구조 스캔 발췌" in p and "순서" in p


def test_volume_rules_cover_auto_loaded_docs():
    pats = [r[0] for r in c.VOLUME_RULES]
    for need in ("CLAUDE.md", "docs/역할노트-*.md", "docs/세션카드/*.md"):
        assert need in pats
    assert c.MEMORY_LIMIT == 200
