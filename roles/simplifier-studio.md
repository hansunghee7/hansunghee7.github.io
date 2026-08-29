# simplifier-studio — 스튜디오 UX/거버넌스 + 저장소 위생 스레드 요약

## ① 목적과 범위
`insight-7b3e9f2c/`(Simplifier Studio, 비공개 관리자 도구) 내부의 UX·기술 일관성을
구축·유지하는 스레드. 페이지가 9개→15개로 늘면서 각자 스타일을 복붙하다 어긋나기
시작한 게 계기 — 공용 인프라(studio.css/js)와 규칙 문서(STYLE_GUIDE.md)를 만들고,
자동 점검 스크립트까지 갖춰서 "규칙이 있다는 걸 미래 세션이 저절로 알게" 하는
거버넌스 체계를 세웠다. 여기서 파생돼 저장소 전체(블로그 본문 603개, 이미지 자산,
git 히스토리, GitHub Actions) 위생 감사까지 맡았고, 최근엔 공개 홈페이지+스튜디오를
아우르는 통합 UX 가이드(`docs/UX_GUIDE.md`) 작성까지 확장됐다.

## ② 확정된 주요 결정사항
- **studio.css/studio.js 공용화**: 15개 스튜디오 페이지가 `:root` 토큰·헤더·
  `#adminShellNav`·ⓘ 버튼·새로고침 버튼 CSS/JS를 각자 인라인으로 복붙하던 걸
  공용 파일 두 개로 통합. 새 메뉴는 `studio.js`의 `STUDIO_NAV` 배열 한 곳만 고치면 됨.
- **ⓘ info-dot 패턴 확정, `title=` 네이티브 툴팁 전면 금지** — 클릭/탭에 반응 안
  하는 죽은 버그가 2회 발견(book/sns-insight 초기 버전, 외부 shorts-lab 파이프라인)
  돼서 확정. 배치 원칙: 설명 대상 바로 옆에, `margin-left:auto`로 구석에 밀지 않음.
- **거버넌스 3종 세트 구축**: `insight-7b3e9f2c/STYLE_GUIDE.md`(스튜디오 전용 규칙,
  실제 사고 기록 포함) + `scripts/check_studio_style.py`(FAIL=자동판정/WARN=사람판단
  구분, 15개 파일 FAIL 0건 유지 중) + `CLAUDE.md`에서 새 세션이 자동으로 보게 연결.
- **외부 생성 페이지도 root-cause 수정**: `shorts-studio.html`을 매번 새로 쓰는
  `shorts-lab/pipeline/build_studio_site.py`(별도 저장소) 자체를 studio.css/js
  패턴에 맞게 재작성 — HTML만 patch하면 다음 재생성 때 되돌아가는 문제 방지.
- **`.doc` 패턴 확립**: 긴 마크다운 문서(숏폼 공정 정본 등, 나중엔 스타일
  가이드 자신도)를 읽기용으로 렌더링하는 두 번째 스튜디오 UX 패턴. 대시보드형
  (1100~1600px, 데이터 밀도)과 문서형(760px 안팎, 가독성 우선)이 공존 — 폭이
  다르게 보이는 건 버그 아니고 의도.
- **저장소 전체 감사 완료(2026-08-29)**: 카테고리 오타 없음, prev/next 링크
  603개 전수 무결, git 히스토리 시크릿 노출 0건, GitHub Actions 5개 전부 최근
  실행 success, 블로그 본문 alt 텍스트 오염 6건 수정, 고아 이미지 743개 삭제 +
  69개 `log_assets/images_quarantine_2026-08-29/`로 격리(README에 확인법 기록).
- **`docs/UX_GUIDE.md` 신설** — 공개 홈페이지(그동안 문서 자체가 없었음, 처음
  문서화) + 스튜디오를 아우르는 공통 원칙/의도적 차이/미정리 차이 정리. **거의
  동시에 "홈" 스레드도 같은 요청을 받아 `insight-7b3e9f2c/style-guide.html`을
  통합 UX 가이드로 확장하고 스튜디오 메뉴명을 "통합 UX 가이드"로 바꿔 병합
  완료** — 중복 작업이었지만 검증해보니 내용 정합함, 그대로 채택.
- **다른 스레드가 `CLAUDE.md`에 추가한 최신 규칙 확인**: main 직접 push 금지
  (작업 브랜치+PR+auto-merge, github-actions/사장님 직접 커밋만 예외),
  이미지 정리는 `scripts/find_orphan_images.py`로만(로고 오탐 사고 이후 의무화),
  `system-map.html`은 인프라 변경과 같은 세션에서 갱신.

## ③ 진행 중이거나 남아있는 작업
- [ ] `STYLE_GUIDE.md` / `docs/UX_GUIDE.md` / `style-guide.html` 세 문서가 동시에
      존재하고 자동 동기화가 없음 — 스튜디오 규칙을 크게 바꿀 때마다 세 곳 다
      확인·갱신해야 어긋나지 않음.
- [ ] `log_assets/images_quarantine_2026-08-29/`의 미확인 이미지 69개 — 확실해질
      때까지 보류, README 기준으로 사람이 최종 삭제 판단.
- [ ] "정리 후보"로 기록만 해두고 결정 안 한 것: 공개 사이트 공유 디자인 토큰
      파일화, 공개 사이트에도 ⓘ 패턴 필요한 지점 있는지 검토.

## ④ 다음에 이어서 할 일
1. 새 Studio 메뉴/페이지 요청이 오면 `STYLE_GUIDE.md` 먼저 읽히고, 완료 보고
   전에 `python scripts/check_studio_style.py` 실행을 기본 동작으로 유지.
2. **이 스레드도 `CLAUDE.md`의 "커밋 교통정리" 규칙을 따를 것** — main에 직접
   push하지 말고 작업 브랜치+PR(auto-merge)로. 지금까지 이 스레드가 만든
   커밋들은 그 규칙 도입(2026-08-29) 이전이라 예외였음, 앞으로는 적용.
3. `images_quarantine_2026-08-29/` 재확인 시점이 되면 README 보고 최종 삭제
   여부 판단.
4. `roles/*.md`가 다른 스레드 것까지 쌓이면(`roles/claude-code-ops.md` 참고)
   통합 정리 세션에서 UX_GUIDE.md 관련 "홈" 스레드와의 중복 부분부터 정리.
