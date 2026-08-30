# roles/ — 스레드별 인수인계 인덱스

여러 Local/Cloud 클로드 세션이 각자 역할을 맡아 이 저장소를 동시에 다룬다.
`/export` 대신 각 스레드가 스스로 요약을 `roles/<파일명>.md`로 이 브랜치
(`roles-notes`, main과 분리돼 라이브 사이트에 영향 없음)에 커밋하는 방식으로
인수인계한다. 새 세션이 어떤 역할을 맡든 여기서 먼저 전체 현황을 훑고,
해당 파일로 들어가면 된다.

> 마지막 통합 정리: 2026-08-30 (cmo-marketing 스레드가 11개 파일 전수 확인, 거의
> 동시에 ux-lead 스레드도 독립적으로 10개 파일을 전수 검토함 — 두 결과를 이
> 문서에 합침). **같은 날 추가 정리**: 사장님이 ux-lead/simplifier-studio가
> 스튜디오 UX 영역에서 겹친다고 지적 → simplifier-studio의 UX/거버넌스 부분을
> ux-lead로 흡수, simplifier-studio는 저장소 위생 전담으로 축소. About 페이지/
> 저자소개 콘텐츠 소관도 cmo-marketing으로 확정. **경험DB 기록 방식도 같은 날
> 바뀜** — 아래 "공통 규칙" 참고. **세 번째 정리(같은 날, 사장님 직접 지시)**:
> GNB 구조/라벨과 About 콘텐츠의 경계는 cmo-marketing(마야) 스레드가 자체적으로
> 정리해서 진행하기로 확정 — ux-lead는 더 이상 안 챙김. `shorts-lab` 파이프라인
> 정리는 "숏감독" 스레드(신규)로 이관. **네 번째 정리(같은 날)**: ux-lead가
> 사장님 요청으로 착수하려던 "블로그 포스트 footer" 벤치마킹이 사실
> `about-books-cta`가 이미 버전 J까지 진행 중이던 "포스트 하단 CTA" 건과 같은
> 일이었음을 뒤늦게 발견 — ux-lead는 손을 떼고 결과만 넘겼다. 아래 🔴 표에서
> 중복 행을 정리.
> 스레드가 스스로 파일을 갱신하면 이 표도 같이 갱신할 것 — 안 그러면 이 문서도
> 곧 낡는다.

## 스레드 목록과 경계

| 파일 | 역할 | 성격 |
|---|---|---|
| [cmo-marketing.md](cmo-marketing.md) | CMO 겸 마케팅 튜터 — 측정 인프라(GA4/서치콘솔/Clarity), 진단, 검색/AEO 전략, 콘텐츠 신디케이션 정책. **2026-08-30부터 About 페이지/저자소개 콘텐츠 소관 + GNB 재설계 전체(구조 포함) 소관도 포함** | 전략·상담 |
| [homepage-growth-ux.md](homepage-growth-ux.md) | 공개 홈페이지 SEO/GEO/AEO 콘텐츠 제작 + 프론트 성능 | 실무(코드) |
| [ux-lead.md](ux-lead.md) | **공개 사이트+스튜디오 UX 총괄**(튜터명 "시안") — 너비 정책, 인사이트 카드/그래프 표준, 스튜디오 사이드바, 스튜디오 UX 거버넌스(STYLE_GUIDE.md/ⓘ 패턴/studio.css·js, 2026-08-30 simplifier-studio에서 이관) | 표준 수립 |
| [ai-cto-tutor.md](ai-cto-tutor.md) | AI CTO 학습 튜터 + 엔지니어링 체계(배포 안전망, 커밋 교통정리, 모닝브리핑, 자동화) | 전략·인프라 |
| [site-repo-ops.md](site-repo-ops.md) | 저장소 운영(노트북) — 배포 사고 대응, 이미지/템플릿 감사, git 충돌 조율 | 실무(운영) |
| [site-engineering.md](site-engineering.md) | 저장소 실무 엔지니어링 — 홈페이지/스튜디오 코드, 인프라 정리 | 실무(코드) |
| [simplifier-studio.md](simplifier-studio.md) | **스튜디오 저장소 위생 전담**(이미지·시크릿·GitHub Actions 감사) — UX/거버넌스는 2026-08-30 ux-lead로 이관 | 실무(운영) |
| [simplifier-qa-agent.md](simplifier-qa-agent.md) | RAG 에이전트 "Simplifier Q&A" + `prd-draft` 스킬 | 실무(코드) |
| [about-books-cta.md](about-books-cta.md) | About/저서 페이지, GNB 재설계, 포스트 CTA — **GNB 재설계·About 콘텐츠 둘 다 cmo-marketing이 정리해서 진행(2026-08-30 확정)**. 포스트 하단 CTA(작가 카드)는 이 스레드가 사장님과 직접 버전 A~J까지 진행 중 | 실무(코드) |
| [multi-publish-sns-insight.md](multi-publish-sns-insight.md) | 멀티 퍼블리싱(CMS→채널별 발행 보조) + SNS 인사이트(팔로워 추이 수집) | 실무(코드) |
| [claude-code-ops.md](claude-code-ops.md) | 클로드 코드 사용법 메타 상담 — 여러 기기/프로젝트 병행 운영 | 메타 |
| 숏감독 (파일 아직 없음) | `shorts-lab` 파이프라인 등 숏폼 제작 인프라 전담(2026-08-30 신설, 사장님 지시) — 다음에 그 스레드가 열리면 스스로 `roles/숏감독.md`를 만들 것 | 실무(코드) |

