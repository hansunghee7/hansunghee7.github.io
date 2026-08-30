---
name: deploy-incident
description: 배포 사고 대응 매뉴얼. 라이브 사이트(simplifier.co.kr)가 죽었거나, build-check.yml 또는 site-health-check.yml 워크플로가 Actions 탭에서 빨간 X로 실패했거나, 사장님이 사이트가 이상하다고 알릴 때 반드시 사용. 원인 커밋 찾기, revert 복구 절차, 브랜드 자산 격리 원칙 포함.
---

# 배포 사고 대응 매뉴얼

이 저장소는 `main`에 push되면 GitHub Pages가 자동으로 빌드·배포합니다(별도
승인 단계 없음). 두 가지 자동 안전장치가 있습니다:

- `.github/workflows/build-check.yml` — push마다 GitHub Pages와 같은 gem
  구성(`Gemfile`)으로 미리 빌드해봅니다. 여기서 실패하면 **실제 라이브
  사이트도 그 커밋부터 빌드가 막혔을 가능성이 높습니다.**
- `.github/workflows/site-health-check.yml` — 10분마다 라이브 사이트
  홈페이지 응답과 핵심 브랜드 자산(로고 등)이 실제로 뜨는지 확인합니다.

**둘 중 하나가 Actions 탭에서 빨간 X로 뜨면(또는 사장님이 사이트가 이상하다고
알려주면) 이렇게 대응하세요:**

1. `curl -sL -o /dev/null -w '%{http_code}\n' https://simplifier.co.kr/` 로
   실제로 죽었는지 먼저 확인 (캐시일 수도 있으니 `-H 'Cache-Control: no-cache'` 추가 고려).
2. `git log --oneline -10`으로 최근 커밋을 보고, **`build-check.yml`이
   마지막으로 성공했던 커밋**을 찾습니다 (Actions 탭에서 초록 체크 확인).
3. 그 이후 커밋 중 의심되는 것을 `git revert <커밋 해시> --no-edit`로
   되돌리고 push합니다. 여러 개면 뒤에서부터 하나씩 되돌리며 재확인.
4. `git revert` 대신 파일을 직접 고칠 수 있으면(원인이 명확하면) 고쳐서
   push해도 됩니다 — 다만 `build-check.yml`이 다시 초록이 되는 것까지
   확인하고 끝내세요.
5. 브랜드 자산(로고·캐릭터 이미지 등 여러 페이지가 같이 쓰는 파일)을 정리·삭제할
   때는 **완전 삭제 대신 격리(quarantine, 별도 폴더로 이동)를 기본값으로
   씁니다** — 오탐이어도 `git mv` 한 줄로 바로 복구할 수 있습니다. 정리
   작업의 마지막 단계로 대표 페이지(홈 등)를 실제로 열어 육안 확인하거나
   `site-health-check.yml`을 수동 실행(workflow_dispatch)해서 확인하세요.
