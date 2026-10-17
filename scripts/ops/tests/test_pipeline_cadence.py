"""pipeline_cadence.py 순수 함수 시험. 네트워크·gh 호출 없음.

작성: 비티(안티그래비티/제미나이) 솔로 과제 #146, 탐이 저장소 import 관행에 맞춤.
"""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline_cadence import intervals_hours, recommend_threshold  # noqa: E402


def test_intervals_hours_standard():
    """연속 datetime 목록에서 시간 단위 간격 계산."""
    base = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    times = [
        base,
        base + timedelta(hours=1, minutes=30),
        base + timedelta(hours=3, minutes=30),
        base + timedelta(hours=6, minutes=45),
    ]
    assert intervals_hours(times) == [1.5, 2.0, 3.25]


def test_intervals_hours_too_few():
    """표본 1개 이하면 간격은 빈 리스트."""
    base = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    assert intervals_hours([]) == []
    assert intervals_hours([base]) == []


def test_recommend_threshold_normal_calculation():
    """정상 표본: max(p90*1.5, median*3) 올림. [1,2,2,5] -> p90=4.1, max(6.15,6.0)=6.15 -> 7."""
    result = recommend_threshold([1.0, 2.0, 2.0, 5.0])
    assert result["recommended"] == 7
    assert result["median"] == 2.0
    assert result["max"] == 5.0
    assert result["p90"] == 4.1
    assert result["comment"] == "정상 산출"


def test_recommend_threshold_median_dominates():
    """중앙값*3이 최대*1.5보다 클 때. [3,3,3,3] -> max(4.5,9.0)=9.0 -> 9."""
    result = recommend_threshold([3.0, 3.0, 3.0, 3.0])
    assert result["recommended"] == 9


def test_recommend_threshold_insufficient_samples():
    """표본 부족(간격 2개 미만): 권장 보류."""
    r1 = recommend_threshold([4.0])
    assert r1["recommended"] is None
    assert r1["comment"] == "표본 부족, 기준 조정 보류"

    r2 = recommend_threshold([])
    assert r2["recommended"] is None
    assert r2["comment"] == "표본 부족, 기준 조정 보류"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK {name}")
    print("단위 시험 통과.")
