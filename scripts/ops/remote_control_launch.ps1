# PC 부팅(로그온) 시 Claude Code Remote Control을 백그라운드로 띄우는 런처.
# 작업 스케줄러(simplifier-remote-control)가 로그온 트리거로 이 스크립트를 호출한다.
# 등록: scripts/ops/register_remote_control_task.ps1 (1회 실행)
# 2026-09-29 N74 보강: 9/29 로그온 직후 실행이 0xC000013A(강제 종료)로 죽은 뒤 수동 실행은 45초 넘게 생존.
#  → 로그온 직후 준비 지연이 원인이라는 추정으로 ① 시작 전 대기 ② 죽으면 재시도 ③ 60초 생존 여부와 종료 코드를 로그에 남긴다.
#  원인이 다른 것으로 드러나도 launch.log의 종료 코드로 알 수 있게 한다(다음 로그온 때 확인).
$ErrorActionPreference = "Stop"

$repoDir = "C:\work\hansunghee7.github.io"
$claudeExe = "$env:APPDATA\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe"
$heartbeatDir = "C:\work\_ops\remote-control"
$heartbeatFile = Join-Path $heartbeatDir "last-start.txt"
$logFile = Join-Path $heartbeatDir "launch.log"
$startDelaySec = 45     # 로그온 직후 네트워크·세션 준비 대기
$aliveCheckSec = 60     # 이 시간 동안 살아 있으면 정상 기동으로 기록
$maxAttempts = 5
$retryWaitSec = 30

New-Item -ItemType Directory -Force -Path $heartbeatDir | Out-Null
function Log($msg) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg" | Add-Content -Path $logFile -Encoding utf8 }

Get-Date -Format "yyyy-MM-dd HH:mm:ss" | Set-Content -Path $heartbeatFile -Encoding utf8
Set-Location $repoDir
Log "launcher start (delay ${startDelaySec}s)"
Start-Sleep -Seconds $startDelaySec

for ($i = 1; $i -le $maxAttempts; $i++) {
    $p = Start-Process -FilePath $claudeExe -ArgumentList @("remote-control", "--spawn=same-dir") -NoNewWindow -PassThru
    Log "attempt $i pid=$($p.Id)"
    if ($p.WaitForExit($aliveCheckSec * 1000)) {
        Log "attempt $i died within ${aliveCheckSec}s exit=$($p.ExitCode)"
        Start-Sleep -Seconds $retryWaitSec
        continue
    }
    Log "attempt $i alive after ${aliveCheckSec}s"
    $p.WaitForExit()
    Log "attempt $i ended later exit=$($p.ExitCode)"
    Start-Sleep -Seconds $retryWaitSec
}
Log "gave up after $maxAttempts attempts"
