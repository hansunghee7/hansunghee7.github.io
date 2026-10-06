"""scripts/ 전체를 'python3 -m pytest scripts -q'로 돌릴 때 수집 범위를 정리한다.

scripts/ops/ 바로 아래의 test_*.py 들은 pytest 테스트가 아니라 독립 실행
스크립트다(assert 함수 모음이 아니라 모듈 최상위에서 바로 실행하고
sys.exit()으로 끝난다. 예: scripts/ops/test_denied_notify.py). pytest가
파일명 패턴만 보고 이들을 수집하면 모듈 임포트 중 sys.exit()이 호출되어
전체 수집이 INTERNALERROR로 멈춘다. 실제 pytest 테스트는
scripts/ops/tests/ 아래에 있으므로 거기는 그대로 수집한다(.github/workflows/
build-check.yml의 `python3 -m pytest scripts/ops/tests -q`와 동일 범위).
"""
collect_ignore_glob = ["ops/*.py"]
