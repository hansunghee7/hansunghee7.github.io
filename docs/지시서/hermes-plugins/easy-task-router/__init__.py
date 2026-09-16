"""Easy-task router.

Classifies the current turn's user message with a cheap regex heuristic
(no extra LLM call) and, when it looks like a simple judgment-free lookup,
injects a per-turn reminder telling the model to use delegate_task instead
of handling it directly. See solar-bible.md section 18 for the policy this
implements, and hansunghee7.github.io docs/진행상황.md (2026-09-17, 탐(로컬))
for the background and empirical evidence that a passive persona-file
policy alone did not reliably trigger auto-delegation.
"""

import re

_EASY_PATTERNS = [
    r"\bhow many\b",
    r"\bcount\b",
    r"\blist (the |all )?files\b",
    r"\bwhat files\b",
    r"\bwhich files\b",
    r"몇\s*개",
    r"개수",
    r"파일\s*목록",
    r"폴더\s*목록",
    r"목록.{0,5}(알려|보여|뽑아)",
]

_NOT_EASY_PATTERNS = [
    r"\bfix\b",
    r"\bimplement\b",
    r"\brefactor\b",
    r"\bdelete\b",
    r"\bremove\b",
    r"\bpush\b",
    r"\bdeploy\b",
    r"\brestart\b",
    r"\bmerge\b",
    r"수정",
    r"구현",
    r"고쳐",
    r"삭제",
    r"배포",
    r"재시작",
    r"머지",
    r"승인",
    r"critical",
    r"approve",
]

_MAX_EASY_LEN = 220

_ROUTER_NOTE = (
    "Router note: this looks like a simple, judgment-free lookup task "
    "(counting, listing, a plain format conversion). Per solar-bible.md "
    "section 18, use delegate_task now to hand it to the gemini-pool "
    "subagent instead of running it yourself."
)


def _classify_easy(message):
    if not message or len(message) > _MAX_EASY_LEN:
        return False
    lowered = message.lower()
    if any(re.search(p, lowered, re.IGNORECASE) for p in _NOT_EASY_PATTERNS):
        return False
    return any(re.search(p, lowered, re.IGNORECASE) for p in _EASY_PATTERNS)


def route_easy_tasks(user_message=None, **kwargs):
    del kwargs
    if _classify_easy(user_message or ""):
        return {"context": _ROUTER_NOTE}
    return None


def register(ctx):
    ctx.register_hook("pre_llm_call", route_easy_tasks)
