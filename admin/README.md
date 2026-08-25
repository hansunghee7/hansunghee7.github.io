# Simplifier Log 글쓰기 (Decap CMS)

`/admin/` 페이지에서 로그인하면 브라우저에서 바로 글을 쓰고 저장할 수 있습니다.
저장하면 이 저장소의 `log_assets/markdown/`에 파일이 커밋되고, GitHub Actions
(`.github/workflows/publish-pipeline.yml`)가 자동으로:

1. 파일명에 순번을 붙이고, 발행일 표시 텍스트를 채우고, 카테고리 링크 스크립트를 넣고
2. 이전글/다음글 링크를 다시 계산하고
3. `log.html` 카드 목록에 새 카드를 추가하고
4. 홈페이지 미리보기가 읽는 `assets/data/posts.json`을 갱신합니다.

**아직 안 된 것 하나**: 로그인이 되려면 GitHub OAuth 앱 하나와, 그 로그인을
중계해줄 아주 작은 서버(프록시) 하나가 필요합니다. GitHub이 브라우저에서
직접 로그인 토큰을 내주지 않기 때문에 이 저장소 파일만으로는 끝낼 수 없는
유일한 단계입니다. 아래 순서대로 하시면 됩니다 (10분 내외, 전부 무료).

## 1) GitHub OAuth 앱 만들기

1. https://github.com/settings/developers 접속 → **New OAuth App**
2. 아래처럼 입력:
   - Application name: `Simplifier Log CMS` (아무 이름이나 무방)
   - Homepage URL: `https://hansunghee7.github.io`
   - Authorization callback URL: `https://<3번에서 만들 프록시 주소>/callback`
     (예: `https://simplifier-cms-auth.<본인계정>.workers.dev/callback`
     — 정확한 주소는 3번을 먼저 끝낸 뒤 다시 와서 채워도 됩니다)
3. **Register application** 클릭 → **Client ID**가 보입니다
4. **Generate a new client secret** 클릭 → 나오는 값을 복사해둡니다
   (이 화면을 벗어나면 다시 못 봅니다)

## 2) Cloudflare 계정 (없다면)

https://dash.cloudflare.com/sign-up 무료 가입. 카드 등록 불필요.

## 3) OAuth 프록시를 Cloudflare Worker로 배포

[`sterlingwes/decap-proxy`](https://github.com/sterlingwes/decap-proxy)를 씁니다
— Decap CMS 전용으로 만들어진, 딱 이 역할만 하는 작은 오픈소스 프록시입니다.

1. 위 저장소 페이지 오른쪽의 안내(README)대로 Cloudflare Worker에 배포합니다.
   (`Deploy to Cloudflare Workers` 버튼이 있으면 그걸 누르는 게 제일 빠릅니다.
   버튼이 안 보이면 README의 `wrangler` 배포 안내를 따라갑니다 — 이 부분은
   막히면 저한테 화면을 보여주시면 같이 진행하겠습니다.)
2. 배포 시 환경변수로 1번에서 만든 **Client ID**, **Client Secret**을 넣습니다.
3. 배포가 끝나면 `https://아무개.workers.dev` 같은 주소가 나옵니다 — 이게
   프록시 주소입니다.
4. 1번의 OAuth 앱 설정으로 돌아가서 **Authorization callback URL**을
   `https://<그 주소>/callback`으로 정확히 맞춰줍니다.

## 4) 이 저장소에 프록시 주소 반영

`admin/config.yml`의 `backend.base_url` 값을 3번에서 받은 주소로 바꿔서
커밋 · 푸시합니다.

```yaml
backend:
  name: github
  repo: hansunghee7/hansunghee7.github.io
  branch: main
  base_url: https://아무개.workers.dev   # <- 여기
```

## 5) 확인

`https://hansunghee7.github.io/admin/`에 접속해서 **Login with GitHub**을
누르면 GitHub 로그인 창이 뜨고, 승인하면 CMS 화면으로 들어갑니다. 이때부터
글쓰기·수정이 전부 브라우저에서 됩니다.

---

## 참고: 로그인 없이 미리 테스트해보기 (선택)

Node.js가 설치된 PC라면, 위 OAuth 단계를 하기 전에도 로컬에서 필드 구성이
어떻게 보이는지 미리 볼 수 있습니다.

```bash
npx decap-server
```

띄운 채로 `/admin/`을 열면(현재 `admin/config.yml`에 `local_backend: true`가
켜져 있어) 로그인 없이 로컬 파일을 직접 편집하는 모드로 들어갑니다. 실제
운영(다른 기기에서 글쓰기)에는 위 1~5번의 GitHub 로그인 경로가 필요합니다.

## 다음 단계 (아직 안 만든 것)

- 링크드인/페이스북/인스타그램/스레드 자동 발행: Buffer 또는 Zapier에 RSS
  피드를 연결하는 방식으로, 홈페이지 쪽에 RSS 피드를 먼저 만들어야 합니다.
  이건 CMS가 실제로 한 번 써보고 잘 돌아가는 걸 확인한 뒤에 이어서
  만드는 게 안전합니다.
- 브런치/네이버블로그/리멤버 커넥트/로켓펀치: 공개 API가 없어 자동화 불가.
  글쓰기 화면의 "수동 발행 채널용 복사 텍스트" 필드에 쓴 내용을 그대로
  복사해서 붙여넣는 방식입니다.
