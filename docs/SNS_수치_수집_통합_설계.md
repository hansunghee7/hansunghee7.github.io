# SNS 수치 수집 통합·API 우선 설계 (2026-10-06, 탐)

> 사장님 지시 10/6: 크롬 확장·구PC 크롤·공식 API·컴포지오로 모은 정보를 통합하고 과거 기록을 정리하며, 앞으로의 수집은 안정성이 높고 API 커버리지가 높은 방향으로 설계한다. 분석은 핏·마야, DB 관리는 탐. 관련 대장 N103·N14·N156, 공정 카드 마야 #2·#3·#8.

## 결론

- 글별 수치는 운영 DB 세 표(`channels`·`content_items`·`metrics_snapshots`)에 **출처 이름(source)을 붙여 한곳에** 쌓는다. 어떤 경로로 모았든 같은 표, 같은 열이다.
- 수집 순서는 **공식 API → 컴포지오(관리형 OAuth) → 구PC 화면 읽기 → 크롬 확장** 순으로 정한다. 위쪽이 안정적이고, 아래쪽은 API가 없는 채널의 마지막 수단이다.
- 오늘 이관한 것: 컴포지오 인스타 2계정 68글, 공식 Meta API 인스타 17글, 네이버 클립 크롤 이력 4일치. `metrics_snapshots` 34행에서 184행이 됐다.

## 현황: 4경로를 실측한 사실

- **공식 API**(비공개 저장소 `carvit-insight-data`, 하루 2회 워크플로): 유튜브 Analytics(영상별·일별), 인스타 sinkihanapt(글별 좋아요·댓글·조회·도달·저장·공유·평균 시청), GA4. 가장 안정적이다. 약점은 10/6 새벽 두 수집이 동시에 push해 한쪽이 거부된 경합(수정 PR이 `carvit-insight-data`에 열려 있음)과 계정마다 토큰이 따로 필요하다는 점이다.
- **컴포지오**(`maya_collect.py`, 하루 1회, 10/6 등록): 인스타 simplifier_seoul 50글·sinkihanapt 18글의 좋아요·댓글·조회·도달·저장·공유. 링크드인은 읽기 도구가 없고(글 올리기·삭제·내 정보·회사 정보 4개뿐), 페이스북 Page는 연결됐지만 글 조회가 OAuth 190 오류다. 연결 링크는 10분 만료, 연결 계정은 로그인된 브라우저 계정을 따른다.
- **구PC 화면 읽기**(`sns_read.py`, Playwright): 네이버 클립 글별 조회(일별 이력 4일치), 레트로 실사판 파일럿 글의 채널별 좋아요(`simplifier_posts.json`). 구PC 크롬이 켜져 있어야 하고 화면이 바뀌면 깨진다.
- **크롬 확장**(`assets/data/sns-insight.json`): 8개 채널(링크드인·페이스북·인스타·로켓펀치·스레드·리멤버·네이버 블로그·브런치)의 **팔로워 일별 시계열만**이다(8/27~10/6). 글별 수치가 없고 사장님 기기에 의존한다. 스레드는 5일치뿐이다.

## 통합 모델

- **채널**(`channels`): `ig-<계정>`, `naver-clip`, `yt-main`처럼 계정 단위 한 줄. `platform`은 instagram·naverclip·youtube 등.
- **콘텐츠**(`content_items`): 플랫폼이 주는 글 id를 `ig-<미디어id>`처럼 붙여 같은 글이 어느 경로로 와도 한 줄이 되게 한다. `kind` 제약은 longform·short·post뿐이다(릴스·영상=short, 이미지·캐러셀=post).
- **스냅샷**(`metrics_snapshots`): 덮어쓰지 않고 시점별로 쌓는다. 열은 조회·좋아요·댓글, `source`가 경로 이름(meta-api, composio-ig, pc-crawl, yt-dlp)이다. 하루 한 번만 쌓이게(멱등) 적재한다.
- **같은 글이 두 경로에서 올 때**: 분석은 `source` 우선순위(공식 API > 컴포지오 > 크롤)로 한 값을 고르고, 나머지는 교차 검증용으로 남긴다.
- **아직 표에 없는 것**: 계정 단위 팔로워 일별 시계열(크롬 확장 데이터 256점)과 도달·저장·공유. 아래 "필요한 변경"에 있다.

