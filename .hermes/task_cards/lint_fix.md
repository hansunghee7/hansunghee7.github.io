# 카드: 린트 수정(미사용 import·변수·중복 정의)

- 호출자: 탐
- Tier: Local (왜: 저장소 소스코드는 공개지만 로컬로 충분하고 실측한 것이 이쪽이다. 문장이 장비 밖으로 나가지 않는다)
- 입력: `scripts/` 아래 파이썬 파일 중 ruff가 F401·F811·F841을 지적한 파일. 300줄 이하(로컬 모델 컨텍스트 8192토큰 한계)
- 출력: 파일별 unified diff(`.hermes/data/delegations/<시각>/`)와 요약 JSON. 결과 봉투는 `file`, `status`, `iterations`, `guard_rejects`, `findings_before`, `findings_after`(스키마 고정)
- 검증기: 봉투 스키마 + ruff 재검사(지적 0) + py_compile + 다른 규칙 오류가 늘지 않았는가. 루프 안에서는 지적된 줄만 수정, 새 이름 금지, 호출 포함 줄 삭제 금지, 블록 머리 줄 금지, 최상위 함수·클래스 보존
- 호출자의 최종 판단: 탐이 diff를 읽고 `git apply`로 적용한다. import 삭제는 모듈 부작용(import만으로 실행되는 코드)을 검증기가 못 보므로 이 단계를 뺄 수 없다
- 실패하면: 그 파일은 제안 없이 "거절"로 요약에 나오고, 탐이 직접 고친다
- 빈도: 스크립트를 자주 추가하므로 주 1회 안팎

실행: `python scripts/ops/delegate_lint.py [--path scripts] [--max-files 5] [--max-lines 300]`
첫 실측(2026-09-30): 후보 8개 중 5개 실행, 4개 제안(모두 1회차), 1개 거절, 13.8초.
