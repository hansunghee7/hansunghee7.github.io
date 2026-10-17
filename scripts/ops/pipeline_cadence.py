#!/usr/bin/env python3
"""
scripts/ops/pipeline_cadence.py
GitHub Actions 워크플로의 실제 성공 실행 주기를 측정하고,
데이터 기반의 신선도 감시 기준값(Freshness Threshold)을 제안하는 스크립트.

작성: 비티(안티그래비티/제미나이) 솔로 과제 #146, 탐 반영(TARGET_PIPELINES 채움).
측정·제안만 한다. watch.py·jobs.toml의 임계값은 읽거나 바꾸지 않는다(적용은 탐이 슈퍼리뷰 뒤 따로).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import statistics
import subprocess
import sys
from typing import Any

# ==============================================================================
# 측정 대상 파이프 목록 (여기에 파이프를 추가하세요)
# 튜플 구성: (저장소 "owner/repo", 워크플로 이름 "Workflow Name", 파이프 식별자)
# 값 출처: scripts/ops/jobs.toml 의 kind="gh_workflow" 수집 파이프(탐 채움 2026-10-18).
# ==============================================================================
TARGET_PIPELINES: list[tuple[str, str, str]] = [
    ("hansunghee7/hansunghee7.github.io", "Site health check", "site_health"),
    ("hansunghee7/hansunghee7.github.io", "Fetch ink queue", "ink_queue"),
    ("hansunghee7/hansunghee7.github.io", "Sync agent corpus", "sync_agent_corpus"),
    ("hansunghee7/carvit-insight-data", "Fetch YouTube deep analytics", "youtube_deep_analytics"),
    ("hansunghee7/carvit-insight-data", "Fetch Instagram insights", "instagram_insights"),
]


def intervals_hours(sorted_times: list[datetime]) -> list[float]:
    """연속된 성공 실행 시각들 사이의 간격(시간 단위)을 계산하는 순수 함수.

    Args:
        sorted_times: 시간순(오름차순)으로 정렬된 UTC datetime 리스트

    Returns:
        연속 실행 사이의 시간(h) 리스트 (소수점 둘째자리 반올림)
    """
    if len(sorted_times) < 2:
        return []

    intervals: list[float] = []
    for prev, curr in zip(sorted_times[:-1], sorted_times[1:]):
        diff_hours = (curr - prev).total_seconds() / 3600.0
        if diff_hours >= 0:
            intervals.append(round(diff_hours, 2))
    return intervals


def _calc_p90(data: list[float]) -> float:
    """외부 의존성(numpy 등) 없이 90백분위수를 계산하는 헬퍼 함수."""
    if not data:
        return 0.0
    s = sorted(data)
    idx = (len(s) - 1) * 0.90
    lower = math.floor(idx)
    upper = math.ceil(idx)
    if lower == upper:
        return s[int(idx)]
    return round(s[lower] * (upper - idx) + s[upper] * (idx - lower), 2)


def recommend_threshold(intervals: list[float]) -> dict[str, Any]:
    """관측된 간격 데이터를 바탕으로 통계 지표와 권장 신선도 기준을 계산하는 순수 함수.

    공식: recommended = math.ceil(max(관측 최대 간격 * 1.5, 중앙값 * 3))
    - 중앙값 * 3: GitHub 큐 지연이나 단발성 일시 장애로 2회 연속 누락되어도
                 경계값 거짓 경보(False Alarm)를 내지 않도록 완충.
    - 최대 간격 * 1.5: 주말·야간 스케줄 불규칙성이나 관측된 최장 배치 간격을
                      안전하게 수용하여 진짜 영구 정지만 감지.

    Args:
        intervals: 성공 실행 간 간격(h) 리스트

    Returns:
        median, mean, max, p90, recommended, comment를 포함한 딕셔너리
    """
    # 성공 표본이 3개 미만이면 간격 표본은 2개 미만이 됨
    if len(intervals) < 2:
        med = round(statistics.median(intervals), 2) if intervals else None
        avg = round(statistics.mean(intervals), 2) if intervals else None
        m_val = round(max(intervals), 2) if intervals else None
        p90_val = round(_calc_p90(intervals), 2) if intervals else None
        return {
            "median": med,
            "mean": avg,
            "max": m_val,
            "p90": p90_val,
            "recommended": None,
            "comment": "표본 부족, 기준 조정 보류",
        }

    med = round(statistics.median(intervals), 2)
    avg = round(statistics.mean(intervals), 2)
    m_val = round(max(intervals), 2)
    p90_val = round(_calc_p90(intervals), 2)

    # 공식 적용 후 시간 단위 올림
    raw_rec = max(m_val * 1.5, med * 3.0)
    rec = int(math.ceil(raw_rec))

    return {
        "median": med,
        "mean": avg,
        "max": m_val,
        "p90": p90_val,
        "recommended": rec,
        "comment": "정상 산출",
    }


def fetch_workflow_runs(repo: str, workflow: str) -> list[dict[str, Any]]:
    """GitHub CLI(gh)를 호출하여 워크플로 실행 이력을 조회."""
    cmd = [
        "gh",
        "run",
        "list",
        "-R",
        repo,
        "--workflow",
        workflow,
        "--limit",
        "100",
        "--json",
        "databaseId,conclusion,createdAt,status",
    ]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        creationflags=flags,
    )

    if proc.returncode != 0:
        raise RuntimeError(f"gh run list 실패 (exit {proc.returncode}): {proc.stderr.strip()}")

    return json.loads(proc.stdout)


def parse_success_datetimes(runs: list[dict[str, Any]]) -> list[datetime]:
    """성공 실행 건만 필터링하여 UTC datetime 리스트로 변환 및 정렬."""
    success_times: list[datetime] = []
    for r in runs:
        if r.get("conclusion") == "success":
            raw_ts = r.get("createdAt")
            if raw_ts:
                # ISO8601 포맷 파싱 (UTC 'Z' 대응)
                dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                success_times.append(dt)
    success_times.sort()
    return success_times


def parse_current_thresholds(arg_str: str | None) -> dict[str, float]:
    """CLI 인자(--current "pipe1=6,pipe2=8")를 딕셔너리로 파싱."""
    if not arg_str:
        return {}
    res: dict[str, float] = {}
    for item in arg_str.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            k, v = item.split("=", 1)
            try:
                res[k.strip()] = float(v.strip())
            except ValueError:
                pass
    return res


def main() -> None:
    parser = argparse.ArgumentParser(description="수집 파이프 신선도 기준 실측 및 권장치 산출 도구")
    parser.add_argument(
        "--current",
        type=str,
        default=None,
        help="현재 설정된 기준값 (형식: 'pipeA=6,pipeB=8')",
    )
    parser.add_argument(
        "--json",
        dest="json_mode",
        action="store_true",
        help="기계 판독용 JSON 형식으로 출력",
    )
    args = parser.parse_args()

    current_map = parse_current_thresholds(args.current)
    results: list[dict[str, Any]] = []
    failures: list[str] = []

    if not TARGET_PIPELINES:
        if args.json_mode:
            print("[]")
        else:
            print("등록된 측정 파이프가 없습니다. 스크립트 상단의 TARGET_PIPELINES를 확인하세요.")
        sys.exit(0)

    for repo, wf, pipe_name in TARGET_PIPELINES:
        try:
            raw_runs = fetch_workflow_runs(repo, wf)
            success_times = parse_success_datetimes(raw_runs)
            sample_count = len(success_times)
            intervals = intervals_hours(success_times)
            stats = recommend_threshold(intervals)

            results.append({
                "pipe": pipe_name,
                "repo": repo,
                "workflow": wf,
                "samples": sample_count,
                "median_h": stats["median"],
                "max_h": stats["max"],
                "p90_h": stats["p90"],
                "mean_h": stats["mean"],
                "current_h": current_map.get(pipe_name),
                "recommended_h": stats["recommended"],
                "comment": stats["comment"],
            })
        except Exception as e:
            failures.append(f"[{pipe_name}] ({repo}/{wf}) 조회 실패: {e}")
            results.append({
                "pipe": pipe_name,
                "repo": repo,
                "workflow": wf,
                "samples": 0,
                "median_h": None,
                "max_h": None,
                "p90_h": None,
                "mean_h": None,
                "current_h": current_map.get(pipe_name),
                "recommended_h": None,
                "comment": "조회 실패",
            })

    # 출력 단계
    if args.json_mode:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        # 사람 판독용 표 출력
        headers = ["파이프", "성공표본", "중앙값(h)", "최대(h)", "p90(h)", "현재기준(h)", "권장기준(h)", "코멘트"]
        row_fmt = "{:<16} {:>8} {:>10} {:>8} {:>8} {:>11} {:>11}  {}"
        print(row_fmt.format(*headers))
        print("-" * 92)

        for r in results:
            cur_str = f"{r['current_h']:.1f}" if r["current_h"] is not None else "-"
            rec_str = str(r["recommended_h"]) if r["recommended_h"] is not None else "-"
            med_str = f"{r['median_h']:.2f}" if r["median_h"] is not None else "-"
            max_str = f"{r['max_h']:.2f}" if r["max_h"] is not None else "-"
            p90_str = f"{r['p90_h']:.2f}" if r["p90_h"] is not None else "-"

            print(row_fmt.format(
                r["pipe"][:16],
                r["samples"],
                med_str,
                max_str,
                p90_str,
                cur_str,
                rec_str,
                r["comment"],
            ))

    # 실패 건이 있을 경우 stderr에 요약 출력 (종료 코드는 0 유지)
    if failures:
        print("\n[경고] 다음 파이프 조회가 실패하여 건너뛰었습니다:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)


if __name__ == "__main__":
    main()
