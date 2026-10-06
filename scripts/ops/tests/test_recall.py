"""recall.py의 순수 함수(tokens, render)와 query 단위 시험.

build()는 opsdb(수파베이스)를 부르므로 건드리지 않는다. query()는 로컬 캐시
파일(recall.CACHE, 원래 윈도우 경로 하드코딩)만 읽으므로 네트워크·DB 호출이
없다 — recall.CACHE를 tmp_path 파일로 monkeypatch해서 완전히 격리한다.

실행: python -m pytest scripts/ops/tests/test_recall.py -v
"""
import importlib.util
import json
from pathlib import Path

OPS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("recall_under_test", OPS / "recall.py")
recall = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recall)


# ---------------------------------------------------------------------------
# tokens(text)
# ---------------------------------------------------------------------------

def test_tokens_strips_josa_and_filters_stopwords():
    assert recall.tokens("사장님이 측정 기준을 정했다") == ["측정", "기준", "정했다"]


def test_tokens_empty_string_returns_empty_list():
    assert recall.tokens("") == []


def test_tokens_only_stopwords_returns_empty_list():
    assert recall.tokens("그냥 이제 그리고") == []


def test_tokens_deduplicates_preserving_first_order():
    assert recall.tokens("측정 측정 기준") == ["측정", "기준"]


# ---------------------------------------------------------------------------
# render(res)
# ---------------------------------------------------------------------------

def test_render_formats_cards_and_boss_lines():
    res = {
        "cards": [
            {"p": "탐", "no": "N1", "t": "제목", "d": "설명", "b": "사장님 말"},
            {"p": "노트", "no": "N2", "t": "둘째", "d": "", "b": ""},
        ],
        "boss": [{"at": "2026-10-06 10:00:00", "w": "탐", "x": "사장님이 한 말"}],
    }
    lines = recall.render(res)
    assert lines[0] == "· 공정 카드 [탐#N1] 제목 ★사장님: 사장님 말"
    assert lines[1] == "· 공정 카드 [노트#N2] 둘째"  # 사장님 발언(b)이 없으면 꼬리가 안 붙는다
    assert lines[2] == "· 사장님이 2026-10-06 10:00에 한 말: 사장님이 한 말"


def test_render_empty_result_returns_empty_list():
    assert recall.render({"cards": [], "boss": []}) == []


# ---------------------------------------------------------------------------
# query(text, n_cards=3, n_boss=3, min_hits=2)  -- recall.CACHE를 monkeypatch
# ---------------------------------------------------------------------------

def _write_cache(path):
    data = {
        "at": "2026-10-06 10:00:00",
        "cards": [
            {"p": "탐", "no": "N1", "t": "브라우저 임대 정책", "d": "임대 정책 설명", "b": "사장님이 브라우저 임대를 정했다"},
            {"p": "노트", "no": "N2", "t": "전혀 다른 주제", "d": "상관없음", "b": ""},
        ],
        "boss": [
            {"at": "2026-10-05 09:00:00", "w": "탐", "x": "브라우저 임대 정책은 이렇게 간다"},
            {"at": "2026-10-06 09:00:00", "w": "탐", "x": "상관없는 다른 이야기"},
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_query_matches_relevant_card_and_boss_line(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    _write_cache(cache)
    monkeypatch.setattr(recall, "CACHE", cache)
    res = recall.query("브라우저 임대 정책 어떻게 돼?")
    assert [c["no"] for c in res["cards"]] == ["N1"]
    assert res["boss"][0]["x"] == "브라우저 임대 정책은 이렇게 간다"


def test_query_missing_cache_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(recall, "CACHE", tmp_path / "없음.json")
    assert recall.query("아무 질문") is None


def test_query_corrupt_cache_returns_none(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    cache.write_text("{broken json", encoding="utf-8")
    monkeypatch.setattr(recall, "CACHE", cache)
    assert recall.query("브라우저 임대") is None


def test_query_too_few_tokens_returns_empty_without_reading_cache(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    _write_cache(cache)
    monkeypatch.setattr(recall, "CACHE", cache)
    assert recall.query("음") == {"cards": [], "boss": [], "q": []}
