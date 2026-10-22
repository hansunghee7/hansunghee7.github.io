"""import_ops_tables.parse_project_tables 시험(임시 문서만 읽음, DB 접속 없음)."""
import sys
from pathlib import Path

OPS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPS))
import import_ops_tables as m  # noqa: E402

HDR = '| 순서 | 항목 | 상태 | PR | CI | 다음 단계 |\n|---|---|---|---|---|---|\n'


def doc(tmp_path, text, name='샘플_슈퍼프로젝트.md'):
    p = tmp_path / name
    p.write_text(text, encoding='utf-8')
    return p


def test_normal_table(tmp_path):
    p = doc(tmp_path, '# 제목\n\n## 진행표 (규칙)\n\n' + HDR + '| 0 |  관문  | 병합 완료 | - | 통과 | 없음 |\n| A | 치환 | 대기 | 12 | - | 내일 |\n\n## 다음 절\n')
    r = m.parse_project_tables([p])
    assert len(r) == 2
    assert r[0] == {'project': '샘플', 'ord': 1, 'step_no': '0', 'item': '관문', 'status': '병합 완료', 'pr': '-', 'ci': '통과', 'next': '없음', 'source': p.as_posix()}
    assert r[1]['ord'] == 2 and r[1]['step_no'] == 'A' and r[1]['pr'] == '12'


def test_separator_and_blank_rows(tmp_path):
    p = doc(tmp_path, '## 진행표\n' + HDR + '|---|---|---|---|---|---|\n| | | | | | |\n| 1 | x | y | - | - | z |\n')
    r = m.parse_project_tables([p])
    assert [x['step_no'] for x in r] == ['1'] and r[0]['ord'] == 1


def test_no_section(tmp_path):
    p = doc(tmp_path, '## 다른 절\n' + HDR + '| 1 | x | y | - | - | z |\n')
    assert m.parse_project_tables([p]) == []


def test_other_header_ignored(tmp_path):
    p = doc(tmp_path, '## 진행표\n| 이름 | 값 |\n|---|---|\n| a | b |\n\n' + HDR + '| 1 | x | y | - | - | z |\n')
    r = m.parse_project_tables([p])
    assert len(r) == 1 and r[0]['item'] == 'x'


def test_simple_cells_and_missing_file(tmp_path):
    p = doc(tmp_path, '## 진행표\n' + HDR + '| 2 | 항목 둘 | 막힘 | - | - |\n')
    r = m.parse_project_tables([p, tmp_path / '없음.md'])
    assert len(r) == 1 and r[0]['next'] == '' and r[0]['status'] == '막힘'
