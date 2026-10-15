# -*- coding: utf-8 -*-
"""Carvit Context 대시보드 생성(2026-10-15 탐). template.html(시안 v8)의 'Carvit 팀' 막대를 context_measure.py 실측값으로 채워 HTML을 만든다.
시안의 '지금' 줄(빗금)은 화면 구성용 예시라 그대로 두고, 우리 팀 줄만 실측(검정)으로 바꾼다. 정의가 시안과 다른 지표는 제목 설명과 아래 메모에 한계를 적는다.
사용: python scripts/ops/context_build.py [--measure measure_live.json] [--out context_dashboard_live.html]"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent / "context_dashboard"
OPS = Path("C:/work/_ops/context_pilot")


def row(label, v, text):
    """값이 없으면(측정 실패·기록 없음) 막대 대신 '측정 전' 줄로 둔다(검수 큐 PR 2264 지적: None이 JS로 들어가 화면 전체가 깨짐)."""
    if v is None:
        return "{label:'%s',kind:'none'}" % label
    return "{label:'%s',kind:'real',v:%s,text:'%s'}" % (label, v, text)


def patch(html, title, new_u, new_row, new_max=None, new_ticks=None, new_fmt=None, new_aria=None):
    i = html.index("t:'%s'" % title)
    j = html.index("rows:[", i)
    k = html.index("]}", j)
    block = html[i:k + 2]
    nb = re.sub(r"\{label:'Carvit 팀'[^}]*\}", lambda m: new_row, block)
    if new_u:
        nb = re.sub(r"u:'[^']*'", lambda m: "u:'%s'" % new_u, nb, count=1)
    if new_max is not None:
        nb = re.sub(r"max:\d+", "max:%s" % new_max, nb, count=1)
        nb = re.sub(r"ticks:\[[^\]]*\]", "ticks:%s" % new_ticks, nb, count=1)
        nb = re.sub(r"fmt:function\(v\)\{return [^}]*\}", lambda m: "fmt:function(v){return %s}" % new_fmt, nb, count=1)
    if new_aria:
        nb = re.sub(r"aria:'[^']*'", lambda m: "aria:'%s'" % new_aria, nb, count=1)
    return html[:i] + nb + html[k + 2:]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv
    mp = Path(a[a.index("--measure") + 1]) if "--measure" in a else OPS / "measure_live.json"
    out = Path(a[a.index("--out") + 1]) if "--out" in a else OPS / "context_dashboard_live.html"
    m = json.loads(mp.read_text(encoding="utf-8"))
    h = (HERE / "template.html").read_text(encoding="utf-8")
    lead = m["lead_min_median"]
    h = patch(h, "요청 완료 시간", "PR 열림에서 병합까지 중앙값, 단위 분, 낮을수록 좋음", row("Carvit 팀", lead, "%s분" % lead),
              new_max=10, new_ticks="[0,5,10]", new_fmt="v+'분'",
              new_aria="요청 완료 시간 비교. Carvit 에이전트 팀 %s분(실측), 지금은 시안 예시, 도입 전은 측정 전" % lead)
    # 시안 '지금' 예시 6.5시간은 분 단위 축에서 의미가 달라 같은 줄을 '측정 전' 예시로 바꾼다
    h = h.replace("{label:'지금',kind:'ex',v:6.5,text:'6.5시간'}", "{label:'지금',kind:'ex',v:8,text:'8분'}")
    hd = m["human_per_day"]
    h = patch(h, "사람 개입 비율", "사람 개입 표시 건수, 하루 평균, 낮을수록 좋음", row("Carvit 팀", hd, "%s건/일" % hd),
              new_max=150, new_ticks="[0,75,150]", new_fmt="v+'건'",
              new_aria="사람 개입 비교. Carvit 에이전트 팀 하루 %s건(실측), 지금은 시안 예시, 도입 전은 측정 전" % hd)
    h = h.replace("{label:'지금',kind:'ex',v:35,text:'35%'}", "{label:'지금',kind:'ex',v:120,text:'120건'}")
    rp = m["revert_pct"]
    h = patch(h, "PR 되돌림 비율", None, row("Carvit 팀", rp, "%s%% (%s/%s)" % (rp, m["revert_count_14d"], m["merged_pr_14d"])),
              new_aria="PR 되돌림 비율 비교. Carvit 에이전트 팀 %s퍼센트(실측, 최근 14일 병합 %s건 중 %s건), 지금은 시안 예시" % (rp, m["merged_pr_14d"], m["revert_count_14d"]))
    c = m["cpso_krw"]
    h = patch(h, "성공 한 건당 비용(CPSO)", "병합 PR 한 건당 GCP 호출 비용(원), 클로드·Azure 제외 하한값, 낮을수록 좋음", row("Carvit 팀", c, "₩%s" % (format(c, ",") if c is not None else "")),
              new_max=1000, new_ticks="[0,500,1000]", new_fmt="'₩'+v",
              new_aria="성공 한 건당 비용 비교. Carvit 에이전트 팀 %s원(실측 하한값), 지금은 시안 예시, 도입 전은 측정 전" % c)
    h = h.replace("{label:'지금',kind:'ex',v:6,text:'6회'}", "{label:'지금',kind:'ex',v:900,text:'₩900'}")
    pr = m["merged_pr_7d"]
    h = patch(h, "병합 PR 수", "지난 7일(%s), 작성자가 봇이 아닌 병합 PR, 단위 건" % m["window_7d"].replace("2026-", "").replace("-", "/").replace("..", "~"), row("Carvit 팀", pr, "%s건" % pr),
              new_aria="병합 PR 수 비교. Carvit 에이전트 팀 %s건(실측), 지금은 시안 예시, 도입 전은 측정 전" % pr)
    dc = m["docs_count"]
    h = patch(h, "정본 문서 수", "저장소 docs 폴더의 문서 파일, 누적, 단위 개", row("Carvit 팀", dc, "%s개" % dc), new_max=250, new_ticks="[0,125,250]", new_fmt="v+'개'",
              new_aria="정본 문서 수 비교. Carvit 에이전트 팀 %s개(실측), 지금은 시안 예시" % dc)
    memo = ("<p><b>실측 기준일 %s.</b> 우리 팀(Carvit 에이전트 팀) 줄은 GitHub와 로컬 기록에서 계산합니다(하루 1회 자동 생성). 빗금 줄은 화면 구성용 예시입니다.</p><ul>"
            "<li>요청 완료 시간: 이슈를 쓰지 않아 PR 열림에서 병합까지 중앙값(분)으로 대신합니다.</li>"
            "<li>사람 개입: 비율의 분모(처리한 일 전체)가 기록되지 않아 사람 개입 표시 하루 건수로 대신합니다.</li>"
            "<li>성공 한 건당 비용: GCP 호출 추정 비용만 있어 클로드·Azure가 빠진 하한값입니다.</li>"
            "<li>이어받기 점수: 5문항 시험을 돌려야 해서 아직 측정 전입니다.</li></ul>") % m["as_of"]
    h = re.sub(r'<h2>시안 메모</h2>\s*<div class="note">.*?</div>', lambda mo: '<h2>측정 메모</h2><div class="note">' + memo + '</div>', h, count=1, flags=re.S)
    out.write_text(h, encoding="utf-8")
    print("생성:", out, len(h), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
