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
- **GNB 재설계안 확정, 단 스테이징에만 존재**: Life → Essay로 라벨 변경,
  "Book & Class" 메뉴를 없애고 About 메뉴로 흡수(첫 항목이 about 페이지로
  연결). 모든 페이지가 공유하는 `_includes/header.html`을 직접 건드리는
  대신 `header-preview.html`(사본) + `/preview/index.html` +
  `/preview/about/index.html`을 만들어 완전히 격리된 상태로 검토 중 —
  **아직 라이브 header.html에는 반영 안 됨**(확인 완료: 현재도 "Life"·
  "Book & Class" 그대로).
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
  승인되면 `header.html`(라이브)에 반영, 스테이징 사본 정리
- [ ] 포스트 하단 CTA 최종 버전 미정 — `cta-test.html`의 버전 A~F 중 하나
  선택 → `post_cta.html`에 반영하고 테스트 파일 정리
- [ ] 너비 토큰 3단 스케일이 [[site-engineering]] 스레드가 기록한
  `--width-prose/content/data` 체계와 같은 작업인지, 겹치는 다른 작업인지
  대조 안 됨 — roles 통합 정리 때 확인 필요

## ④ 다음에 이어서 할 일
1. GNB 스테이징 미리보기를 사장님과 함께 열어(`/preview/index.html`,
   `/preview/about/index.html`) 최종 승인 여부 결정 → 승인 시 라이브 반영
2. `cta-test.html` 버전 A~F를 사장님과 비교 리뷰해 최종안 확정 →
   `post_cta.html`에 반영, 관련 주석 갱신
3. `roles/` 폴더에 다른 스레드 파일들이 다 쌓이면(통합 정리 세션에서)
   [[homepage-growth-ux]]·[[site-engineering]]과 이 파일의 너비 토큰/CTA
   관련 기록이 서로 겹치거나 모순되는 부분 없는지 대조
