"""공고 알림 분류 시험(마야 2026-10-22). 실행: python scripts/ops/test_notice_filter.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notice_filter import classify, record_digest  # noqa: E402

CASES = [
    # 사장님 10/22 텔레그램 스크린샷에서 무관하게 걸렸던 두 공고: 이제 아무 데도 안 간다
    ("2026년 시설농업 AI로봇 실증기반 구축사업 기술지원(기술지도) 수혜기업 모집 공고", None),
    ("2026년 호남권 AX랩 지능형농업 데이터 활용 경진대회 공고(AI융합 지능형 농업 생태계 구축 사업)", None),
    # 이름 있는 프로그램은 결정이 필요할 수 있어 텔레그램
    ("2027년 창업도약패키지 일반형 신규 창업기업 모집", "core"),
    ("2026년 초격차 스타트업 프로젝트(DIPS) 2차 모집", "core"),
    ("2026년 TIPS 운영사 추가 지정 공고", "core"),
    # 우리 업종과 닿을 수 있는 것은 슈퍼인박스
    ("2026년 SaaS 개발·사업화 지원 사업 2차 모집", "digest"),
    ("AI 에이전트 서비스 개발 스타트업 지원사업 모집", "digest"),
    ("2026년 AI 바우처 공급기업 추가 모집", "digest"),
    ("클라우드 서비스 보급·확산 사업 공급기업 모집", "digest"),
    # AI 단독은 걸리지 않는다
    ("AI 교육 특강 참가자 모집", None),
    ("2026 청년 일자리 박람회 참가기업 모집", None),
    # 제외어가 있으면 digest에서 버린다
    ("제조 AI 솔루션 실증 지원사업", None),
]


def main():
    bad = 0
    for title, want in CASES:
        got = classify(title)
        ok = got == want
        bad += not ok
        print(("ok  " if ok else "FAIL"), want, got, title[:50])
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "digest.jsonl"
        record_digest("시험", "X1", "제목", "https://example.com", path=p)
        record_digest("시험", "X2", "제목2", "https://example.com/2", path=p)
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        ok = len(lines) == 2
        bad += not ok
        print(("ok  " if ok else "FAIL"), "digest 두 줄 기록", len(lines))
    print("실패", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
