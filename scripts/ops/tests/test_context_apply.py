# -*- coding: utf-8 -*-
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("context_apply", Path(__file__).resolve().parents[1] / "context_apply.py")
ca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ca)


def test_hide_refs_takes_only_cards_before_colon_in_hide_section():
    text = """## B0. 혼란 정보 판정

**숨김(1차에서 내림)**
- 핏-발행#24: 정본 #43으로 대체됨.
- 핏-영상생성#47, 핏-대본#19: #61로 통합하고 숨긴다.

**정본 표시 보강**
- 핏-영상생성#61: 정본

## B. 장부 판정
- 핏-조립#1: 무관
"""
    assert ca.hide_refs(text) == [("핏-발행", 24), ("핏-영상생성", 47), ("핏-대본", 19)]


def test_hide_refs_without_b0_returns_empty():
    assert ca.hide_refs("## A. 제안\n- 핏#1: x") == []


def test_actions_reads_rewrite_block_and_drops_bad_items():
    text = '본문\n```actions\n[{"op":"rewrite","card":"마야#35","instruction":"정본 마야#38을 가리키게"},{"op":"rewrite","card":"없는형식","instruction":"x"},{"op":"delete","card":"핏#1","instruction":"x"}]\n```\n'
    assert ca.actions(text) == [{"op": "rewrite", "card": "마야#35", "instruction": "정본 마야#38을 가리키게"}]


def test_actions_missing_or_broken_block_returns_empty():
    assert ca.actions("```actions\n[깨진 json\n```") == []
    assert ca.actions("블록 없음") == []
