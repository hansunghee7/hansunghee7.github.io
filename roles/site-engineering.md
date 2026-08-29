# site-engineering — hansunghee7.github.io 저장소 실무 엔지니어링 스레드

## ① 목적과 범위
전략/카피 결정이 아니라 **hansunghee7.github.io(simplifier.co.kr) 저장소의 실제 코드 작업**을 담당하는 스레드. 홈페이지 UX·성능 개선, Simplifier Studio(관리자 내부 도구, `insight-7b3e9f2c/`) 구축·유지보수, 저장소 인프라/문서 정리, 배포 사고 대응이 핵심 영역. CXO/CMO/메타운영([[claude-code-ops]]) 같은 전략·상담 스레드와 달리, 파일을 직접 읽고 고치고 커밋·배포까지 확인하는 실무형 스레드.

## ② 확정된 주요 결정사항
- **`index.html`/`preview/index.html` 완전 중복 해소**: 헤드 메타(title/description/canonical)만 남기고 나머지 전체를 `_includes/home-body.html`로 통합, `is_staging` 파라미터로 헤더 include만 분기. 라이브 검증 완료.
- **홈 스크롤 fade 메커니즘 리팩터**: 매 스크롤 프레임마다 `style.opacity`를 강제로 다시 쓰던 방식 → 경계 넘을 때 클래스 하나만 토글하고 실제 애니메이션은 CSS transition에 맡기는 방식으로 교체(FPS 실측 검증 완료).
- **저장소 구조/외부연동 전수 감사** 완료 → Simplifier Studio에 **"시스템 구조"**(`system-map.html`) 페이지로 상시 게시. **CLAUDE.md에 "인프라 바뀌면 이 페이지도 같이 갱신" 원칙이 명문화됨** — 지키지 않으면 나중에 사장님이 직접 발견해 지적하는 사례가 이미 한 번 있었음.
- **저장소 정리**: 아무 데서도 참조 안 되는 죽은 파이썬 스크립트 9개 삭제, 실사용 파이프라인 스크립트를 `scripts/`로 위치 통일, 기획 문서를 `docs/`로, 브런치 원본 CSV를 `archive/`로 이동.
- **Studio 모바일 내비게이션**: 가로 스크롤 알약 줄 → 햄버거 버튼 + 드롭다운으로 교체(`studio.css`/`studio.js` 공용, 전 페이지 자동 반영).
- **"통합 UX 가이드" 신설**: 기존 "스타일 가이드"(홈페이지 전용, 실측값)와 `docs/UX_GUIDE.md`(공개 사이트+스튜디오 공통 원칙)를 병합해 `insight-7b3e9f2c/style-guide.html`(메뉴명 "통합 UX 가이드")로 통합. `docs/UX_GUIDE.md`가 마크다운 정본, `style-guide.html`이 그걸 사람이 읽는 렌더링 — 자동 동기화 없음, 고칠 때 양쪽 다 손대야 함.
- **심각 인시던트 대응**: `docs/UX_GUIDE.md` 추가 직후 GitHub Pages "Build with Jekyll"이 1시간 넘게 연속 실패(저장소에 `_config.yml`이 없어 front matter 없는 `.md`까지 `jekyll-optional-front-matter`가 정식 페이지로 취급해 Liquid/kramdown 전체 파이프라인을 태우는 게 근본 원인으로 추정 — Actions 로그가 비공개라 원문 예외 메시지까지는 확인 못함). `_config.yml`을 신설해 `docs/`·`CLAUDE.md`·`STYLE_GUIDE.md`·README 2개를 빌드 대상에서 제외해 해결, 배포 정상화 확인. 같은 시각 다른 세션도 `UX_GUIDE.md` 안 `{% include %}` 표기를 raw로 감싸는 콘텐츠 수정으로 독립 대응 — 두 수정이 충돌 없이 합쳐짐.
- **Studio 페이지 폭(width) 불일치 검토**: "UX 총괄" 입장에서 코멘트 요청받아 실측 데이터(1100/1200/1600/760px 4종 혼재)를 근거로 평가 — ask.html·style-guide.html의 760px(대화·긴글 가독성)과 book-insight.html의 1600px(2열 비교 그리드)은 정당, system-map.html의 1200px은 근거 없는 임의값이라고 지적. 사용자가 "북 인사이트 빼고 1200으로 통일" 지시했으나, **그 사이 다른 세션이 `--width-prose`(720px, 읽기·대화형)/`--width-content`(1200px, 표준)/`--width-data`(1600px, 데이터형) 3단 CSS 변수 체계로 더 정교하게 이미 구현**(2026-08-30, `studio.css`/`docs/UX_GUIDE.md` 갱신 확인됨) — 내가 실행하기 전에 선점되어 재작업 불필요해짐.
- **(발견, 미착수) 배포 거버넌스 변경**: `CLAUDE.md`에 "세션은 main에 직접 push 금지 — 작업 브랜치 + PR + auto-merge(build-check 통과 조건)" 원칙이 새로 추가된 걸 확인. `build-check.yml`(push마다 Pages와 동일 조건으로 사전 빌드 검증), `site-health-check.yml`(10분마다 라이브 사이트 확인) 두 안전장치도 신설된 상태 — 위 인시던트의 직접적 후속 조치로 보임. **이 스레드는 아직 이 새 절차로 커밋해본 적 없음**(지금까지는 전부 main 직접 push, 정책 도입 이전/과도기).

## ③ 진행 중이거나 남아있는 작업
- [ ] Studio 폭 정책의 다른 세션 구현(`--width-prose/content/data`)이 실제로 내가 지적한 3개 문제(ask.html/style-guide.html 760 정당성, system-map 임의값, book-insight 1600 근거부족)를 잘 해소했는지 브라우저로 검증 안 함.
- [ ] `system-map.html`(시스템 구조 페이지)이 최근 인프라 변경(`_config.yml` 신설, `build-check.yml`/`site-health-check.yml` 신설)을 아직 반영 못함 — CLAUDE.md 원칙상 갱신 대상.
- [ ] `CLAUDE.md`의 새 "커밋 교통정리" 절차(작업 브랜치+PR+auto-merge)를 이 스레드가 실제로 한 번도 안 밟아봄.
- [ ] `CLAUDE.md`에 새로 추가된 "튜터 원칙"(AI CTO 학습 여정 — 규모 최적화·AI CTO 성장 두 기준으로 모든 제안 검증, 평가 요청 시 미화 없이 솔직하게, 핵심 결정은 사장님이 직접 내리게 유도)을 인지는 했으나 이 세션에서 실제 적용 사례는 아직 없음.

## ④ 다음에 이어서 할 일
1. 다음 코드 변경부터는 `main` 직접 push 대신 **작업 브랜치 생성 → 커밋 → PR → auto-merge 설정** 절차를 실제로 따라가며 확인.
2. `system-map.html`에 `_config.yml` 도입과 `build-check.yml`/`site-health-check.yml` 신설을 반영(요약 통계·외부연동 표·정리 이력).
3. Studio 폭 정책 최종 구현을 `check_studio_style.py` + 브라우저(375px/1280px)로 직접 검증하고, 문제 있으면 보완.
4. 이후 모든 제안·평가는 CLAUDE.md "튜터 원칙"(규모 최적화 / AI CTO 성장) 기준으로 통과시키고, 핵심 결정은 사장님이 직접 내리도록 유도하는 톤으로 전환.
5. `roles/` 폴더에 다른 스레드 파일이 쌓이는 대로 이 파일과 겹치는 인프라/배포 관련 결정사항이 없는지 대조.
