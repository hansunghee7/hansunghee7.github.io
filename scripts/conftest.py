"""scripts/ 전체를 'python3 -m pytest scripts -q'로 돌릴 때 수집 범위를 정리한다.

scripts/ops/ 바로 아래의 test_*.py 들은 pytest 테스트가 아니라 독립 실행
스크립트다(assert 함수 모음이 아니라 모듈 최상위에서 바로 실행하고
sys.exit()으로 끝난다. 예: scripts/ops/test_denied_notify.py). pytest가
파일명 패턴만 보고 이들을 수집하면 모듈 임포트 중 sys.exit()이 호출되어
전체 수집이 INTERNALERROR로 멈춘다. 실제 pytest 테스트는
scripts/ops/tests/ 아래에 있으므로 거기는 그대로 수집한다(.github/workflows/
build-check.yml의 `python3 -m pytest scripts/ops/tests -q`와 동일 범위).

주의: pytest의 collect_ignore_glob은 fnmatch로 매칭되고 fnmatch의 '*'는
'/'도 그냥 삼킨다(경로 인식 glob이 아님). 그래서 "ops/*.py" 패턴을 쓰면
"ops/tests/test_foo.py"처럼 하위 폴더 파일까지 재귀적으로 걸려
scripts/ops/tests/가 전부 무시되고 CI의 '운영 스크립트 시험' 단계가
"no tests ran"으로 실패한다(2026-10 발견). 그래서 와일드카드 패턴 대신
ops 바로 아래의 실제 test_*.py 파일명만 나열한다 -- 글자 그대로 비교되므로
하위 폴더로 번질 여지가 없다.
"""
from pathlib import Path

_OPS_DIR = Path(__file__).resolve().parent / "ops"
collect_ignore_glob = sorted(
    f"ops/{p.name}" for p in _OPS_DIR.glob("test_*.py")
) if _OPS_DIR.is_dir() else []
