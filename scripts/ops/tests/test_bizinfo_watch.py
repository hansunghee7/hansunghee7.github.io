# -*- coding: utf-8 -*-
"""기업마당 감시 파서 시험(2026-10-15 탐). 네트워크 없이 샘플 HTML로 목록 파싱과 키워드 일치만 확인한다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bizinfo_watch as bw  # noqa: E402

SAMPLE = '''<td class="t_l"><a href= "/sii/siia/selectSIIA200Detail.do?rows=15&pblancId=PBLN_000000000000001" title="2026년 AI 바우처 지원사업 공고"> 2026년 AI 바우처 </a></td>
<td class="t_l"><a href= "/sii/siia/selectSIIA200Detail.do?rows=15&pblancId=PBLN_000000000000002" title="[서울] 소상공인 컨설팅 &amp; 교육"> [서울] 소상공인 </a></td>
<td class="t_l"><a href= "/sii/siia/selectSIIA200Detail.do?rows=15&pblancId=PBLN_000000000000001" title="중복 제목 무시"> 중복 </a></td>'''


def test_parse_extracts_ids_and_titles_dedup():
    items = bw.parse(SAMPLE)
    assert items == [("PBLN_000000000000001", "2026년 AI 바우처 지원사업 공고"), ("PBLN_000000000000002", "[서울] 소상공인 컨설팅 & 교육")]


def test_parse_empty_returns_empty_list():
    assert bw.parse("<html>구조가 바뀐 페이지</html>") == []


def test_hit_matches_keywords_case_insensitive():
    assert "AI" in bw.hit("2026 ai 바우처")
    assert bw.hit("소상공인 컨설팅") == []
