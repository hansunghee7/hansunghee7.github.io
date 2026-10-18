"""fetch_book_insight.py 병합 로직 순수 함수 시험(네트워크·파일·playwright 없음).

병합 규칙(마야 확정 2026-10-18, 탐 #156): 그날 첫 성공값이 정본, 뒤 실행은 빈칸만
채우고 덮어쓰지 않는다. 0은 실제 값이라 보존. 다른 non-null은 later_values에 진단 기록.
실행: python -m pytest scripts/test_fetch_book_insight.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_book_insight import merge_day_record, upsert, mark_suspect_stale  # noqa: E402

AT = "2026-10-18T07:01"


def test_null_does_not_overwrite_good_value():
    """① 기존 yes24.sales_point=588, 새 실행 null -> 588 유지, later_values 없음."""
    existing = {"date": "2026-10-18", "yes24": {"sales_point": 588, "reviews": 12}}
    incoming = {"date": "2026-10-18", "yes24": {"sales_point": None, "reviews": 12}}
    out = merge_day_record(existing, incoming, AT)
    assert out["yes24"]["sales_point"] == 588
    assert "later_values" not in out


def test_different_nonnull_kept_and_logged():
    """② 기존 millie.category_rank=85, 새 실행 55 -> 85 유지 + later_values 기록."""
    existing = {"date": "2026-10-18", "millie": {"category_rank": 85}}
    incoming = {"date": "2026-10-18", "millie": {"category_rank": 55}}
    out = merge_day_record(existing, incoming, AT)
    assert out["millie"]["category_rank"] == 85
    assert out["later_values"] == [{"field": "millie.category_rank", "value": 55, "at": AT}]


def test_zero_is_real_value_not_overwritten():
    """③ 기존 reviews=0, 새 실행 5 -> 0 유지(0은 실제 값)."""
    existing = {"date": "2026-10-18", "millie": {"reviews": 0}}
    incoming = {"date": "2026-10-18", "millie": {"reviews": 5}}
    out = merge_day_record(existing, incoming, AT)
    assert out["millie"]["reviews"] == 0
    assert out["later_values"] == [{"field": "millie.reviews", "value": 5, "at": AT}]


def test_blank_filled_without_later_values():
    """④ 기존 rating=None, 새 실행 9.2 -> 9.2로 채움, later_values 없음."""
    existing = {"date": "2026-10-18", "yes24": {"rating": None}}
    incoming = {"date": "2026-10-18", "yes24": {"rating": 9.2}}
    out = merge_day_record(existing, incoming, AT)
    assert out["yes24"]["rating"] == 9.2
    assert "later_values" not in out


def test_missing_source_filled_whole():
    """소스 자체가 없으면 통째로 채운다(새 값 None 아님)."""
    existing = {"date": "2026-10-18", "yes24": {"sales_point": 588}}
    incoming = {"date": "2026-10-18", "yes24": {"sales_point": 588}, "millie": {"category_rank": 55}}
    out = merge_day_record(existing, incoming, AT)
    assert out["millie"] == {"category_rank": 55}
    assert "later_values" not in out


def test_upsert_new_date_appends():
    """⑤ 새 날짜 -> 그대로 append + 날짜 정렬."""
    history = [{"date": "2026-10-17", "yes24": {"sales_point": 100}}]
    upsert(history, "2026-10-18", {"date": "2026-10-18", "yes24": {"sales_point": 200}})
    assert [h["date"] for h in history] == ["2026-10-17", "2026-10-18"]
    assert history[-1]["yes24"]["sales_point"] == 200


def test_upsert_same_date_merges_not_replaces():
    """같은 날짜 재실행: 통째 교체가 아니라 빈칸만 채움."""
    history = [{"date": "2026-10-18", "yes24": {"sales_point": 588, "rating": None}}]
    upsert(history, "2026-10-18", {"date": "2026-10-18", "yes24": {"sales_point": None, "rating": 9.0}}, at=AT)
    assert history[0]["yes24"]["sales_point"] == 588   # 덮어쓰기 안 함
    assert history[0]["yes24"]["rating"] == 9.0        # 빈칸 채움


def test_suspect_stale_marks_three_day_identical():
    """최근 3일 동일 non-null -> suspect_stale 표시."""
    history = [
        {"date": "2026-10-16", "yes24": {"sales_point": 588}},
        {"date": "2026-10-17", "yes24": {"sales_point": 588}},
        {"date": "2026-10-18", "yes24": {"sales_point": 588}},
    ]
    mark_suspect_stale(history)
    assert history[-1]["suspect_stale"] == ["yes24.sales_point"]


def test_suspect_stale_absent_when_changing():
    """값이 변하면 표시 안 함."""
    history = [
        {"date": "2026-10-16", "yes24": {"sales_point": 100}},
        {"date": "2026-10-17", "yes24": {"sales_point": 200}},
        {"date": "2026-10-18", "yes24": {"sales_point": 300}},
    ]
    mark_suspect_stale(history)
    assert "suspect_stale" not in history[-1]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("단위 시험 통과.")
