# -*- coding: utf-8 -*-
"""Carvit Context 대시보드, 고객 대표 시점 시안 생성(2026-10-15 탐, 사장님: "지투시그마 손지인 대표님이 보는 형태로, 지투시그마 에이전트가 주인공, 카빗 에이전트가 비교치").
context_build.py가 만든 live HTML을 받아 막대 순서를 [고객 팀(주인공), Carvit 팀(비교), 도입 전]으로 바꾸고 고객 팀 줄을 예시 숫자(빗금)로 둔다.
고객 데이터 규칙(메모리: 고객 데이터 노출 절대 금지, 실험 화면은 가상 데이터만): 고객 팀 숫자는 가상 예시이고, 얼리 액세스 이용계약 전에는 고객 기록을 읽지 않는다.
사용: python scripts/ops/context_build_customer.py [--in live.html] [--out zitu.html] [--name 지투시그마]"""
import re
import sys
from pathlib import Path

OPS = Path("C:/work/_ops/context_pilot")
# 가상 예시값(제목 → (값, 표기)). 실제 연결되면 고객이 API로 보낸 기록으로 교체한다.
SAMPLE = {
    "교신 가능 에이전트 수": (2, "2명"),
    "병합 PR 수": (24, "24건"),
    "정본 문서 수": (31, "31개"),
    "요청 완료 시간": (6, "6분"),
    "사람 개입 비율": (12, "12건"),
    "이어받기 점수": None,
    "PR 되돌림 비율": (2.1, "2.1%"),
    "성공 한 건당 비용(CPSO)": (520, "₩520"),
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv
    src = Path(a[a.index("--in") + 1]) if "--in" in a else OPS / "context_dashboard_live.html"
    out = Path(a[a.index("--out") + 1]) if "--out" in a else OPS / "context_dashboard_zitu.html"
    name = a[a.index("--name") + 1] if "--name" in a else "지투시그마"
    h = src.read_text(encoding="utf-8")

    def fix_rows(m):
        block = m.group(0)
        title = re.search(r"t:'([^']*)'", block)
        # 이 블록 앞의 제목을 찾기 위해 바깥에서 처리한다(아래 루프)
        return block

    pos = 0
    res = []
    for mt in re.finditer(r"\{t:'([^']*)'.*?rows:\[(.*?)\]\}", h, flags=re.S):
        title = mt.group(1)
        rows = mt.group(2)
        carvit = re.search(r"\{label:'Carvit 팀'[^}]*\}", rows)
        carvit_row = carvit.group(0).replace("label:'Carvit 팀'", "label:'Carvit 비교'") if carvit else "{label:'Carvit 비교',kind:'none'}"
        s = SAMPLE.get(title)
        mine = "{label:'%s',kind:'none'}" % name if s is None else "{label:'%s',kind:'ex',v:%s,text:'%s'}" % (name, s[0], s[1])
        new_rows = "%s,%s,{label:'도입 전',kind:'none'}" % (mine, carvit_row)
        res.append((mt.start(2), mt.end(2), new_rows))
    for st, en, nr in reversed(res):
        h = h[:st] + nr + h[en:]
    h = h.replace("내 계정 · 에이전트 팀 1개 연결됨", "%s · 에이전트 팀 1개 연결 예정" % name)
    h = re.sub(r'<p class="lead">.*?</p>', '<p class="lead">%s 에이전트 팀이 일을 얼마나 빨리, 얼마나 사람 손 없이, 얼마나 되돌림 없이 해냈는지를, 비교 기준인 Carvit 에이전트 팀과 나란히 놓고 봅니다.</p>' % name, h, count=1, flags=re.S)
    h = h.replace("<title>Carvit Context 대시보드</title>", "<title>Carvit Context 고객 시점 시안</title>")
    h = re.sub(r'<h2>측정 메모</h2><div class="note">.*?</div>', '<h2>시안 메모</h2><div class="note"><p><b>%s 줄은 가상 예시 숫자(빗금)입니다.</b> 연결 전이라 실제 기록이 아니며, 이용계약 뒤 고객이 보낸 기록으로 바뀝니다. 그 전에는 고객 기록을 읽지 않습니다.</p><ul><li>Carvit 비교 줄(검정)은 우리 팀의 실제 기록입니다(최근 7일).</li><li>막대는 짧을수록 좋은 것(완료 시간, 개입, 되돌림, 비용)과 길수록 좋은 것(이어받기 점수)이 섞여 있어 각 그래프 제목 아래에 방향을 적었습니다.</li><li>이어받기 점수는 5문항 시험이 필요해 두 팀 모두 측정 전입니다.</li></ul></div>' % name, h, count=1, flags=re.S)
    out.write_text(h, encoding="utf-8")
    print("생성:", out, len(h), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
