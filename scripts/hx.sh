#!/usr/bin/env bash
# hx.sh - 탐이 신PC(헤르메스 PC)를 SSH로 부르는 유일한 통로.
# 왜 이 래퍼인가: 신PC는 4090과 각종 키가 있는 장비다. `ssh 호스트 아무명령`을 열어 두면
# 세미콜론 한 개로 임의 명령이 되므로, 허용한 동작(업무지시·읽기)만 여기서 통과시킨다.
# 사장님 결정(2026-09-20): 업무지시·읽기는 자유, 스크립트 수정(put)은 백업·문법검사 조건으로 허용.
# 그 밖의 수정·삭제·쓰기와 보안·되돌릴 수 없는 일은 사장님 컨펌.
# 호스트 정보는 이 저장소(공개)에 두지 않는다: ~/.ssh/config 의 별칭 `shinpc`를 쓴다.
#
# 사용:
#   hx.sh cron                 헤르메스 크론 목록
#   hx.sh ls  <경로>           폴더 목록 (허용 경로만)
#   hx.sh read <경로> [줄수]   파일 앞부분 읽기 (허용 경로만, 기본 200줄)
#   hx.sh kick                 우편함 배달원을 지금 실행(우편을 폰/그룹으로 즉시 전달)
#   hx.sh ask                  표준입력의 업무지시를 헤르메스에게 넘기고 답을 받는다
#   hx.sh put <scripts\이름.py>  표준입력의 새 스크립트로 교체(백업+문법검사)
set -euo pipefail

HOST=shinpc
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=8 -o ServerAliveInterval=30 -o ServerAliveCountMax=10 "$HOST")

ps_run() { printf '%s\n' "$1" | "${SSH[@]}" powershell -NoProfile -NonInteractive -Command - ; }
UTF8='[Console]::OutputEncoding=[Text.Encoding]::UTF8;'

