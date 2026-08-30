# simplifier-studio — 스튜디오 저장소 위생 스레드 요약

> **2026-08-30 범위 축소(사장님 직접 지시)**: 이 스레드가 갖고 있던 **UX/거버넌스
> 영역**(STYLE_GUIDE.md 정본 관리, ⓘ info-dot 패턴, studio.css/js 공용 인프라,
> `.doc` 문서형 패턴)은 [ux-lead.md](ux-lead.md)로 흡수됐다 — 두 스레드가 사실상
> 같은 일(스튜디오 UX 표준)을 각자 이름으로 하고 있었기 때문("홈+스튜디오 UX는
> 시안" 지시). 아래 ②절의 UX 관련 결정사항은 **역사 기록으로 그대로 남겨두되**,
> 앞으로 그 영역의 정본·다음 작업은 `ux-lead.md`를 본다. 이 스레드는 이제
> **저장소 위생**(이미지·시크릿·GitHub Actions 감사 등 UX가 아닌 것)만 전담한다.

## ① 목적과 범위
~~`insight-7b3e9f2c/`(Simplifier Studio, 비공개 관리자 도구) 내부의 UX·기술 일관성을
구축·유지하는 스레드.~~ (2026-08-30부터 이 부분은 ux-lead 소관 — 위 안내 참고)

**현재 범위**: 저장소 전체(블로그 본문, 이미지 자산, git 히스토리, GitHub Actions)
위생 감사. 페이지가 9개→15개로 늘면서 각자 스타일을 복붙하다 어긋나기 시작한 게
이 스레드의 시작 계기였고, 그 과정에서 파생돼 저장소 전체 위생 감사까지 맡게 됐다.

## ② 확정된 주요 결정사항 (UX 부분은 역사 기록 — 정본은 ux-lead.md)
- **studio.css/studio.js 공용화**: 15개 스튜디오 페이지가 `:root` 토큰·헤더·
  `#adminShellNav`·ⓘ 버튼·새로고침 버튼 CSS/JS를 각자 인라인으로 복붙하던 걸
  공용 파일 두 개로 통합. 새 메뉴는 `studio.js`의 `STUDIO_NAV` 배열 한 곳만 고치면 됨.
  **(→ ux-lead.md로 이관)**
- **ⓘ info-dot 패턴 확정, `title=` 네이티브 툴팁 전면 금지** — 클릭/탭에 반응 안
  하는 죽은 버그가 2회 발견(book/sns-insight 초기 버전, 외부 shorts-lab 파이프라인)
  돼서 확정. 배치 원칙: 설명 대상 바로 옆에, `margin-left:auto`로 구석에 밀지 않음.
  **(→ ux-lead.md로 이관, 2026-08-30에 모바일 오버플로 버그까지 추가로 발견·수정됨)**
- **거버넌스 3종 세트 구축**: `insight-7b3e9f2c/STYLE_GUIDE.md`(스튜디오 전용 규칙,
  실제 사고 기록 포함) + `scripts/check_studio_style.py`(FAIL=자동판정/WARN=사람판단
  구분, 15개 파일 FAIL 0건 유지 중) + `CLAUDE.md`에서 새 세션이 자동으로 보게 연결.
  **(→ ux-lead.md로 이관)**
- **외부 생성 페이지도 root-cause 수정**: `shorts-studio.html`을 매번 새로 쓰는
  `shorts-lab/pipeline/build_studio_site.py`(별도 저장소) 자체를 studio.css/js
  패턴에 맞게 재작성 — HTML만 patch하면 다음 재생성 때 되돌아가는 문제 방지.
  **(→ ux-lead.md로 이관)**
- **`.doc` 패턴 확립**: 긴 마크다운 문서(숏폼 공정 정본 등, 나중엔 스타일
  가이드 자신도)를 읽기용으로 렌더링하는 두 번째 스튜디오 UX 패턴. 대시보드형
  (1100~1600px, 데이터 밀도)과 문서형(760px 안팎, 가독성 우선)이 공존 — 폭이
  다르게 보이는 건 버그 아니고 의도. **(→ ux-lead.md로 이관)**
- **저장소 전체 감사 완료(2026-08-29)** — **이 스레드가 계속 정본**: 카테고리
  오타 없음, prev/next 링크 603개 전수 무결, git 히스토리 시크릿 노출 0건,
  GitHub Actions 5개 전부 최근 실행 success, 블로그 본문 alt 텍스트 오염 6건
  수정, 고아 이미지 743개 삭제 + 69개 `log_assets/images_quarantine_2026-08-29/`
  로 격리(README에 확인법 기록).
- **`docs/UX_GUIDE.md` 신설** — 공개 홈페이지 + 스튜디오를 아우르는 공통 원칙
  정리. **(→ ux-lead.md로 이관)**
- **다른 스레드가 `CLAUDE.md`에 추가한 최신 규칙 확인**: main 직접 push 금지
  (작업 브랜치+PR+auto-merge, github-actions/사장님 직접 커밋만 예외),
  이미지 정리는 `scripts/find_orphan_images.py`로만(로고 오탐 사고 이후 의무화),
  `system-map.html`은 인프라 변경과 같은 세션에서 갱신. **(이 스레드도 계속 지킴)**

## ③ 진행 중이거나 남아있는 작업
- [ ] `log_assets/images_quarantine_2026-08-29/`의 미확인 이미지 69개 — 확실해질
      때까지 보류, README 기준으로 사람이 최종 삭제 판단. **(이 스레드 소관 유지)**
- [x] ~~`STYLE_GUIDE.md`/`docs/UX_GUIDE.md`/`style-guide.html` 3중 동기화~~
      **→ ux-lead.md로 이관(2026-08-30)**
- [x] ~~공개 사이트에도 ⓘ 패턴 필요한 지점 검토~~ **→ ux-lead.md로 이관(2026-08-30)**

## ④ 다음에 이어서 할 일
1. `images_quarantine_2026-08-29/` 재확인 시점이 되면 README 보고 최종 삭제
   여부 판단.
2. 이 스레드가 다시 열리면 이 파일 상단 안내부터 확인 — UX/거버넌스 질문이면
   `ux-lead.md`로, 저장소 위생(이미지·시크릿·Actions 감사)이면 계속 여기.
3. `roles/README.md`의 스레드 경계표도 이 범위 축소를 반영해뒀는지 확인.
