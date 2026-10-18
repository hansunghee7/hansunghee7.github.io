#!/usr/bin/env python3
"""수집 데이터(JSON) 점검기 — 산출물 앞 점검기 ① (N192-②)

자동 수집 결과(JSON)가 브리핑 등에 쓰이기 전에, 빈 값·급변·누락을
**코드 기준(기계적)** 으로 걸러 경고한다. LLM 해석은 넣지 않는다.

점검 규칙:
  1. 빈 값 회귀  — 직전 날 non-null이던 소스.필드가 최신 날 null로 떨어짐(수집 실패 의심).
  2. 급변        — 판매 계열(sales_index/sales_point)은 직전 대비 비정상적으로 큰
                   비율 변동(기본 ±70%, --threshold로 조정).
                   순위 계열(*_rank)은 비율이 아니라 절대 순위 차이로 판정한다
                   (기본 50계단, --rank-jump로 조정). 순위는 1→2가 100%처럼
                   최상위권 정상 변동이 매일 오탐되므로 비율이 부적절하다.
                   리뷰 수·평점은 급변 대상에서 제외(마야 규칙과 일치).
  3. 최신 레코드 누락 소스 — history 최신 날에 아예 빠진 소스.

정책(비티·덱스 슈퍼리뷰 반영):
  점검 통과는 '승인'이 아니다. 실패 시 전면 중단이 아니라 경고 플래그를 붙여
  흘려보내는 것이 기본(pass-with-alert). --strict일 때만 경고가 있으면 exit 1.

읽기 전용 — 데이터를 수정하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

# 급변 점검 대상 필드. 판매지수·세일즈포인트(비율)와 모든 *_rank 계열(절대차).
# 리뷰 수·평점은 제외(원래 잘 안 변하므로 급변 판정 대상이 아니다).
_VELOCITY_EXACT = {"sales_index", "sales_point"}

# 순위 급변 기본 임계(계단 수). 이보다 더 크게 순위가 뛰면 급변으로 본다.
DEFAULT_RANK_JUMP = 50


def is_velocity_field(field: str) -> bool:
    """급변 점검 대상 필드인지. 판매 계열 + *_rank 계열."""
    return field in _VELOCITY_EXACT or field.endswith("_rank")


def is_rank_field(field: str) -> bool:
    """순위 계열(작을수록 좋음, 절대 순위 차이로 급변 판정)인지."""
    return field.endswith("_rank")


def _source_fields(source_value: Any) -> Dict[str, Any]:
    """소스 값이 dict이면 그대로, 아니면 빈 dict."""
    return source_value if isinstance(source_value, dict) else {}


def check_history(
    history: List[Dict[str, Any]],
    threshold: float = 0.70,
    rank_jump: int = DEFAULT_RANK_JUMP,
) -> List[Dict[str, Any]]:
    """history(레코드 리스트)를 점검해 경고 목록을 반환한다. 순수 함수.

    각 경고는 dict: {kind, source, field, prev, curr, date, detail}.
      kind: 'null_regression' | 'spike' | 'missing_source'

    급변 판정은 두 갈래:
      - 판매 계열(sales_index/sales_point): 비율 변동 > threshold.
      - 순위 계열(*_rank): 절대 순위 차이 > rank_jump(계단).
    """
    warnings: List[Dict[str, Any]] = []
    if not history or len(history) < 1:
        return warnings

    latest = history[-1]
    latest_date = latest.get("date", "?")

    # 비교용 직전 레코드(있을 때만 빈 값 회귀·급변 점검).
    prev: Optional[Dict[str, Any]] = history[-2] if len(history) >= 2 else None

    # 최신 레코드에 존재하는 소스(book/date 등 메타 제외).
    latest_sources = {
        k: v for k, v in latest.items()
        if isinstance(v, dict)
    }

    # 3) 최신 레코드 누락 소스: 직전 날엔 있었는데 최신 날 아예 빠진 소스.
    if prev is not None:
        prev_sources = {k: v for k, v in prev.items() if isinstance(v, dict)}
        for src in prev_sources:
            if src not in latest_sources:
                warnings.append({
                    "kind": "missing_source",
                    "source": src,
                    "field": None,
                    "prev": "(present)",
                    "curr": None,
                    "date": latest_date,
                    "detail": f"직전 날({prev.get('date','?')})엔 있던 소스 '{src}'가 최신 날에 없음",
                })

    if prev is None:
        return warnings

    # 1) 빈 값 회귀 + 2) 급변 — 최신·직전 공통 소스의 각 필드 비교.
    for src, latest_fields in latest_sources.items():
        prev_fields = _source_fields(prev.get(src))
        for field, curr in latest_fields.items():
            if field not in prev_fields:
                continue
            prev_val = prev_fields[field]

            # 1) 빈 값 회귀: 직전 non-null → 최신 null.
            if prev_val is not None and curr is None:
                warnings.append({
                    "kind": "null_regression",
                    "source": src,
                    "field": field,
                    "prev": prev_val,
                    "curr": None,
                    "date": latest_date,
                    "detail": f"{src}.{field} 직전 {prev_val} → 최신 null (수집 실패 의심)",
                })
                continue

            # 2) 급변: 판매·순위 계열만, 둘 다 숫자(bool 제외)일 때.
            if not is_velocity_field(field):
                continue
            if not isinstance(prev_val, (int, float)) or isinstance(prev_val, bool):
                continue
            if not isinstance(curr, (int, float)) or isinstance(curr, bool):
                continue

            if is_rank_field(field):
                # 순위 계열: 절대 순위 차이로 판정(비율은 1→2=100%처럼 오탐).
                jump = abs(curr - prev_val)
                if jump > rank_jump:
                    warnings.append({
                        "kind": "spike",
                        "source": src,
                        "field": field,
                        "prev": prev_val,
                        "curr": curr,
                        "date": latest_date,
                        "detail": f"{src}.{field} 직전 {prev_val} → 최신 {curr} (순위 {jump:.0f}계단 변동, 임계 {rank_jump}계단)",
                    })
                continue

            # 판매 계열: 비율 변동(직전이 0이면 비율 계산 불가라 건너뜀).
            if prev_val == 0:
                continue
            ratio = abs(curr - prev_val) / abs(prev_val)
            if ratio > threshold:
                warnings.append({
                    "kind": "spike",
                    "source": src,
                    "field": field,
                    "prev": prev_val,
                    "curr": curr,
                    "date": latest_date,
                    "detail": f"{src}.{field} 직전 {prev_val} → 최신 {curr} ({ratio*100:.0f}% 변동, 임계 {threshold*100:.0f}%)",
                })

    return warnings


def check_file(path: str, threshold: float = 0.70, rank_jump: int = DEFAULT_RANK_JUMP) -> Dict[str, Any]:
    """파일 하나를 읽어 점검한다. 결과 dict 반환(읽기 오류 포함)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"path": path, "error": "파일 없음", "warnings": []}
    except (json.JSONDecodeError, OSError) as e:
        return {"path": path, "error": f"읽기 실패: {e}", "warnings": []}

    history = data.get("history", []) if isinstance(data, dict) else []
    warnings = check_history(history, threshold=threshold, rank_jump=rank_jump)
    return {
        "path": path,
        "error": None,
        "records": len(history),
        "warnings": warnings,
    }


