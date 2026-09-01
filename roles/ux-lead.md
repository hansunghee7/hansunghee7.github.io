# ux-lead — Simplifier UX 총괄 스레드 요약

> 2026-09-01 정리: 442줄 → 80줄 상한 적용. 사고 경위·디버깅 서사는 PR 링크로
> 대체하고 재사용 가능한 결론만 남겼다. 자세한 경위가 필요하면 PR 본문 참고.

## ① 목적과 범위
공개 홈페이지(simplifier.co.kr)+스튜디오(`insight-7b3e9f2c/`) **양쪽 UX 총괄**.
개별 요청 처리가 아니라 "다른 화면과의 일관성"을 먼저 판단해 정본 문서에
규칙으로 남기는 방식. About/저자소개 콘텐츠는 마야(cmo-marketing) 소관,
`shorts-lab` 파이프라인은 2026-08-31부터 [숏감독.md](숏감독.md) 소관 —
겸임 종료, 새 요청 들어오면 그쪽으로 안내.

정본 문서: [docs/UX_GUIDE.md](../docs/UX_GUIDE.md)(공통) ·
[insight-7b3e9f2c/STYLE_GUIDE.md](../insight-7b3e9f2c/STYLE_GUIDE.md)(스튜디오 세부).
저장소 운영·사고 대응은 [site-repo-ops.md](site-repo-ops.md) 소관.

## ② 확정된 결정사항

**너비 정책** — 컨테이너 기본은 표준형(`--width-content`, 유동 1200px). 예외는
콘텐츠 성격으로만 판정, 넷째 값 만들지 않기: ①혼합형(`--width-prose` 720px,
`.doc` 5개·블로그 본문) ②텍스트전용(컨테이너 자체를 읽기형, `ask.html`)
③데이터전용(`--width-data` 1600px, `book-insight.html`). 고정 px 대신
`min()`/`clamp()`, 폴백 명시(`var(--width-content, 1200px)`) — 미정의 시
`max-width` 무효화로 텍스트가 전체 화면으로 퍼지는 사고 있었음. 토큰 정의는
`studio.css`/`_includes/width-tokens.html` 두 곳뿐, 컨테이너급 하드코딩 px 0건
(grep 감시 가능). `.doc` 너비 규칙은 `studio.css`에 둘 것 — 페이지 인라인은
외부 `shorts-lab` 파이프라인 재실행 때 덮어써짐.

**스튜디오 사이드바** — 사용빈도순 4그룹(인사이트→제작→대화→참조),
`studio.js`의 `STUDIO_NAV` 배열 `group` 필드로 소제목 자동 생성. 그룹 소제목은
`--good`(초록), 타이틀 아래·그룹 사이 간격 34px 통일.

**카드·그래프 표준** — `.tile`(studio.css 공용) + 변형 `.tile-sm`/`.tile-accent`.
그래프는 누적 추이=라인 스파크라인, 일별 발생량=막대.

**GA4 해상도 실측** — `0x0`(헤드리스/크롤러)은 반드시 집계 제외, 제외 건수는
`excluded_invalid_sessions`로 화면에도 표시. 클라우드 세션도 `fetch-analytics.yml`을
`workflow_dispatch`로 실행 후 `assets/data/analytics.json` 읽으면 됨 — 로컬
자격증명 불필요("PC 전용"은 과거 오기, 정정됨).

**작업 관행(위반 시 재발한 실수들)**
- 스튜디오 작업 후 `python scripts/check_studio_style.py` 필수(문자열 패턴만 봄,
  여백 등은 미리보기로 직접 확인). GitHub Pages CSS 캐시 ~10분 — 확인은 Ctrl+F5.
- **모바일 오버플로/레이아웃 버그는 `playwright.devices`(isMobile:true)로만
  검증** — 데스크톱 뷰포트 리사이즈는 레이아웃 뷰포트가 고정이라 재현 안 됨,
  `window.innerWidth`는 콘텐츠 오버플로에 따라 늘어나므로 판정 기준으로 쓰면
  순환 오류(`document.documentElement.clientWidth` 사용). PR #16→#21 교훈.
- **주소창 접힘/펼침 같은 실기기 동적 뷰포트 버그는 헤드리스로도 재현 불가** —
  사장님 실기기 재확인이 유일한 검증 수단, 재현 안 된다고 "버그 없음"으로
  결론 내리지 않는다. `position:sticky` + vh 계열 단위 조합은 `dvh`가 스크롤
  중 바뀌면 뒤 콘텐츠 전체가 밀린다 — **새 vh 단위는 기본 `svh`**, 의도적으로
  변해도 되는 요소에만 `dvh` (PR #39/#40/#42).
- **새 작업 착수 전엔 항상 `roles/README.md`의 "🔴 사장님 결정 대기" 표부터
  훑는다** — 다른 스레드가 같은 주제를 이미 진행 중일 수 있다(블로그 CTA
  중복 착수 직전 중단 사례, shorts-lab 이관 인지 못 하고 착수한 사례 둘 다
  이 규칙을 안 지켜서 발생).
- **스테이징/미리보기 격리 사본은 그 자체로 안전장치가 아니다** — 사장님의
  명시적 승인 문구 없이는 어떤 세션도 라이브에 반영하지 않는다(GNB "About"
  무단 승격 사고, PR #9·#10으로 완전 원복).
- ⓘ info-dot이 정본 패턴, `title=` 네이티브 툴팁 전면 금지(클릭 무반응 버그
  반복). 새 표를 `.tablebox`로 감쌀 땐 그 표의 "카드 없음 전제" padding-top이
  남아있는지 확인(pillar-manage.html PR #38 교훈).

## ③ 진행 중이거나 남아있는 작업
- [ ] **GA4 해상도 표본 관찰** — 표본이 작을 때 GA4 리포트가 조회마다 흔들림
  확인(75→59건 등), 아직 "충분히 쌓였다"고 볼 단계 아님. 수백 건대 쌓이면
  1200px 표준형 타당성 재확인.
- [ ] **`STYLE_GUIDE.md`/`UX_GUIDE.md`/`style-guide.html` 3중 동기화** — 자동
  동기화 없음, 스튜디오 규칙 크게 바꿀 때마다 세 곳 수동 확인. 통합 여부
  사장님이 질문했으나 **통합 비추천**(읽는 빈도·목적이 달라 합치면 한쪽이
  묻힘) — 자동 동기화 스크립트 투자는 아직 과함(3회 연속 안 어긋남).
- [ ] **공개 사이트 ⓘ 패턴 필요 지점 검토** — 범위 커서 사장님 확인 후 착수.

## ④ 다음에 이어서 할 일
1. 새 화면 만들 때 너비 3분류 중 어디 속하는지 먼저 판정, 숫자 새로 하드코딩 안 함.
2. 새 ⓘ 변형은 `positionInfoText()`/`positionAllInfoDots()`가 처리하게 맞추고
   직접 새 로직 만들지 않는다.
3. 이 스레드가 다시 열리면 이 파일 + 두 정본 문서(UX_GUIDE.md, STYLE_GUIDE.md)만
   읽으면 된다 — 대화 전체를 다시 볼 필요 없음.
