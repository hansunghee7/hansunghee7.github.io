# PC 부팅(로그온) 시 Claude Code Remote Control을 백그라운드로 띄우는 런처.
# 작업 스케줄러(simplifier-remote-control)가 로그온 트리거로 이 스크립트를 호출한다.
# 등록: scripts/ops/register_remote_control_task.ps1 (1회 실행)
$ErrorActionPreference = "Stop"

$repoDir = "C:\work\hansunghee7.github.io"
$claudeExe = "$env:APPDATA\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe"
$heartbeatDir = "C:\work\_ops\remote-control"
$heartbeatFile = Join-Path $heartbeatDir "last-start.txt"

New-Item -ItemType Directory -Force -Path $heartbeatDir | Out-Null
Get-Date -Format "yyyy-MM-dd HH:mm:ss" | Set-Content -Path $heartbeatFile -Encoding utf8

Set-Location $repoDir
& $claudeExe remote-control --spawn=same-dir
