# -*- coding: utf-8 -*-
import importlib.util
from datetime import datetime
from pathlib import Path

spec = importlib.util.spec_from_file_location("tami_watch", Path(__file__).resolve().parents[1] / "tami_watch.py")
tw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tw)
NOW = datetime(2026, 10, 15, 22, 30)


def test_factory_flags_stale_read_and_idle_credits():
    csv = ("account,pc,credits,read_at,reset_kst,last_new_cut,last_tick,note\n"
           "a,구PC,2,10-15 20:00,-,10-15 21:00,10-15 22:00,ok\n"
           "b,신PC,26,10-15 07:58,-,10-15 00:51,10-15 22:00,남은 씬 없음\n")
    out = tw.factory_anomalies(csv, NOW)
    assert len(out) == 2 and all("[신PC b]" in x for x in out)


def test_factory_bad_format_reports_once():
    assert tw.factory_anomalies("오류", NOW) == ["공장 장부를 읽지 못함(fit_db.py factory 출력 형식 다름)"]


def test_status_reads_only_red_lines():
    text = "| 상태 | 항목 | 내용 | 시작 |\n| 🔴 | 감시A | 종료 코드 2 | x |\n| 🟡 | 감시B | 늦음 | y |\n"
    assert tw.status_anomalies(text) == ["[수집·주기 작업] 감시A — 종료 코드 2"]


def test_pipeline_stale_and_owner_routing():
    rows = [{"slug": "a", "name": "파이프A", "owner": "마야", "status": "작동", "freshness_hours": 24, "last_success": "2026-10-13T10:00:00+09:00"},
            {"slug": "b", "name": "파이프B", "owner": "탐", "status": "작동", "freshness_hours": 24, "last_success": "2026-10-15T20:00:00+09:00"},
            {"slug": "c", "name": "파이프C", "owner": "탐", "status": "중단", "freshness_hours": 24, "last_success": None}]
    out = tw.pipeline_anomalies(rows, NOW)
    assert len(out) == 1 and out[0].startswith("[수집 파이프·마야] 파이프A")
    many = [dict(rows[0], slug=str(i), last_success="2026-10-11T10:00:00+09:00") for i in range(6)]
    assert len(tw.pipeline_anomalies(many, NOW)) == 1 and "함께 멈춤" in tw.pipeline_anomalies(many, NOW)[0]
    assert tw.owner_of(out[0]) == "마야"
    assert tw.owner_of("[신PC u5] 크레딧") == "핏"
    assert tw.owner_of("[수집·주기 작업] x") == "탐"


def test_fell_back_detects_credit_refusal_and_fallback(tmp_path):
    import tami_watch as t
    log = tmp_path / "agent.log"
    log.write_text("old line Fallback activated: a → b\n", encoding="utf-8")
    start = log.stat().st_size
    assert t.fell_back(log, start) == ""
    with open(log, "a", encoding="utf-8") as f:
        f.write("x Your credit balance is too low to access\n")
    assert "크레딧" in t.fell_back(log, start)
    log2 = tmp_path / "b.log"
    log2.write_text("y Fallback activated: qwen → nemotron\n", encoding="utf-8")
    assert "대체 모델" in t.fell_back(log2, 0)
