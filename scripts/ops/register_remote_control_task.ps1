# 1회 실행용 등록 스크립트. Windows 작업 스케줄러에 "simplifier-remote-control" 작업을
# 만든다 — 이 PC에 로그온할 때마다 remote_control_launch.ps1을 창 없이(숨김) 실행해
# claude remote-control --spawn=same-dir을 백그라운드로 띄운다.
#
# 사용법: PowerShell(관리자 권한 불필요, 현재 사용자 로그온 트리거라 일반 권한으로 충분)에서
#   powershell -ExecutionPolicy Bypass -File scripts\ops\register_remote_control_task.ps1
$ErrorActionPreference = "Stop"

$taskName = "simplifier-remote-control"
$launcher = "C:\work\hansunghee7.github.io\scripts\ops\remote_control_launch.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$launcher`""

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$settings = New-ScheduledTaskSettingsSet -Hidden -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
  -Settings $settings -Description "로그온 시 claude remote-control 백그라운드 자동 실행 (탐 등록, 2026-09-28)" `
  -Force | Out-Null

Write-Host "등록 완료: $taskName (트리거: $env:USERNAME 로그온)"
Write-Host "지금 1회 시험 실행: Start-ScheduledTask -TaskName '$taskName'"