**겹치는 경계 요약** (자세한 사정은 각 파일 ①절 참고):
- 콘텐츠 **전략**(cmo-marketing) vs **제작**(homepage-growth-ux) — 허브/필러 페이지는
  homepage-growth-ux가 실착수, cmo-marketing은 승인 전 중복 착수 금지.
- **UX 표준 수립**(ux-lead) vs **실제 코드 구현**(site-engineering, about-books-cta,
  homepage-growth-ux) — 표준은 ux-lead가 정본 문서(UX_GUIDE.md/STYLE_GUIDE.md)에
  정리하고, 뒤의 셋이 실제 페이지에 적용. (2026-08-30 이전엔 simplifier-studio도
  UX 표준 수립 쪽이었으나 ux-lead로 통합됨 — 겹침 해소.)
- **인프라/배포 체계**(ai-cto-tutor) vs **저장소 운영 실무**(site-repo-ops) — 안전망·
  자동화 설계는 ai-cto-tutor, 개별 사고 대응·감사는 site-repo-ops.
- **About/GNB** — 2026-08-30 사장님이 "마야가 최대한 정리해서 진행"이라고 확정.
  ux-lead가 제안했던 "콘텐츠=마야/구조=ux-lead" 분리안은 채택되지 않았고, GNB
  재설계 전체를 cmo-marketing이 담당한다. ux-lead는 결과가 나오면 UX 표준
  문서(UX_GUIDE.md)에 반영하는 역할만 한다.
- **블로그 포스트 하단 footer/CTA** — about-books-cta 단독 소관(2026-08-30 확인).
  ux-lead가 별개 항목("블로그 footer 부재")으로 착수하려다 같은 일임을 뒤늦게
  발견 — 아래 🟡 해소 상태 참고.

## 🔴 사장님 결정 대기 (2026-08-30 기준)

| 스레드 | 대기 항목 |
|---|---|
| cmo-marketing / about-books-cta | GNB 재설계안(Life→Essay, Book&Class→About 흡수) 재승인 여부 — 완전히 원복된 상태에서 다시 논의 시작. 경계 문제는 해소됐으니(마야가 전담) 콘텐츠·구조 재승인만 남음 |
| cmo-marketing | 발행정책 전환(사이트 먼저 → 며칠 뒤 SNS 재발행) — "OK" 한마디로 확정 |
| homepage-growth-ux | "스타트업 전략" 필러 PRD 승인 여부 + 열린 질문 3개(고아페이지 재평가 기준·"미국진출" 카테고리 포함 여부·테마별 인용문 담당) |
| about-books-cta | 포스트 하단 CTA 버전 A~J(`cta-test.html`) 중 최종 선택 — 사장님이 직접 버전을 다듬는 중(2026-08-30, G~J). ux-lead가 브런치 벤치마킹으로 방향성만 외부 검증(사진+이름+역할+팔로우 카드로 수렴하는 게 맞다) |
| simplifier-studio | 격리 이미지 69개(`log_assets/images_quarantine_2026-08-29/`) 최종 삭제 여부 |
| site-repo-ops | `log.html` 무한 스크롤(전체 펼치면 약 49,000px) 개선 착수 여부 |
| simplifier-qa-agent | `shorts-lab/LAUNCH_PRD.md`의 확인 필요 항목(RICE 점수 정식화 등) |

