# -*- coding: utf-8 -*-
"""스레드 글자 수 관문(publish_sns_queue.policy_problem) 시험. 제목을 본문에 붙인 뒤 500자를 넘으면 막는다."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("psq", ROOT / "scripts" / "publish_sns_queue.py")
psq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(psq)


def item(body, title="", platform="threads"):
    return {"id": "t1", "platform": platform, "publishAt": "2026-10-01T00:00:00+09:00",
            "content": {"media_source": ["x.png"], "body": body, "title": title}}


def test_threads_under_limit_passes_text_gate():
    p = psq.policy_problem(item("가" * 500))
    assert p is None or "스레드" not in p


def test_threads_over_limit_blocked():
    assert "501자" in psq.policy_problem(item("가" * 501))


def test_threads_title_counts_toward_limit():
    assert "스레드" in psq.policy_problem(item("가" * 495, title="제목입니다"))


def test_other_platform_not_limited():
    p = psq.policy_problem(item("가" * 900, platform="linkedin"))
    assert p is None or "스레드" not in p


def test_final_body_matches_register_rule():
    c = {"title": "제목", "body": "본문"}
    assert psq.final_body(c) == "제목\n\n본문"
    assert psq.final_body({"title": "제목", "body": "제목 본문"}) == "제목 본문"
