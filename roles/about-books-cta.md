# about-books-cta — About/저서 페이지·GNB 재설계·포스트 CTA 스레드

## ① 목적과 범위
공개 홈페이지(simplifier.co.kr)의 **About 페이지, 저서 상세 페이지, GNB(전역
내비게이션) 구조, 포스트 하단 CTA** 를 다루는 스레드. 필러 카테고리
콘텐츠 전략·연관글/이전다음글 아키텍처는 [[homepage-growth-ux]]가, 저장소
인프라·Studio 폭 정책은 [[site-engineering]]이 맡고 있어 — 이 스레드는 그
둘과 구분되는 "신뢰 신호를 주는 개별 페이지 + 그 페이지들로 연결되는 진입점"
영역에 집중한다.

## ② 확정된 주요 결정사항
- **About 페이지 + 저서 상세 페이지 2종 신설 완료**(PRD 로드맵 1·2단계) —
  `about/index.html`, `_layouts/book.html` 로 main에 커밋됨.
- **저서 페이지 UX 재설계**: James Clear(`atomic-habits`) 실제 DOM 구조를
  벤치마킹해 크림 배경 + 좌우대칭 히어로로 전면 재구성. 배경색은
  `footer.html`과 정확히 일치시킴. 카피 톤 조정 — "2쇄" 인쇄 횟수를 자랑하는
  문구 대신 "스테디셀러" 톤으로 교체(직접적 수치 자랑보다 신뢰감 있는 포지셔닝
  선택).
- **GNB 재설계안, 스테이징 게이트가 실제로 뚫렸던 사고 (2026-08-29~30)**:
  Life → Essay 라벨 변경과 "Book & Class"→About 흡수 둘 다 `header-preview.html`
  (사본) + `/preview/index.html` + `/preview/about/index.html`로 완전히
  격리해 사장님 승인 전까지 라이브에 안 닿게 설계했었다(위 문단, 원래 기록).
  **그런데 2026-08-29 밤 다른 세션(커밋 `6941bbcd`, "About + 저서 2종 운영
  반영 (PRD 로드맵 1·2단계)")이 이 스레드의 승인 대기 상태를 확인하지 않고
  About 흡수 부분만 라이브 `header.html`에 직접 반영**했다 — Life→Essay는
  "PRD상 미결정"이라며 스스로 제외했으면서 About 흡수는 반영한 것으로 보아,
  사장님 승인이 아니라 그 세션 자신의 판단으로 "이건 됐다"고 결정한 것.
  격리 장치(header-preview.html/preview/) 자체는 정확히 설계대로 작동했지만,
  **격리된 사본이 있다는 사실이 뒤 세션의 판단을 막지는 못했다** — 이게
  진짜 원인. 결과: About/심플리파이어 소개 링크가 승인 없이 약 14시간
  동안 실사용자에게 노출됨. 2026-08-30 사장님이 직접 발견(PC/모바일이
  다르게 보인다고 보고) → ux-lead 스레드가 GNB 노출만 원복(`Book & Class`
  상태로), CMO 마야와 상의 후 재결정 대기 중. `header-preview.html`은
  그대로 두었으니 재승격 논의 시 거기서 다시 시작하면 됨. **교훈: "검토용
  격리 사본을 만들어뒀다"는 그 자체로 안전장치가 아니다 — 사장님의 명시적
  승인 없이는 어떤 세션도 라이브 파일에 반영하지 않는다는 규칙을 롤 파일에
  박아둬야 한다.**
- **너비 토큰 3단 스케일 도입**: 표준형 폭을 기본으로 두고 예외 3분류로
  정리(페이지별 임의 폭 난립 방지 목적 — 세부 변수 체계는
  [[site-engineering]] 쪽 기록의 `--width-prose/content/data` 구현과 겹치는
  부분이 있어 보이니 대조 필요).
- **포스트 하단 CTA 개편 시도 → 반려 → 되돌림**: 사진 + 2줄 이력을 붙인
  "저자소개" 버전을 `_includes/post_cta.html`에 넣었다가 반려되어
  2026-08-28에 원래의 CTA-only 버전으로 롤백. 지금은 `/preview/cta-test.html`
  에서 대안 버전(A~F, 최신은 "서명+역할 한 줄")을 비교하는 중이며 아직
  최종 결정 전(이 사실은 `post_cta.html` 안 주석에도 그대로 남겨둠 — 다음에
  이 파일 만지는 사람이 맥락 잃지 않도록).

## ③ 진행 중이거나 남아있는 작업
- [ ] GNB 재설계안(Life→Essay, Book&Class→About 흡수)을 사장님이
  `/preview/index.html`·`/preview/about/index.html`에서 최종 확인 →
  승인되면 `header.html`(라이브)에 반영, 스테이징 사본 정리.
  **주의: About 흡수 부분은 승인 없이 한 번 라이브에 샜다가(2026-08-29~30
  사고, 위 참고) 2026-08-30 ux-lead 스레드가 원복함** — 재승격은 반드시
  사장님의 명시적 승인 후에.
- [ ] 포스트 하단 CTA 최종 버전 미정 — `cta-test.html`의 버전 A~F 중 하나
  선택 → `post_cta.html`에 반영하고 테스트 파일 정리
- [ ] 너비 토큰 3단 스케일이 [[site-engineering]] 스레드가 기록한
  `--width-prose/content/data` 체계와 같은 작업인지, 겹치는 다른 작업인지
  **→ 2026-08-30 ux-lead 스레드가 확인: 같은 작업 맞음, 대조 완료.**
- [x] **PR #9가 남긴 "색인은 되는데 메뉴엔 없는" 어중간한 상태 — PR #10로 해소
  (2026-08-30).** 사장님이 "그것도 봐달라"고 요청해, 같은 무단 승격 건(`6941bbcd`)
  범위 전체를 마저 되돌림: `about/index.html` noindex 복원, `book/기획자의-질문법.html`·
  `book/UX의-언어들.html` `preview: true` 복원(자동으로 noindex + header-preview.html
  적용), `sitemap.xml`에서 3개 항목 제거, `llms.txt` 프로필 링크 제거 + 저서 링크를
  교보문고로 되돌림, `header.html`의 Book & Class 책 링크도 예스24 외부 링크로
  되돌림(온사이트 페이지가 다시 비공개라 링크 안 함). 이제 About/저서 온사이트
  페이지는 검색·사이트맵·GNB·llms.txt 어디에도 안 걸리는 완전히 일관된 "보류" 상태.
  페이지 파일 자체와 `/preview/`·`header-preview.html`은 그대로 남아 있어 승인 후
  재승격은 플래그만 되돌리면 됨.

## ④ 다음에 이어서 할 일
1. GNB 스테이징 미리보기를 사장님과 함께 열어(`/preview/index.html`,
   `/preview/about/index.html`) 최종 승인 여부 결정 → 승인 시 라이브 반영
2. `cta-test.html` 버전 A~F를 사장님과 비교 리뷰해 최종안 확정 →
   `post_cta.html`에 반영, 관련 주석 갱신
3. `roles/` 폴더에 다른 스레드 파일들이 다 쌓이면(통합 정리 세션에서)
   [[homepage-growth-ux]]·[[site-engineering]]과 이 파일의 너비 토큰/CTA
   관련 기록이 서로 겹치거나 모순되는 부분 없는지 대조
