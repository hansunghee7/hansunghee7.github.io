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
