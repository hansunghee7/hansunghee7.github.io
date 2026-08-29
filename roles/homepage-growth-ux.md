# homepage-growth-ux — 공개 홈페이지 SEO/GEO/AEO·UX·성능 스레드

## ① 목적과 범위
공개 홈페이지(simplifier.co.kr, Jekyll + GitHub Pages) 자체를 다루는 스레드.
검색/AI엔진 노출 극대화(SEO/GEO/AEO)를 위한 콘텐츠 전략과, 그걸 뒷받침하는
프론트엔드 UX·성능 개선을 함께 맡는다. claude-code-ops(메타 운영 상담),
클라우드 이사 가이드(인프라 이전) 스레드와는 별개 — 이 스레드는 대부분
main 브랜치의 실제 배포 코드(`_layouts/`, `_includes/`, `_data/pillars.yml`,
`scripts/`)를 직접 건드린다.

## ② 확정된 주요 결정사항
- **연관글 추천 알고리즘**: 단어 단위 토큰화 + IDF 가중 Jaccard 유사도로 고도화 완료.
- **12개 필러 카테고리 소개문(intro/intro_extended)**: 전면 재작성 완료 — em-dash
  금지(AI가 쓴 것처럼 안 보이게), GNB를 유일한 소스오브트루스로 완결/연재중 상태 정합.
- **아키텍처 리팩터**: 코칭문의 CTA·이전/다음글·연관글을 마크다운 본문에서
  `_includes/post_cta.html`·`post_nav.html`·`related_posts.html`로 분리,
  `sync_all.py`가 prev/next를 front matter에 기록하도록 변경.
- **성능**: LCP `<link rel=preload>`(커버 이미지), 본문 이미지 `loading="lazy"`
  (웹툰/에피소드 카테고리는 스와이프 뷰어 JS와 충돌해 제외), 1006/1007개 본문
  이미지에 width/height 부여해 CLS 방지, 외부(kakaocdn) 이미지 전량 로컬라이즈,
  `normalize_new_post.py`가 향후 신규 글의 외부 커버 이미지를 자동 다운로드.
- **콘텐츠 전략 대전환**: 브런치 원문과의 중복(브런치 쪽은 캐노니컬 기능이 없어
  손 못 댐) 문제를 "브런치에 없는 새 종합 콘텐츠"로 대응하기로 확정 — 기존
  카테고리(브런치 상속)가 아니라 **"전략적 필러"**(코칭/PO/기획/UX/스타트업전략/강연,
  실제 사업 포지셔닝 축)를 신설하는 방향.
  - 파일럿 "스타트업 전략"(브런치 `startstrategy` 30편과 1:1 매칭 검증됨) PRD
    작성 완료 → [Artifact](https://claude.ai/code/artifact/d2adbd6a-b03b-4514-b5cf-45a543ab75c4)
  - 벤치마킹: CB Insights "Why Startups Fail"(구조), HubSpot 토픽클러스터 이론,
    GEO 논문(구체적 숫자/인용 포함 시 AI 인용률 상승) — 단, 1인 브랜드가 이 패턴을
    쓴 검증된 선례는 못 찾음(리서치로 확인).
  - **의도적 실험**: 이 파일럿은 "고아 페이지"로 시작(GNB·footer 링크 없음,
    sitemap.xml엔 포함, noindex 아님) — HubSpot의 양방향 링크 원칙에서 벗어나는
    걸 알고도 사용자가 직접 선택한 실험. 개별 글 페이지엔 애초에 footer 자체가
    없어서(별도 미해결 이슈) 지금은 footer 링크도 불가능한 상태.
- **pillar.html UX**: 카테고리 nav 활성 pill 자동 스크롤, Esc로 "더보기" 모달
  닫기, 스크롤 시 상단 카테고리 nav sticky 고정(2026-08-30). "스와이프로 필러 간
  이동" 아이디어는 기각 — 이미 있는 가로 스크롤 topic-nav와 제스처가 겹치고
  오조작 위험이 커서, 더 안전한 sticky nav로 대체 제안·채택.
- **빌드 안정성 패턴 확립**: `jekyll-optional-front-matter` 플러그인 때문에
  front matter 없는 `.md` 파일도 Jekyll이 Liquid로 처리한다 — 문서 안에 리터럴
  `` {% include %} `` 같은 텍스트가 있으면 raw 래핑이 없는 한 **사이트 전체
  빌드가 깨진다.** 2026-08-29~30 사이 이 패턴으로 2번 실제 장애 발생
  (`insight-7b3e9f2c/STYLE_GUIDE.md`, `docs/UX_GUIDE.md`) — 둘 다 이 스레드가
  발견해 `{% raw %}`로 수정. 진단 절차: GitHub Actions API
  `/commits/{sha}/check-runs` → `/check-runs/{id}/annotations`(관리자 권한 없어도
  됨, `/actions/jobs/{id}/logs`는 403). annotation이 실제 에러 지점 전에
  잘려있으면(로그가 길 때 흔함) `git log`로 마지막 성공 커밋 이후 의심 커밋을
  좁혀 직접 훑는다.
- **⚠️ 방금 발견한 저장소 정책 변경(2026-08-29 도입, CLAUDE.md)**: 이제 세션은
  **main에 직접 push 금지** — 작업 브랜치에 push 후 PR + auto-merge(build-check
  통과 시 자동 병합) 방식으로 전환됨. 이 스레드는 오늘 그 규칙이 보이기 직전/직후
  경계에서 main에 직접 push 3회 했다(`56d2eb0b`, `762daa61`, `e472c81b` — 빌드
  장애 긴급 대응 포함). **다음 커밋부터는 이 스레드도 새 규칙(브랜치+PR)을 따라야 함.**

## ③ 진행 중이거나 남아있는 작업
- [ ] "스타트업 전략" PRD 사용자 승인 대기 — 승인되면 실제 파일럿 페이지 빌드 시작
- [ ] PRD의 열린 질문 3개 미해결: 고아페이지 재평가 시점/기준, "미국진출" 카테고리
  포함 여부, 테마별(6개 클러스터) 인용문·통계 추출 담당
- [ ] 나머지 전략 필러 5개(코칭 ~121편, PO 47편, 기획 33편, UX 35편, 강연 ~21편)
  콘텐츠 매핑은 논의됐으나 PRD 미작성, 착수 전
- [ ] 개별 글 페이지에 footer가 없는 문제(현재 `/`, `/log.html`, `page.is_index`만
  footer 노출) — 고아페이지 실험 결과 보고 footer 링크 도입 여부 재검토 예정
- [ ] main 직접 push 금지 정책이 새로 생겼는데, 이 스레드는 아직 브랜치+PR 방식으로
  전환 안 함 — 다음 코드 변경부터 적용 필요

## ④ 다음에 이어서 할 일
1. 사용자에게 PRD 피드백(승인/수정) 받기 → 승인 시 스타트업 전략 파일럿 페이지 실제 빌드
2. 이후 코드 변경은 `git checkout -b <작업브랜치>` → push → PR(auto-merge)로 진행,
   main 직접 push 지양
3. PRD 열린 질문 3개를 사용자에게 확인해 확정
4. 파일럿 결과(색인 여부, GEO 인용 여부)를 월 1회 SEO/GEO/AEO 검증 루틴(GSC·Rich
  Results Test·AI엔진 직접 질의)으로 확인 후 나머지 5개 전략 필러 착수 여부 판단