def _print_human(results: List[Dict[str, Any]]) -> None:
    for r in results:
        print(f"\n[{r['path']}]")
        if r.get("error"):
            print(f"  오류: {r['error']}")
            continue
        warns = r["warnings"]
        print(f"  레코드 {r['records']}개")
        if not warns:
            print("  이상 없음")
            continue
        for w in warns:
            label = {
                "null_regression": "빈 값 회귀",
                "spike": "급변",
                "missing_source": "소스 누락",
            }.get(w["kind"], w["kind"])
            print(f"  [경고/{label}] {w['detail']}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="수집 데이터(JSON) 점검기 — 빈 값·급변·누락을 코드 기준으로 경고")
    ap.add_argument("paths", nargs="+", help="점검할 JSON 경로(여럿 가능)")
    ap.add_argument("--threshold", type=float, default=0.70,
                    help="판매 계열 급변 비율 임계(기본 0.70 = ±70%%)")
    ap.add_argument("--rank-jump", dest="rank_jump", type=int, default=DEFAULT_RANK_JUMP,
                    help=f"순위 계열(*_rank) 급변 절대차 임계(기본 {DEFAULT_RANK_JUMP}계단)")
    ap.add_argument("--strict", action="store_true",
                    help="경고가 하나라도 있으면 exit 1(기본은 경고만 내고 exit 0)")
    ap.add_argument("--json", dest="as_json", action="store_true",
                    help="결과를 JSON으로 출력")
    args = ap.parse_args(argv)

    results = [check_file(p, threshold=args.threshold, rank_jump=args.rank_jump) for p in args.paths]
    total_warnings = sum(len(r["warnings"]) for r in results)
    any_error = any(r.get("error") for r in results)

    if args.as_json:
        print(json.dumps({
            "results": results,
            "total_warnings": total_warnings,
            "strict": args.strict,
        }, ensure_ascii=False, indent=2))
    else:
        _print_human(results)
        print(f"\n총 경고 {total_warnings}건" + (" (이상 없음)" if total_warnings == 0 else ""))

    # 정책: 기본은 pass-with-alert(경고만, exit 0). --strict면 경고/오류 시 exit 1.
    if args.strict and (total_warnings > 0 or any_error):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