## 채널별 커버리지와 다음 후보

- 유튜브: 공식 API 완비. 추가 작업 없음.
- 인스타: 공식 API(sinkihanapt)와 컴포지오(simplifier_seoul, sinkihanapt)가 겹쳐 있다. 완비.
- GA4: 공식 API 완비(글별 유입은 UTM의 `utm_content` 글 번호 필요).
- 스레드: **공식 Threads API가 글별 조회·좋아요를 준다**(마야 리서치 10/6, 미검증). 지금 팔로워만 크롬 확장으로 5일치라서, API 커버리지를 가장 크게 늘릴 후보 1순위다. 필요한 것은 사장님의 메타 개발자 계정 로그인 1회다.
- 페이스북 Page: 컴포지오 연결은 됐고 OAuth 190 오류를 풀면 열린다. 신원 확인(Meta 368) 해제 여부가 의심 원인(미확정). 풀리면 2순위.
- 페이스북 개인 프로필·링크드인·리멤버·로켓펀치·네이버 블로그·브런치·네이버 클립: 개인 대상 공식 API가 없거나 심사형이라 화면 읽기가 남는다. 링크드인 `r_member_postAnalytics`는 심사형(마야 실사 10/6)이라 자동 수집 1순위로 두지 않는다.

## 수집 설계 원칙

- API가 있는 채널은 화면 읽기를 쓰지 않는다. 화면 읽기는 채널별로 "API 없음"이 확인된 뒤에만 쓴다.
- 새 수집은 모두 `jobs.toml` 감시 대장에 올리고 종료 코드로 실패를 드러낸다(0건이면 실패).
- 모든 적재 스크립트는 멱등이고, 값은 비밀을 담지 않는다(토큰은 금고 경유).
- 크롬 확장은 팔로워 시계열의 마지막 수단이다. 같은 값을 구PC 화면 읽기나 API가 대신하면 퇴역한다(N33 퇴역 조건).
- 경로를 바꿔도 분석 쪽(핏·마야)은 같은 세 표만 읽는다.

## 이관 상태 (10/6 실측)

- 완료: 컴포지오 인스타 68글, 공식 Meta API 인스타 17글(source meta-api), 네이버 클립 크롤 4일치 65점(source pc-crawl). 스크립트: `maya_metrics_to_db.py`, `insight_history_to_db.py`. 두 번 돌려 두 번째가 0건인 것을 확인했다.
- 대기: 유튜브 영상별 일별(youtube_deep, `metrics_snapshots`에 일별 시점 적재), 레트로 실사판 파일럿 채널별 좋아요(`simplifier_posts.json`). 팔로워 시계열은 아래 표 신설 뒤 이관한다.

## 필요한 변경 (사장님 승인 필요: 운영 DB 표 추가)

계정 단위 팔로워 일별 시계열을 담을 표 `account_snapshots`가 필요하다. 지금 `kpi_daily`는 md 거울이라 인스타·네이버 팔로워 칸이 대부분 빈칸이고 8개 채널을 담지 못한다. 되돌리기는 `drop table account_snapshots`다.

```sql
create table account_snapshots (
  id bigint generated always as identity primary key,
  channel_id text not null references channels(id),
  day date not null,
  followers integer,
  source text not null,
  captured_at timestamptz not null default now(),
  unique (channel_id, day, source)
);
```

적용 뒤 `sns-insight.json`(8채널 256점)과 인스타 공식 API 팔로워 이력을 한 번에 넣고, 크롬 확장은 이 표를 다른 경로가 채우게 되면 퇴역을 검토한다.

## 한계

- 공식 Meta API와 컴포지오가 같은 계정(sinkihanapt)을 겹쳐 읽는 정도는 아직 대조하지 않았다(좋아요 수 일치 여부).
- 스레드 API·링크드인 심사 가능 여부는 공식 문서 확인 전이다.
- 도달·저장·공유는 JSON 원본에만 있고 표에 열이 없다.
