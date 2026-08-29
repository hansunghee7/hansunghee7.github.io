# multi-publish-sns-insight — 멀티 퍼블리싱 & SNS 인사이트 스레드 요약

## ① 목적과 범위
Simplifier Studio 안에 **"멀티 퍼블리싱"**(CMS로 쓴 글을 채널별로 다듬어 복사·붙여넣기 쉽게 만드는 도구)과 **"SNS 인사이트"**(각 SNS 팔로워 수를 자동 수집해 추이로 보여주는 기능) 두 개를 처음 설계·구현한 스레드. 세션 초반에는 그 전 단계로 admin CMS 자체(Decap→Sveltia 전환, GitHub OAuth 로그인 연결, 여러 실운영 버그 수정)도 다뤘음 — 지금은 안정화되어 더 손댈 일 없음.

## ② 확정된 주요 결정사항
- **CMS**: Decap에서 Sveltia로 메인 전환 완료(`/admin/` = Sveltia, `/admin-legacy/` = Decap 보존). 기존 Cloudflare Worker OAuth를 그대로 재사용 — 새 OAuth 앱/워커를 만들지 않는 게 이후 모든 로그인 관련 기능(멀티 퍼블리싱, SNS 인사이트 확장)의 공통 원칙이 됨.
- **write.html**: 실제 SNS 사이트 대부분(LinkedIn/Threads/Facebook/Instagram/브런치/로켓펀치)이 `X-Frame-Options`로 iframe 삽입을 원천 차단한다는 걸 실측 확인 → CMS(Sveltia)만은 같은 출처(자기 사이트)라 iframe으로 Studio 셸 안에 그대로 삽입 가능해서 그렇게 함.
- **멀티 퍼블리싱**: 8개 채널 탭(LinkedIn / LinkedIn 뉴스레터 / Threads / Facebook / Instagram / 브런치·네이버블로그 / 리멤버 커넥트 / 로켓펀치). 각 탭은 실제 서비스 쓰기화면을 흉내냄 — `narrow`(제목 없이 좁은 폭, 산세리프: LinkedIn 포스트/Threads/Facebook/Instagram/리멤버/로켓펀치)과 `wide`(제목칸+넓은 폭+Noto Serif KR: 브런치·네이버블로그, LinkedIn 뉴스레터)로 구분. narrow 채널은 제목+본문을 한 텍스트로 합침(실제 화면에 제목칸이 없어서). 채널별 실제 글자수 제한 적용(리멤버 1500/로켓펀치 2000은 사용자 스크린샷으로 실측, 나머지는 공개된 수치). AI 요청 프롬프트 복사 버튼(채널별 톤 지침 포함) 추가. "새 글쓰기 열기"는 iframe이 막혀서 새 탭으로 여는 방식으로 확정, 버튼 줄(글쓰기/AI요청/복사)은 위·아래 모두, 한 줄에 나란히 배치.
- **SNS 인사이트**: 로그인 세션 없이는 대부분 SNS를 스크래핑할 수 없다는 걸 실측으로 확인(LinkedIn/Facebook/Instagram/Threads/리멤버/로켓펀치는 authwall 또는 SPA 셸만 응답) → 크롬 확장(`_sns-extension/`)이 사용자가 실제 로그인한 브라우저에서 프로필을 방문할 때 화면 텍스트에서 팔로워 수를 읽어 GitHub에 커밋하는 방식으로 확정. 브런치만 예외로 공개 HTML에 `followerCount`가 그대로 노출되어 있어 서버(GitHub Actions, `scripts/fetch_brunch_stats.py`)가 매일 자동 수집. (이후 다른 세션이 이어받아 네이버블로그·로켓펀치도 로그인 없이 공개라는 걸 추가로 확인해 서버 수집으로 옮기고, OAuth 팝업이 GitHub 로그인 페이지의 COOP 정책 때문에 불안정한 걸 발견해 PAT 붙여넣기 로그인도 추가함 — 확장은 지금 이 스레드 밖에서도 계속 진화 중.)
- SNS 인사이트 바로가기 링크(↗)와 멀티 퍼블리싱의 "새 글쓰기 열기"는 **의도적으로 완전히 같은 URL**을 씀 — 크롬 확장은 클릭 출처가 아니라 도착 URL만 보고 동작하므로, 둘 중 어디로 방문해도 동일하게 수집됨.

## ③ 진행 중이거나 남아있는 작업
- **2026-09-27경 재검토 예정** (사용자와 합의, 메모리 `hansunghee7_sns_insight_followups.md`에 기록): (1) 네이버블로그 수집이 매일 안정적으로 갱신되는지, (2) 카드에 7일/30일 추세 요약을 추가할지.
- 다른 세션(북인사이트 담당)에게 RIDI(`ridibooks.com/category/bestsellers/320`)·밀리의서재(`millie.co.kr/v3/search/3depth/1298`) 책 순위 소스를 전달함 — 반영 여부는 그쪽 판단 대기 중, 이 스레드가 할 일 아님.
- SNS 인사이트/확장 관련 파일들이 지금 다른 세션들과 공동 소유 상태로 계속 진화 중(studio.css/js 공통 스타일 통합, 카드 톤 통일, 확장의 수집 로직 개선 등) — 이 스레드가 원 설계자이지만 더 이상 단독 소유는 아님.

## ④ 다음에 이어서 할 일
1. 멀티 퍼블리싱/SNS 인사이트/write.html 관련 요청이 오면, 위 설계 원칙(narrow/wide 구분 이유, iframe이 안 되는 이유, 크롬 확장 아키텍처)을 다시 조사하지 말고 이 파일을 먼저 참고해서 바로 이어갈 것.
2. 2026-09-27 전후로 SNS 인사이트 네이버블로그 갱신 여부·추세 요약 추가를 사용자와 다시 논의.
3. `CLAUDE.md`에 2026-08-29부로 "세션은 main에 직접 push 금지, 자기 브랜치+PR로 병합" 규칙이 새로 생겼음 — 이 스레드가 실제 사이트 파일(main 기준)을 다시 고칠 일이 생기면 이 규칙을 따를 것. (이 파일이 있는 `roles-notes` 브랜치 자체는 원래도 main과 분리된 목적이라 무관.)
