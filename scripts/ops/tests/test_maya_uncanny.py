# -*- coding: utf-8 -*-
"""마야 글쓰기 lint()의 불쾌한 골짜기 규칙(U1~U12) 시험. 예문은 짧게 직접 쓴 것이다(초안 원문을 넣지 않는다)."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("maya_write", HERE / "maya_write.py")
mw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mw)


def rules(text, context="essay"):
    return {i["rule"]: i["level"] for i in mw.lint(text, context)["issues"] if i["rule"].startswith("U")}


# 대표 수정본 문체를 흉내 낸 예문: 이름으로 부르고, 원인·동기가 있고, 감탄 어미로 온도를 낸다
BOSS_STYLE = (
    "지난 금요일 처음으로 AWS에 가입했습니다. 크레딧을 받으려고 서류를 세 번 고쳐 냈습니다. "
    "건망증 때문에 마감을 놓칠 뻔해서 지투에게 일정을 챙기라고 시켰습니다. "
    "막상 승인 메일을 받으니 도전욕이 생기더군요. 이래선 안되겠다는 생각에 다음 신청서도 바로 썼습니다.\n\n"
    "에이전트에게 말을 함부로 하던 버릇도 그날 고쳤습니다. 생각보다 일이 빨라지네요. 같이 해 보시죠 ;-)"
)


def test_boss_style_has_no_uncanny_errors():
    for ctx in ("essay", "linkedin", "home", "generic"):
        r = rules(BOSS_STYLE, ctx)
        assert r == {}, (ctx, r)


def test_maya_draft_style_triggers_rules():
    maya = (
        "결론부터 말하면 크레딧은 스노우볼처럼 불어납니다. 그 에이전트는 반가웠어요. "
        "결국 작은 신청 하나가 큰 기회를 만든 셈이죠. ㅎㅎ\n\n"
        "여러분은 어떤 크레딧을 받고 계신가요?"
    )
    r = rules(maya, "linkedin")
    assert r.get("U2-셈이죠") == "error"
    assert r.get("U1-결론부터") == "warn"
    for rid in ("U4-상투은유", "U5-인터뷰말투", "U6-추상평가어", "U10-ㅎㅎ", "U11-질문마무리"):
        assert r.get(rid) == "warn", rid
    assert mw.lint(maya, "linkedin")["code"] == 2


def test_conclusion_first_only_in_experience_contexts():
    t = "결론부터 말하면 설정은 세 단계입니다. 먼저 키를 만듭니다."
    assert rules(t, "essay").get("U1-결론부터") == "warn"
    assert rules(t, "linkedin").get("U1-결론부터") == "warn"
    assert "U1-결론부터" not in rules(t, "home")
    assert "U1-결론부터" not in rules(t, "generic")


def test_summary_and_fiction_are_errors():
    assert rules("핵심은 순서입니다. 그래서 바꿨습니다.", "home").get("U1-요약선언") == "error"
    assert rules("가상의 상황을 하나 들어 보겠습니다.", "home").get("U7-가상장면") == "error"


def test_count_thresholds():
    once = "속도가 아니라 방향입니다. 그래서 바꿨습니다."
    twice = once + " 도구가 아니라 습관입니다."
    assert "U3-대구프레임" not in rules(once)
    assert rules(twice).get("U3-대구프레임") == "warn"
    assert "U8-모호지칭" not in rules("그 에이전트가 답했습니다.")
    assert rules("그 에이전트가 답했습니다. 한 팀원이 웃었습니다.").get("U8-모호지칭") == "warn"
    two = "대표는 바쁩니다. 대표가 결정합니다."
    assert "U9-3인칭대표" not in rules(two)
    assert rules(two + " 대표의 하루는 깁니다.").get("U9-3인칭대표") == "warn"


def test_flat_formal_essay_warns_but_not_info_post():
    flat = "오늘 회의에서 순서를 바꿨습니다. " * 40
    assert rules(flat, "essay").get("U12-감탄어미없음") == "warn"
    assert "U12-감탄어미없음" not in rules(flat, "home")
    assert "U12-감탄어미없음" not in rules(flat + "생각보다 빠르네요.", "essay")


def test_existing_selftest_still_passes():
    assert mw.selftest() == 0
