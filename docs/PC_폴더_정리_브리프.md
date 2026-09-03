# PC·노트북 폴더 정리 — 로컬 세션 브리프 (진단, Phase 1)

> 사장님 PC/노트북에서 직접 실행되는 클로드 코드 세션이 읽고 진행하는 작업
> 지시입니다. 숏(클라우드 세션)이 2026-09-04 작성.
>
> 배경(`docs/진행상황.md` 백로그): 프로젝트 폴더·에피소드별 폴더를 찾기
> 어렵다는 신고(2026-09-04). 사장님 추정으로는 윈도우 계정별 폴더가 2개
> 생겨서(흔한 원인: OneDrive가 "문서"를 리다이렉트하면서 로컬 문서 폴더와
> 이중으로 생기는 것) 파일이 흩어진 것 — 아직 미확인, 이 브리프가 확인한다.
>
> **이 브리프는 진단만 한다.** 이동·삭제는 이 브리프 범위 밖 — Phase 1 결과를
> 사장님이 보고 승인한 뒤, 별도 Phase 2 브리프로 진행한다.

## Objective

이 컴퓨터(PC 또는 노트북, 각자 따로 실행)에서 프로젝트 폴더가 실제로 몇
군데에 흩어져 있는지, 원인이 무엇인지(계정 중복·OneDrive 리다이렉트 등)를
사람이 읽을 수 있는 표로 정리한다. **파일은 한 개도 옮기거나 지우지 않는다.**

## Context

- 증상: `shorts-lab`·`shorts-lab-pilot` 같은 프로젝트 폴더, 그 안의 에피소드별
  폴더를 찾기 어려움.
- 이번 파일럿 세션에서 확인된 사실: `shorts-lab-pilot`은
  `~\Documents\shorts-lab-pilot`(PowerShell `$HOME\Documents` 기준)에
  클론됨 — 이 위치가 "정답"인지, 다른 곳에도 같은 이름 폴더가 더 있는지가
  이번 진단의 핵심.
- 이 문서는 **PC와 노트북 둘 다 대상**이지만, 실행은 기기별로 따로 한다 —
  두 기기의 계정 구성이 같다는 보장이 없다.

## Constraints

- **Phase 1은 읽기 전용이다.** `Remove-Item`, `Move-Item`, `Rename-Item` 등
  파일을 바꾸는 명령을 이 단계에서 실행하지 않는다.
- **지금 다른 파이프라인이 그 폴더를 쓰고 있으면 안 된다** — 시작 전에
  `Get-Process`로 python·ComfyUI·claude 등 관련 프로세스가 떠 있는지 확인.
  떠 있으면 그 작업이 끝난 뒤 다시 시작한다.
- **새 터미널 창**에서 실행한다 — 다른 작업이 진행 중이던 창을 재사용하지
  않는다.
- 나중에(Phase 2) 실제로 정리할 때도 **애매한 건 지우지 말고 격리**
  (이름 그대로 유지한 채 `_정리대기` 같은 폴더로 옮기기만) — 이 저장소의
  `image-cleanup` 스킬과 같은 원칙("모르면 격리, 삭제 아님"). 확실히
  지워도 되는 것만 사장님이 개별 확인 후 삭제.

## 진행 순서 (Phase 1 — 진단)

1. **계정 확인**
   ```powershell
   whoami
   $env:USERPROFILE
   Get-LocalUser | Select-Object Name, Enabled
   ```
   실제 로그인 가능한 로컬 계정이 몇 개인지 확인.

2. **"문서" 폴더가 실제로 어디를 가리키는지 확인** (OneDrive 리다이렉트 여부)
   ```powershell
   $env:OneDrive
   Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" | Select-Object Personal, Desktop
   ```
   `Personal` 값이 `C:\Users\<계정>\OneDrive\Documents`면 리다이렉트된 것 —
   탐색기에서 보이는 "문서"와 PowerShell `~`가 가리키는 곳이 이거다.
   `C:\Users\<계정>\Documents`(OneDrive 아닌 경로)에도 파일이 남아있는지
   별도로 확인.

3. **프로젝트 폴더 전수 검색** — `C:\Users` 전체에서 알려진 프로젝트명으로
   찾는다(계정마다, OneDrive 안팎 모두 걸리게):
   ```powershell
   Get-ChildItem -Path C:\Users -Directory -Recurse -Depth 5 -ErrorAction SilentlyContinue |
     Where-Object { $_.Name -match 'shorts-lab|hansunghee7' } |
     Select-Object FullName, LastWriteTime,
       @{N='크기(MB)';E={ [math]::Round((Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1MB,1) }}
   ```
   (전체 디스크 아니라 `C:\Users`로 좁혀서 실행 시간을 줄인다. 필요하면
   사장님이 아는 다른 프로젝트명도 `-match` 패턴에 추가.)

4. **결과를 표로 정리** — 다음 형식으로 사장님께 제시:

   | 프로젝트 | 발견된 경로 | 최종 수정일 | 크기 | 추정 |
   |---|---|---|---|---|
   | shorts-lab-pilot | `C:\Users\PC\Documents\shorts-lab-pilot` | (실측) | (실측) | **정답(최신)** |
   | shorts-lab-pilot | `C:\Users\PC\OneDrive\Documents\...` (있다면) | (실측) | (실측) | 리다이렉트로 생긴 흔적 추정 |

   "이게 정답 위치다 / 이건 이래서 생긴 옛 흔적으로 보인다"를 사람이 바로
   판단할 수 있게 근거(수정일·크기)를 같이 적는다.

5. **여기서 멈춘다.** 파일 이동·삭제는 하지 않는다. 결과를 사장님께 보고.

## Acceptance Criteria

- [ ] 실제 로컬 계정 수 확인됨
- [ ] "문서" 폴더의 실제 위치(OneDrive 리다이렉트 여부) 확인됨
- [ ] 알려진 프로젝트 폴더가 이 컴퓨터에 몇 군데 있는지, 각각 최종 수정일·
      크기까지 표로 정리됨
- [ ] **파일 이동·삭제 0건**
- [ ] 사장님이 읽고 바로 판단할 수 있는 요약 제시

## 완료 후 다음

Phase 2(실제 통합·정리)는 이 결과를 사장님이 보고 승인한 뒤, 그 내용을
반영한 별도 브리프로 진행한다. PC에서 Phase 1을 마쳤으면 노트북에서도
같은 브리프로 따로 한 번 더 실행한다 — 두 기기 결과가 같다는 보장이 없다.
