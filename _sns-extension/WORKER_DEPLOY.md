# SNS 확장 GitHub 쓰기 Worker 배포 가이드 (사장님이 할 일)

`worker.js`를 Cloudflare에 올려서, 확장이 GitHub PAT를 직접 안 들고도
SNS 데이터 3개 파일(`sns-insight.json`·`naver-content.json`·
`claude-usage.json`)에 기록할 수 있게 만드는 절차입니다. CMS 로그인용
Worker(`simplifier-cms-auth`)와 같은 계정, 다른 이름으로 하나 더 만듭니다
— 서로 안 건드립니다.

> **이미 클로드 사용량만 처리하는 버전을 배포했다면**: 1~4단계(토큰
> 발급·Worker 생성·Secret 등록)는 다시 안 해도 됩니다. Cloudflare 그
> Worker 화면에서 **"Edit code"** 열어 안의 코드를 이 저장소의 최신
> `worker.js` 내용으로 통째로 교체하고 **Deploy**만 다시 누르면 됩니다
> (파일 3개 허용 목록으로 넓어진 것 외엔 Secret 값 변경 없음).

## 1. GitHub 토큰 새로 만들기 (이 Worker 전용)

1. `github.com` → 오른쪽 위 프로필 → **Settings**
2. 왼쪽 메뉴 맨 아래 **Developer settings**
3. **Personal access tokens → Fine-grained tokens**
4. **Generate new token** 클릭
5. Token name: `claude-usage-writer` (아무 이름이나 가능)
6. Expiration: 원하는 기간 선택
7. Repository access: **Only select repositories** → `hansunghee7.github.io` 선택
8. Permissions → Repository permissions → **Contents**를 **Read and write**로 변경
9. **Generate token** 클릭 → 나오는 `github_pat_...` 값을 **지금 바로 복사**
   (다시 못 봄 — 놓치면 이 토큰 삭제하고 처음부터 다시)

## 2. Cloudflare에서 새 Worker 만들기

1. `dash.cloudflare.com` 접속 (CMS 로그인 Worker 만들 때 쓰던 계정)
2. 왼쪽 메뉴 **Workers & Pages** 클릭
3. **Create** (또는 "Create application" → "Create Worker") 클릭
4. 이름: `simplifier-claude-usage-writer` (아무 이름이나 가능, 나중에
   URL에 그대로 들어감)
5. **Deploy**(일단 기본 코드로 배포) 클릭

## 3. 코드 교체

1. 방금 만든 Worker 화면에서 **Edit code**(또는 "Quick edit") 클릭
2. 에디터 안의 기존 코드를 **전부 지우고**, 이 저장소의
   `_sns-extension/worker.js` 파일 내용을 그대로 붙여넣기
3. **Deploy**(또는 Save and deploy) 클릭

## 4. 비밀 값 두 개 등록

Worker 설정 화면(Settings → Variables and Secrets, 또는 "Environment
Variables")에서 **Secret**(Variable 아님, 반드시 Secret)으로 두 개 추가:

| 이름 | 값 |
|---|---|
| `GITHUB_TOKEN` | 1단계에서 복사한 `github_pat_...` 값 |
| `APP_KEY` | `c670c01273e6b6bd4808ebccf7b5588743dbd09fa560e91d` (탐이 생성, 아래 확장 코드에도 이 값을 그대로 씀) |

등록 후 **Save and deploy**.

## 5. Worker 주소 확인해서 알려주기

Worker 화면 위쪽에 `https://simplifier-claude-usage-writer.<계정이름>.workers.dev`
같은 형태의 주소가 보입니다. 이 정확한 주소를 저(탐)에게 알려주세요 —
그러면 확장 코드에서 그 주소로 호출하도록 마지막으로 연결하겠습니다.

## 확인 방법 (선택)

터미널이나 브라우저 확장 없이도, 아래처럼 확인할 수 있습니다(안 해도 됨,
저와 함께 마지막에 실제로 테스트할 것입니다):

```
curl -X POST https://<위에서 확인한 주소> \
  -H "Content-Type: application/json" \
  -d '{"key":"c670c01273e6b6bd4808ebccf7b5588743dbd09fa560e91d","fields":{"session_5h":1},"capturedAt":"2026-01-01T00:00:00.000Z"}'
```

`{"ok":true}`가 나오면 성공입니다.
