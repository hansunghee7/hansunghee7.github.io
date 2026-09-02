# UTM 규칙

> 왜 있나: 2026-09-02 진단에서 사이트 유입의 대부분이 "direct"로 잡혀 있었다.
> 실제로는 링크드인·페이스북 등 앱 내장 브라우저에서 온 클릭인데, 태그가
> 없어 GA4가 출처를 구분 못 하고 뭉갠 것이다. 어떤 채널·어떤 글의 재유통이
> 실제로 사이트 방문을 만드는지 알아야 다음 채널 선택이 되므로, 심플리파이어
> 계정에서 밖으로(SNS → 사이트) 붙이는 링크에는 항상 아래 세 값을 붙인다.

## 언제 붙이나 / 언제 안 붙이나

- **붙인다**: 링크드인·페이스북·인스타그램·스레드·리멤버·로켓펀치·유튜브·틱톡
  등에서 `simplifier.co.kr`로 연결하는 모든 링크(새 글 알림, 옛글 재유통, 숏폼
  설명란·고정 댓글 등).
- **안 붙인다**: 사이트 안에서 사이트 안으로 가는 링크(예: 홈 → 필러 페이지).
  네이버 블로그·브런치는 우리 계정이 원본을 올리는 곳이라 GA4 세션 소스가
  이미 "브런치"·"네이버"로 정확히 잡힌다 — 태그가 오히려 혼란을 더한다.

## 세 값

| 파라미터 | 값 | 비고 |
|---|---|---|
| `utm_source` | 채널명 (소문자 영문) | `linkedin` / `facebook` / `instagram` / `threads` / `remember` / `rocketpunch` / `youtube` / `tiktok`. `assets/data/sns-insight.json`의 키와 그대로 맞춘다 — 나중에 팔로워 수와 세션을 채널 기준으로 바로 조인할 수 있게 |
| `utm_medium` | 링크가 놓인 자리 | `social`(피드 게시물 본문) / `bio`(프로필 고정 링크) / `video`(숏폼 설명란·고정 댓글) |
| `utm_campaign` | 무엇 때문에 걸었나 | `repost_<글 id>`(옛글 재유통) / `new_<글 id>`(신규 글, 지금은 새 글을 안 쓰므로 당분간 미사용) / `shorts_<에피소드명>`(숏폼 발행, 예: `shorts_ep07`) |

`<글 id>`는 `assets/data/posts.json`의 `id` 필드(예: `615`)를 그대로 쓴다 —
파일명과 URL에 이미 있는 번호라 새로 정할 게 없다.

## 만드는 법 (예시)

옛글 `615_내 인생의 돛, 내가 잡고 있나.html`을 링크드인 피드에 재유통할 때:

```
https://simplifier.co.kr/log_assets/markdown/615_내 인생의 돛, 내가 잡고 있나.html?utm_source=linkedin&utm_medium=social&utm_campaign=repost_615
```

같은 글을 스레드 프로필 고정 링크로도 걸면:

```
...html?utm_source=threads&utm_medium=bio&utm_campaign=repost_615
```

숏폼 `ep07` 설명란에서 부모 글로 연결할 때:

```
...html?utm_source=youtube&utm_medium=video&utm_campaign=shorts_ep07
```

주소에 한글·공백이 섞여도 상관없다 — 브라우저와 GA4가 자동으로 인코딩해서 처리한다.

## 확인하는 곳

`scripts/fetch_ga4.py`가 매일 GA4에서 `sessionSource`·`sessionMedium`·
`sessionCampaignName`을 모아 `assets/data/analytics.json`의 `utm_campaigns`에
저장한다(2026-09-02 추가). 태그 없는 일반 트래픽은 이미 있던 `top_sources`가
다루므로, `utm_campaigns`엔 실제로 태그가 붙은 세션만 나온다 — 처음엔 비어
있다가 재유통을 시작한 다음 날부터 값이 쌓인다.

## 지금 하지 않는 것

- 링크 단축기(bit.ly 등) — 자체 도메인이라 태그 붙은 URL 그대로 붙여도 되고,
  단축기는 새 서비스 종속과 클릭 통계 이원화만 늘린다.
- `utm_content`(같은 글의 이미지/문구 A·B 테스트 구분) — 재유통 자체의 효과를
  먼저 보고, 채널 간 차이가 확인된 다음에 추가해도 늦지 않다.
