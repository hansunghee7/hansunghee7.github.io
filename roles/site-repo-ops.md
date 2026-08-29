# site-repo-ops — hansunghee7.github.io 저장소 운영(노트북) 스레드 요약

## ① 목적과 범위
특정 기능 개발이 아니라 **hansunghee7.github.io(Simplifier 블로그) 저장소 자체의
상태를 유지보수하는 실무 스레드**. 노트북에서 시작됐고, 배포 사고 대응, 이미지/
템플릿 버그 감사, 저장소 구조 점검, 그리고 여러 클로드 세션이 이 저장소를 동시에
건드릴 때의 git 충돌 조율이 핵심 주제. `claude-code-ops`([roles/claude-code-ops.md](claude-code-ops.md))가
"클로드 코드를 어떻게 쓸지"를 다루는 메타 스레드라면, 이 스레드는 "이 저장소 하나"의
실제 운영을 다룸.

## ② 확정된 주요 결정사항
- **이미지 격리 사고 복구 (2026-08-29)**: 자산 정리 작업이 사이트 로고(`logo_white.png`)와
  JSON-LD용 캐릭터 이미지(`character_black.png`)를 오탐 격리해 로고가 깨졌던 걸 발견,
  `git mv`로 복구. 원인은 참조 검사 범위가 `log_assets/markdown/`(블로그 글 본문)에만
  한정돼 템플릿(`_includes/`, `_layouts/`)에서만 쓰이는 파일을 못 걸러냈기 때문.
- **재발 방지 스크립트 완료**: `scripts/find_orphan_images.py` 작성·커밋. 참조 검사를
  저장소 전체(git grep)로 넓히고, 브랜드 자산은 이름 패턴으로 이중 보호하며, 절대
  자동 삭제하지 않고 격리(quarantine)만 함. 절차는 `CLAUDE.md`의 "이미지 자산 정리"
  절에 정본으로 남김.
- **푸터 누락 버그 발견/수정**: `_layouts/pillar.html`(카테고리 허브 12개 페이지가
  공유하는 레이아웃)에 `{% include footer.html %}`이 아예 없었음 — 라이브에서
  `hasFooter:false` 확인 후 추가. `default.html`/`book.html`은 정상.
- **커밋 교통정리(PR + auto-merge) 프로세스를 이 스레드에서 실제로 사용**: main 직접
  push가 금지된 뒤 첫 사례로 `claude/progress-notes-2026-08-30` 브랜치 → PR #2 →
  머지까지 진행. `gh` CLI가 노트북에 없어서 GitHub REST/GraphQL API를 git credential의
  토큰으로 직접 호출해 PR은 열었으나, auto-merge 활성화(GraphQL mutation)는 권한
  classifier가 차단해 사장님이 직접 버튼을 눌러 머지함.
- **여러 세션의 동시 작업 디렉토리 공유 문제 확인**: 이 노트북에서 다른 스레드(너비
  정책/Studio UX 작업)가 같은 로컬 폴더를 쓰다 보니, 그쪽이 `git checkout main`을
  하면 이쪽 작업 결과물이 로컬에서 사라진 것처럼 보이는 혼란이 반복됨(원격엔 안전하게
  있었음). `git stash` + `ListAgents`/`SendMessage`로 그때그때 조율했음. **이번 역할
  파일 작업부터 `git worktree`로 전환**해 별도 디렉토리(`hansunghee7.github.io-roles-notes`)에서
  작업 — main 체크아웃을 건드리지 않는 더 나은 방법으로 확인.

## ③ 진행 중이거나 남아있는 작업
- [ ] **로그 홈(`log.html`) 무한 스크롤 문제 미해결** — 블로그 글 587건을 전부 한
  페이지에 20개씩 배치로 렌더링하는 방식이라, 전체를 펼치면 페이지 높이가 약
  49,000px(화면 68개 분량)까지 늘어나 푸터에 사실상 도달 불가능. 자동화 브라우저로
  스트레스 테스트 중 탭이 반복적으로 죽는 현상도 관찰됐으나 실제 사용자 브라우저
  재현 여부는 미확인. `docs/진행상황.md`에 기록만 해두고 코드 수정은 안 함.
- [ ] **`gh` CLI 미설치** — 이 노트북에 없어서 PR 생성/auto-merge를 API 직접 호출로
  우회함. 앞으로 커밋 교통정리 절차를 자주 쓸 거면 설치 권장.
- [ ] **룰셋 `main-protect`가 아직 Disabled 상태** (`docs/진행상황.md` 참고) — 봇
  워크플로가 PAT로 전환돼야 Active 전환 가능. 이 스레드 소관인지 다른 스레드
  소관인지 불명확, 확인 필요.

## ④ 다음에 이어서 할 일
1. `log.html` 무한 스크롤 개선안 설계(페이지네이션 도입 또는 배치/총 렌더링 개수
   제한) — 아직 착수 전, 사장님 확인 후 진행.
2. 이 저장소에서 여러 스레드가 동시에 돌 때 **`git worktree`를 표준 관행으로 삼을지**
   결정하고, 그러기로 하면 `CLAUDE.md`의 "여러 기기에서 작업할 때" 절에 반영.
3. `main-protect` 룰셋 Active 전환 진행 상황을 다른 스레드와 조율해 확인.
4. 이 스레드가 다시 열리면 이 파일부터 참고해서 이어서 시작할 것 — 대화 전체를
   다시 읽을 필요 없음.
