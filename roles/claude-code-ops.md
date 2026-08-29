# claude-code-ops — 클로드와의 Q&A 스레드 요약

## ① 목적과 범위
특정 프로젝트 업무가 아니라 **"클로드 코드를 어떻게 운영할 것인가"를 다루는 메타 상담 스레드**. 건강/작업습관 상담과, PC·노트북을 오가며 여러 프로젝트(hansunghee7.github.io, shorts-lab, simplifier-agent)를 안전하게 병행하기 위한 워크플로우 설계가 핵심 주제.

## ② 확정된 주요 결정사항
- **작업 환경**: 데스크톱 앱(Local 세션)은 그 PC에서만 보이고 노트북과 공유 안 됨 — 기기 독립적으로 이어가려면 **claude.ai/code에서 항상 Cloud(Default) 환경으로 새 세션을 시작**하기로 확정. 채팅 입력창 바로 위 ☁️ 아이콘에서 한 번만 Cloud로 설정해두면 이후 세션에 계속 적용됨.
- **Local이 실제로 필요한 유일한 경우**: simplifier-agent의 책 PDF(`book_sources/`, .gitignore 대상)를 갖고 `ingest.py`를 다시 돌릴 때. → 해결책으로 **PDF를 Supabase Storage에 올리고 ingest.py가 거기서 읽도록 바꾸면 이마저도 Cloud에서 가능**해짐(아직 미실행, 다음 단계 후보).
- **여러 Local 스레드(CXO/AI CTO/CMO/Notebook 등)의 내용을 이어가는 법**: `/export`로 대화 내보내서 새 Cloud 세션에 붙여넣는 방법 대신, **각 스레드가 스스로 자기 역할을 요약해 `roles/<파일명>.md`로 커밋하는 방식**을 채택. 라이브 사이트(main)에 영향 안 주려고 **`roles-notes`라는 별도 브랜치**를 만들어 거기에만 커밋하기로 함(이 파일도 그 브랜치에 있음).
- **Cloud 환경은 사용량(Max 한도) 소진 속도에 영향 없음** — Local이든 Cloud든 같은 한도 공유, 추가 과금 없음. 다만 동시에 여러 세션을 켜두면(예: 한때 "실행 중인 작업 7개") 총 소비 속도는 당연히 빨라짐.
- **shorts-lab 저장소는 다른 스레드가 실시간으로 작업 중인 상태를 확인**했음 — 이 스레드에서는 절대 건드리지 않기로 함(충돌 방지 원칙).
- **simplifier-agent(RAG 챗봇) 프로젝트 상태 점검 완료**: 콘텐츠 임베딩 100% 완료, Cloudflare Worker 배포 완료, `ask.html`에서 실제 질문-답변 테스트까지 성공 확인. 이 저장소에 git이 아예 없었던 걸 발견해 **로컬 git init + 첫 커밋** 완료(비공개 GitHub 저장소 생성은 사용자가 진행 중).

## ③ 진행 중이거나 남아있는 작업
- [ ] simplifier-agent GitHub 비공개 저장소 생성 후 push (gh CLI 없어서 사용자가 웹에서 직접 repo 생성 필요, 이후 원격 연결은 이어서 처리)
- [ ] (선택) simplifier-agent의 book_sources PDF를 Supabase Storage로 옮기고 ingest.py 수정 — Local 의존성 완전 제거용, 급하지 않음
- [ ] 다른 스레드들(CXO/AI CTO/CMO/Notebook 등)이 각자 `roles/*.md`를 다 올리고 나면, **통합 정리(교통정리) Cloud 세션**을 열어 `roles/README.md`로 인덱스화하고 겹치는 내용 정리 필요

## ④ 다음에 이어서 할 일
1. 사용자가 simplifier-agent GitHub repo 생성 완료했는지 확인 → 완료됐으면 원격 추가하고 push
2. `roles/` 폴더에 다른 스레드 파일들이 쌓였는지 확인 (`roles-notes` 브랜치) → 다 모이면 통합 정리 세션 진행
3. 이 세션은 "메타 운영 상담" 역할이므로, 앞으로도 Claude Code 사용법·워크플로우·여러 프로젝트 교통정리 관련 질문이 오면 이 파일을 먼저 참고