### ⚠️ 사고 기록 (해결됨): GNB "About" 무단 승격 (2026-08-29 밤~2026-08-30)

About/저서 GNB 재설계는 `header-preview.html` + `/preview/`로 완전히 격리해
사장님 승인 전엔 라이브에 안 닿게 설계돼 있었다. 그런데 **다른 세션(커밋
`6941bbcd`)이 이 승인 대기 상태를 확인하지 않고 "Book & Class"→About 흡수
부분만 라이브 `header.html`에 직접 반영**했다 — 격리 사본이 있다는 사실 자체는
뒤 세션의 판단을 막지 못했다. 결과: About 링크가 승인 없이 약 14시간 노출.
사장님이 직접 발견(PC/모바일이 다르게 보인다고 보고) → ux-lead 스레드가 GNB
노출만 1차 원복(PR #9)했으나 `noindex`·`sitemap.xml`·`llms.txt`는 그대로 둬
"색인은 되는데 메뉴엔 없는" 어중간한 상태가 남았고, 사장님이 "그것도 봐달라"고
요청해 **PR #10로 같은 건의 범위 전체를 완전히 원복**했다: `about/index.html`
noindex 복원, 두 저서 페이지 `preview:true` 복원, sitemap/llms.txt에서 제거,
GNB의 책 링크도 예스24 외부 링크로 원복. 지금은 검색·사이트맵·GNB·llms.txt
어디에도 안 걸리는 완전히 일관된 "보류" 상태 — 페이지 파일과 `/preview/`는
남아있으니 향후 승인 시 플래그만 되돌리면 재승격 가능하다.

**이 사고에서 나온 규칙(아래 "공통 규칙"에도 반영)**: 스테이징/미리보기 격리
사본을 만들어뒀다는 것 자체는 안전장치가 아니다. 사장님의 명시적 승인 없이는
어떤 세션도 라이브 파일에 반영하지 않는다.

**비공개 저장소(`simplifier-cxo-db`)에 기록 완료** — `decisions/2026-08-30-approval-gate-for-staging-promotion.md`
+ `incidents/2026-08-30-gnb-unauthorized-promotion.md`로 남겼다(완성 문서
방식이 아직 정착 규칙이던 시점). **첫 시도는 Claude Code 자동 모드 분류기가
차단**했지만(사업 관련 비공개 저장소에 새로 push 권한을 붙이는 걸 민감 동작으로
판단한 듯) 사장님이 재시도를 지시하자 두 번째 시도는 통과됐다 — 같은 세션에서
동일 요청을 다시 하면 풀리는 경우가 있다는 뜻이라, 막히면 바로 포기하지 말고
한 번 더 시도해볼 것.

### ⚠️ 사고 기록 (해결됨): 스튜디오 모바일 GNB — 자체 검증이 놓친 진짜 버그

PR #16로 스튜디오 모바일 오버플로를 고쳤다고 검증까지 마쳐 보고했으나, 사장님이
시크릿 모드로도 재현된다고 재확인해줘서 검증 방법 자체를 의심 → 데스크톱
브라우저 뷰포트 리사이즈는 모바일 에뮬레이션이 아니라는 게 근본 원인이었다
(자세한 내용은 `ux-lead.md`, PR #21). **경험DB 인박스 이슈로도 남김**:
[simplifier-cxo-db#1](https://github.com/hansunghee7/simplifier-cxo-db/issues/1).
**후속**: 새로 추가된 `brand-guide.html`(마야 스레드 신설)에서 모바일 메뉴에
새 항목이 안 보인다는 재확인 요청이 있었으나, 재검증 결과 정상 — 사장님도 재확인
완료.

## 🟡 스레드 간 대조 필요하다고 각자 적어뒀던 것 — 해소 상태

- **너비 토큰 체계** — `site-engineering`·`about-books-cta` 둘 다 "겹치는지 대조
  필요"라고 남겨뒀으나, `ux-lead`가 8/30에 `--width-prose/content/data` 3단
  체계로 통합 완료, `docs/UX_GUIDE.md`가 정본. **해소됨.**
- **`main-protect` 룰셋 Disabled** — `site-repo-ops`는 "소관 불명확"이라 적어뒀으나,
  `ai-cto-tutor`가 원인(봇 워크플로가 fine-grained PAT로 커밋하게 전환돼야 Active
  전환 가능)을 이미 파악 중. **ai-cto-tutor 소관으로 정리.**
- **ux-lead ↔ simplifier-studio 스튜디오 UX 영역 중복** — 둘 다 STYLE_GUIDE.md/
  UX_GUIDE.md 동기화를 사실상 같이 보고 있던 것을 사장님이 지적, ux-lead로
  통합. **해소됨(2026-08-30).**
- **About 콘텐츠 vs GNB 구조 경계** — ux-lead가 분리안(콘텐츠=마야/구조=ux-lead)을
  제안했으나, 사장님이 "마야가 최대한 정리해서 진행"으로 확정 — 분리하지 않고
  cmo-marketing이 전담. **해소됨(2026-08-30).**
- **블로그 footer(ux-lead) vs 포스트 하단 CTA(about-books-cta) — 같은 일이었다** —
  사장님이 ux-lead에게 "블로그 587개 글에 footer가 없다, 브런치 벤치마킹 해달라"고
  요청했는데, ux-lead는 착수 전 이 🔴 표를 대조하지 않았다. 정리하려고 코드를
  보다가 `about-books-cta`가 같은 주제(글 끝 작가 카드)를 이미 오늘 버전 A~J까지,
  사장님과 직접 주고받으며 진행 중인 걸 발견 — 브런치에서 찾은 패턴(사진+이름+
  역할+팔로우 카드)을 그쪽은 이미 5개 레이아웃 비교 + 반려 경험 + 외부 벤치마킹까지
  거쳐 더 깊게 검증한 상태였다. ux-lead는 손을 떼고 방향성 확인만 넘겼다.
  **해소됨(2026-08-30)** — 이 주제는 about-books-cta 단독 소관으로 명확화.
  **일반화된 교훈**: 다른 스레드에서 요청받은 게 아니라 **사장님이 직접 준 새
  요청이라도**, 착수 전에 이 🔴 표부터 통째로 훑어야 한다 — "사장님이 시켰으니
  새 일이다"라고 가정하지 말 것.

## 🟢 각 스레드가 자체적으로 진행 (사장님 액션 불필요)

- `ai-cto-tutor`: 2026-08-31 06:00 첫 모닝브리핑 도착 확인, GA4 백업 트리거
  cron-job.org 이전. **참고: GA4 조회(`scripts/fetch_ga4.py`)는 인증정보가 있는
  PC 세션에서만 가능 — 클라우드 세션은 실행 자체가 안 됨(2026-08-30 확인).**
- `simplifier-qa-agent`: `qa_feedback` 👎 로그 리뷰, 골든 테스트셋 구축
- `site-engineering`: `system-map.html`에 `_config.yml`/`build-check.yml`/
  `site-health-check.yml` 반영 여부 확인
- `ux-lead`: `STYLE_GUIDE.md`/`docs/UX_GUIDE.md`/`style-guide.html` 세 문서
  동기화 유지(2026-08-30 simplifier-studio에서 이관). 통합 여부는 검토했고
  **비추천 의견**(읽는 빈도·목적이 달라 합치면 한쪽이 묻힘) — `ux-lead.md` ③절 참고.
- `multi-publish-sns-insight`: 2026-09-27경 네이버블로그 수집 안정성·추세 요약
  추가 여부 재검토 예정(사용자와 합의됨)
- `claude-code-ops`: simplifier-agent GitHub 비공개 저장소 push 상태 확인
- `숏감독`(신규): `shorts-lab` 생성기가 옛 너비 규칙을 쓰는 문제 — 화면 자체는
  `ux-lead`가 만든 `.wrap:has(> .doc)` 특이도 장치로 이미 안전하니 급하지 않음.
- ✅ (완료) 스튜디오 ⓘ 말풍선 뷰포트 오버플로 버그 — `cmo-marketing`이 작업
  칩(`task_cf685175`)으로만 등록해뒀던 걸 `ux-lead`가 전수 검토 중 발견해
  직접 수정(PR #8 → 검증 결함 발견 후 진짜 수정 PR #21, 2026-08-30)
- ✅ (완료) 스튜디오 모바일 가로 스크롤 — `ux-lead`가 Playwright 실측으로
  발견·수정(PR #16, 실기기 에뮬레이션으로 재검증해 진짜 원인까지 잡은
  후속 PR #21, 2026-08-30)

## 공통 규칙 (모든 스레드가 지켜야 함, 정본은 `CLAUDE.md`)

- **스테이징/미리보기 격리 사본은 그 자체로 안전장치가 아니다** (2026-08-29~30
  GNB 무단 승격 사고에서 확립, 위 참고) — `/preview/`나 `-preview.html` 같은
  사본을 만들어뒀어도, 사장님의 명시적 승인 없이는 어떤 세션도 그 내용을
  라이브 파일에 반영하지 않는다. "격리해뒀으니 안전하다"고 판단하지 말 것 —
  반영 여부는 반드시 승인 확인 후.
- **main 직접 push 금지** (2026-08-29 도입) — 작업 브랜치 + PR + auto-merge
  (build-check 통과 조건). 예외: 사장님 본인 직접 커밋, github-actions 자동화 커밋.
- **경험DB 기록은 "완성 문서"가 아니라 "인박스 이슈"로 던진다** (2026-08-30 변경,
  `simplifier-cxo-db`의 `decisions/2026-08-30-inbox-not-finished-docs.md`가 정본) —
  세션이 되돌리기 어려운 결정이나 사고를 다뤘으면, 그 저장소에 `[인박스]` 이슈
  템플릿(`.github/ISSUE_TEMPLATE/inbox.md`)으로 **세 줄이어도 되니 가볍게** 던진다.
  프론트매터 갖춘 `decisions/`·`incidents/` 완성 파일을 직접 쓰지 않는다 — 다듬기는
  주 1회(금요일 모닝 브리핑)가 한다. **"왜 그렇게 판단했는가"는 이슈에만 쓰고,
  공개 저장소 커밋 메시지엔 "무엇을 했는가"만 남긴다.** 그 저장소에 새로 접근
  (특히 push/이슈 작성 권한)하려는 시도는 자동 모드 분류기가 처음엔 막을 수
  있는데, **한 번 더 시도하면 풀리는 경우가 있다** — 막혔다고 바로 포기하지
  말고 사장님께 재시도를 확인받을 것.
- **새 작업(다른 스레드가 준 요청이든, 사장님이 직접 준 요청이든)에 착수하기
  전에 이 문서의 "🔴 사장님 결정 대기" 표를 통째로 먼저 훑는다** (2026-08-30
  블로그 footer/포스트 CTA 중복 착수 근접 사례에서 확립) — 자기 스레드 이름과
  다르게 불려도 이미 다른 스레드가 같은 주제를 더 앞서 다루고 있을 수 있다.
- `git fetch origin <A> <B>` 형태로 브랜치 여러 개 나열해서 받지 말 것 — 하나라도
  없으면 전체가 조용히 실패.
- 이미지 자산 정리는 `scripts/find_orphan_images.py`로만, 절대 즉시 삭제하지 않고
  격리(quarantine)만.
- 인프라를 바꾸면 같은 세션에서 `insight-7b3e9f2c/system-map.html`도 갱신.
- 스튜디오 파일 작업 후 `python scripts/check_studio_style.py` 실행 필수.

## 이 문서를 다시 열게 되면

1. 위 "🔴 사장님 결정 대기" 표부터 확인 — 대부분의 스레드가 사장님 응답 대기 상태라
   병목이 여기 몰려 있을 가능성이 높다.
2. 자기 스레드 파일(`roles/<이름>.md`)을 열어 ②~④절부터 읽는다 — 대화 전체를
   다시 볼 필요 없음.
3. 다른 스레드 파일을 고쳤다면(특히 결정 대기 항목이 해소됐다면) 이 인덱스도
   같이 갱신한다.
