# 사장님용: WorkOS AuthKit 프로젝트 issuer 찾기 (5분)

> 연휴 끝나고 여유 있을 때 하시면 됩니다. AuthKit JWT 검증기 스파이크(PR #104)를
> 실제 WorkOS 환경으로 마지막 검증하는 데 필요한 값 하나(issuer 주소)만
> 찾으면 됩니다. 지투가 정리 요청(2026-09-24), 노트 작성.

## 1단계: 대시보드 열기

아래 링크를 클릭해서 로그인하세요(이번 OAuth 스파이크 때 이미 로그인해두신
계정 그대로입니다).

https://dashboard.workos.com/

## 2단계: AuthKit 도메인 찾기

로그인하면 좌측 메뉴에 여러 항목이 보입니다. 아래 중 하나에서 `authkit.app`으로
끝나는 주소(예: `xyz1234.authkit.app`)를 찾으세요:

- 좌측 메뉴 **"Authentication"** 또는 **"AuthKit"** 항목
- 좌측 메뉴 **"Developer" → "API Keys"** (Client ID 옆에 같이 보일 수 있음)
- 대시보드 첫 화면(Overview)에 "AuthKit domain" 같은 이름으로 표시될 수 있음

⚠️ 정확한 메뉴 이름은 제가 직접 화면을 본 게 아니라 WorkOS 공식 문서 기준으로
적은 것이라 실제 화면과 표현이 다를 수 있습니다. 못 찾으시면 **그 화면을
캡처해서 클로드 코드(노트)에게 보여주세요** — 이번 OAuth 스파이크 때처럼
화면 보고 바로 다음 단계를 알려드릴 수 있습니다.

## 3단계: 찾은 주소가 맞는지 확인 (선택, 확실히 하고 싶으면)

터미널(PowerShell)을 열고 아래 명령을 실행하세요. `xyz1234.authkit.app` 자리에
2단계에서 찾은 주소를 넣으세요.

```bash
curl https://xyz1234.authkit.app/.well-known/oauth-authorization-server
```

화면에 `"issuer": "https://xyz1234.authkit.app"` 같은 JSON이 나오면 맞는
주소입니다. 에러가 나면 주소가 틀린 것이니 2단계로 돌아가세요.

## 4단계: 저에게 알려주기

찾은 주소를 그대로 대화창에 붙여넣어 주시면, 제가 나머지(실제 연결 검증)를
진행하겠습니다. 별도로 만드시거나 설정하실 건 없습니다 — 주소 하나만 있으면
됩니다.

---
근거: PR #104(simplifier-saegim), WorkOS 공식 문서
(workos.com/docs/authkit/mcp, workos.com/docs/dashboard).
