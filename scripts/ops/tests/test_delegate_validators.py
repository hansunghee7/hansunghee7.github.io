"""delegate_tone_tags.py·delegate_pr_desc.py의 검증기(validate) 단위 시험.

ask()는 ollama_ask.py(로컬 LLM)를 서브프로세스로 부르고 delegate_pr_desc.py의 main()은
gh(PR diff)를 부르므로, 이 시험은 그 경로를 아예 타지 않는 validate()만 직접 호출한다.
두 모듈을 임포트해도 네트워크·서브프로세스 부작용이 없다(둘 다 `if __name__ == "__main__":`
가드 뒤에 실행 로직이 있다) — 다만 안전을 위해 외부 호출 함수(ask, gh)는 그래도 monkeypatch로
존재만 확인하고 호출되지 않음을 보장한다.

실행: python -m pytest scripts/ops/tests/test_delegate_validators.py
"""
import importlib.util
from pathlib import Path

OPS = Path(__file__).resolve().parents[1]


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, OPS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tone_tags = _load("delegate_tone_tags_under_test", "delegate_tone_tags.py")
pr_desc = _load("delegate_pr_desc_under_test", "delegate_pr_desc.py")


def _mock_ask_never_called(monkeypatch, module):
    def boom(*a, **kw):
        raise AssertionError("ask()가 호출되면 안 된다(이 시험은 validate만 본다)")

    monkeypatch.setattr(module, "ask", boom)


# ---------------------------------------------------------------------------
# delegate_tone_tags.validate(tags, n)
# ---------------------------------------------------------------------------

def _tag(i, tone="explain", speed=1.0, pause=0.3, emph=False):
    return {"i": i, "tone": tone, "speed": speed, "pause": pause, "emph": emph, "why": "test"}


def test_tone_tags_valid_input_has_no_complaints(monkeypatch):
    _mock_ask_never_called(monkeypatch, tone_tags)
    tags = [_tag(0), _tag(1, tone="hook"), _tag(2, tone="closing")]
    assert tone_tags.validate(tags, 3) == []


def test_tone_tags_empty_input_zero_lines_is_valid():
    assert tone_tags.validate([], 0) == []


def test_tone_tags_line_count_or_order_mismatch():
    tags = [_tag(0), _tag(2)]  # 1번이 빠짐
    why = tone_tags.validate(tags, 3)
    assert any("줄 번호" in w for w in why)


def test_tone_tags_rejects_unknown_tone():
    tags = [_tag(0, tone="rage")]
    why = tone_tags.validate(tags, 1)
    assert any("tone" in w and "rage" in w for w in why)


def test_tone_tags_speed_range_boundaries():
    assert tone_tags.validate([_tag(0, speed=0.85)], 1) == []
    assert tone_tags.validate([_tag(0, speed=1.2)], 1) == []
    assert any("speed" in w for w in tone_tags.validate([_tag(0, speed=0.84)], 1))
    assert any("speed" in w for w in tone_tags.validate([_tag(0, speed=1.21)], 1))


def test_tone_tags_pause_range_boundaries():
    assert tone_tags.validate([_tag(0, pause=0.15)], 1) == []
    assert tone_tags.validate([_tag(0, pause=1.0)], 1) == []
    assert any("pause" in w for w in tone_tags.validate([_tag(0, pause=0.14)], 1))
    assert any("pause" in w for w in tone_tags.validate([_tag(0, pause=1.01)], 1))


def test_tone_tags_emph_over_three_is_rejected():
    tags = [_tag(i, emph=True) for i in range(4)]
    why = tone_tags.validate(tags, 4)
    assert any("emph" in w for w in why)


def test_tone_tags_emph_exactly_three_is_allowed():
    tags = [_tag(i, emph=True) for i in range(3)]
    assert tone_tags.validate(tags, 3) == []


def test_tone_tags_why_list_is_capped_at_six():
    # 4줄 각각 tone·speed·pause 세 가지를 동시에 위반 -> 12개 사유가 나올 수 있지만 6개로 잘린다.
    tags = [_tag(i, tone="rage", speed=9, pause=9) for i in range(4)]
    why = tone_tags.validate(tags, 4)
    assert len(why) <= 6


# ---------------------------------------------------------------------------
# delegate_pr_desc.validate(d, files)
# ---------------------------------------------------------------------------

def _draft(**kw):
    d = {
        "title": "짧은 제목",
        "what": ["변경 1", "변경 2", "변경 3"],
        "how_to_verify": ["테스트 실행"],
        "touched_files": ["a.py"],
    }
    d.update(kw)
    return d


def test_pr_desc_valid_draft_has_no_complaints(monkeypatch):
    _mock_ask_never_called(monkeypatch, pr_desc)
    assert pr_desc.validate(_draft(), {"a.py", "b.py"}) == []


def test_pr_desc_title_too_long():
    long_title = "가" * 61
    why = pr_desc.validate(_draft(title=long_title), {"a.py"})
    assert any("제목" in w for w in why)


def test_pr_desc_title_at_sixty_is_allowed():
    ok_title = "가" * 60
    assert pr_desc.validate(_draft(title=ok_title), {"a.py"}) == []


def test_pr_desc_what_count_bounds():
    assert any("what" in w for w in pr_desc.validate(_draft(what=["x", "y"]), {"a.py"}))  # 2개(3미만)
    assert any("what" in w for w in pr_desc.validate(_draft(what=["x"] * 7), {"a.py"}))  # 7개(6초과)
    assert pr_desc.validate(_draft(what=["x", "y", "z"]), {"a.py"}) == []  # 3개(경계 통과)


def test_pr_desc_how_to_verify_count_bounds():
    assert any("how_to_verify" in w for w in pr_desc.validate(_draft(how_to_verify=[]), {"a.py"}))
    assert any("how_to_verify" in w for w in pr_desc.validate(_draft(how_to_verify=["a", "b", "c", "d"]), {"a.py"}))
    assert pr_desc.validate(_draft(how_to_verify=["a", "b", "c"]), {"a.py"}) == []


def test_pr_desc_touched_files_must_be_subset_of_diff_files():
    why = pr_desc.validate(_draft(touched_files=["a.py", "nope.py"]), {"a.py"})
    assert any("diff에 없는 파일" in w for w in why)


def test_pr_desc_touched_files_empty_is_allowed():
    assert pr_desc.validate(_draft(touched_files=[]), {"a.py"}) == []


def test_pr_desc_rejects_parentheses():
    why = pr_desc.validate(_draft(title="제목(설명)"), {"a.py"})
    assert any("괄호" in w for w in why)


def test_pr_desc_rejects_em_dash():
    why = pr_desc.validate(_draft(what=["변경 1", "변경 2—부가 설명", "변경 3"]), {"a.py"})
    assert any("긴 줄표" in w for w in why)