# 읽기 허용 경로: solar-bible 저장소, 헤르메스 scripts/logs/cron 폴더.
# 비밀 파일(.env, 키, 토큰 등)과 상위 이동(..)은 거부한다.
check_path() {
  local p="$1"
  [[ "$p" =~ ^C:\\ ]] || { echo "거부: 절대경로(C:\\...)만 허용" >&2; exit 3; }
  [[ "$p" == *".."* ]] && { echo "거부: .. 포함" >&2; exit 3; }
  [[ "$p" =~ [\'\"\`\$\;\&\|\<\>\*\?\(\)] ]] && { echo "거부: 특수문자 포함" >&2; exit 3; }
  shopt -s nocasematch
  if [[ "$p" =~ (\.env|\.key|\.pem|id_ed25519|id_rsa|credential|secret|token|password|config\.yaml) ]]; then
    echo "거부: 비밀 파일 가능성이 있는 이름" >&2; exit 3
  fi
  shopt -u nocasematch
  if [[ "$p" =~ ^C:\\work\\solar-bible(\\|$) ]] \
     || [[ "$p" =~ ^C:\\Users\\PC\\AppData\\Local\\hermes\\(scripts|logs|cron)(\\|$) ]] \
     || [[ "$p" == 'C:\Users\PC\AppData\Local\hermes\mailbox_courier_state.json' ]]; then
    return 0
  fi
  echo "거부: 허용 경로 밖 ($p)" >&2; exit 3
}

cmd="${1:-}"; shift || true
case "$cmd" in
  cron)
    ps_run "${UTF8} hermes cron list" ;;
  ls)
    [ $# -ge 1 ] || { echo "사용: hx.sh ls <경로>" >&2; exit 2; }
    check_path "$1"
    ps_run "${UTF8} Get-ChildItem -LiteralPath '$1' | Select-Object Mode,LastWriteTime,Length,Name | Format-Table -AutoSize | Out-String -Width 200" ;;
  read)
    [ $# -ge 1 ] || { echo "사용: hx.sh read <경로> [줄수]" >&2; exit 2; }
    check_path "$1"
    n="${2:-200}"; [[ "$n" =~ ^[0-9]+$ ]] || { echo "줄수는 숫자" >&2; exit 2; }
    ps_run "${UTF8} Get-Content -LiteralPath '$1' -Encoding UTF8 -TotalCount $n" ;;
  kick)
    # 우편함 배달원을 지금 한 번 실행한다(폴링을 기다리지 않는 즉시 배달). 인자 없는 고정 명령이라 안전하다.
    # 배달원은 상태 파일로 중복 발송을 막으므로 크론과 겹쳐 실행돼도 같은 우편을 두 번 보내지 않는다.
    ps_run "${UTF8} python 'C:\Users\PC\AppData\Local\hermes\scripts\mailbox_courier.py'" ;;
  ask)
    # 업무지시는 따옴표 문제를 피하려고 base64로 실어 보내고, 신PC 임시 폴더에 파일로 내려 --query-file로 읽힌다.
    b64=$(base64 -w0)
    [ -n "$b64" ] || { echo "표준입력이 비었음" >&2; exit 2; }
    ps_run "${UTF8} \$t=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('$b64')); \$f=Join-Path \$env:TEMP ('hx_'+[guid]::NewGuid().ToString('N')+'.txt'); [IO.File]::WriteAllText(\$f,\$t,(New-Object Text.UTF8Encoding \$false)); try { hermes chat --query-file \$f --oneshot -Q } finally { Remove-Item -LiteralPath \$f -ErrorAction SilentlyContinue }" ;;
  put)
    [ "${HX_MODE:-}" = lite ] && { echo "거부: lite 모드(hx_lite.sh)에서는 put(스크립트 교체)을 쓸 수 없음" >&2; exit 3; }
    # 스크립트 배포(사장님 허용 2026-09-20: 보안·되돌릴 수 없는 것 외의 스크립트 수정).
    # 안전장치: 대상은 헤르메스 scripts 폴더의 .py 한 개, 200KB 이하, 문법 검사를 통과해야만 교체,
    # 교체 전 자동 백업(<이름>.py.bak_<시각>). 그 밖의 쓰기는 이 래퍼로 못 한다.
    [ $# -ge 1 ] || { echo "사용: hx.sh put <C:\\Users\\PC\\AppData\\Local\\hermes\\scripts\\이름.py> < 새 파일" >&2; exit 2; }
    dst="$1"
    [[ "$dst" =~ ^C:\\Users\\PC\\AppData\\Local\\hermes\\scripts\\[A-Za-z0-9_]+\.py$ ]] \
      || { echo "거부: 대상은 헤르메스 scripts 폴더의 .py 파일(영문·숫자·_)만 가능" >&2; exit 3; }
    b64=$(base64 -w0)
    [ -n "$b64" ] || { echo "표준입력이 비었음" >&2; exit 2; }
    ps_run "\$ErrorActionPreference='Stop'; ${UTF8} \$dst='$dst'; \$bytes=[Convert]::FromBase64String('$b64'); if (\$bytes.Length -gt 204800) { Write-Output 'REFUSED: over 200KB'; exit 1 }; \$tmp=Join-Path \$env:TEMP ('put_'+[guid]::NewGuid().ToString('N')+'.py'); [IO.File]::WriteAllBytes(\$tmp,\$bytes); python -m py_compile \$tmp; if (\$LASTEXITCODE -ne 0) { Remove-Item -LiteralPath \$tmp -ErrorAction SilentlyContinue; Write-Output 'REFUSED: syntax check failed, not replaced'; exit 1 }; \$bak=''; if (Test-Path -LiteralPath \$dst) { \$bak=\$dst+'.bak_'+(Get-Date -Format yyyyMMdd_HHmmss); Copy-Item -LiteralPath \$dst \$bak }; Move-Item -LiteralPath \$tmp \$dst -Force; Write-Output ('REPLACED: '+\$dst+' ('+\$bytes.Length+' bytes) backup: '+\$bak)" ;;
  *)
    echo "사용: hx.sh {cron | kick | ls <경로> | read <경로> [줄수] | ask < 업무지시 | put <scripts\\이름.py> < 새 파일}" >&2; exit 2 ;;
esac
