# watch_done.ps1: 폴더를 읽기 전용으로 지켜보다가 이름 조건에 맞는 파일이 도착(생성·이름 바꾸기·변경)하는 순간 종료한다.
# 세션이 폴링(반복 확인) 대신 백그라운드로 실행해 두면, 이 스크립트가 끝날 때 오는 종료 알림으로 세션이 깨어난다.
# 실측(2026-09-20, 신PC): 파일 저장부터 감지 12밀리초, 감지부터 세션이 깨어나 첫 명령을 실행하기까지 6~11초.
#
# 사용 예(백그라운드로 실행할 것):
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\watch_done.ps1 `
#       -dir C:\work\solar-bible\tasks\done -match 지시서이름의일부 -timeoutSec 600
# 출력: WATCHING(시작), FIRST_SEEN, ARRIVED 이름과 시각(UTC 에포크 밀리초). 시간 초과면 TIMEOUT과 종료 코드 1.
#
# 주의: FileSystemWatcher.WaitForChanged를 반복 호출하는 방식은 호출 사이의 이벤트(임시 파일이 곧바로 최종 이름으로 바뀌는 순간)를
# 놓쳐서 두 번 실패했다. 그래서 이벤트를 쌓아 두는 Register-ObjectEvent 방식을 쓴다.
# 헤르메스 지시서의 완료 표시(## RESULT)는 일정하지 않으므로, 완료 신호는 "tasks/done 도착"으로 본다.
param([string]$dir, [string]$match, [int]$timeoutSec = 600)
$fsw = New-Object IO.FileSystemWatcher $dir, "*.md"
$fsw.EnableRaisingEvents = $true
Register-ObjectEvent $fsw Created -SourceIdentifier ev_c | Out-Null
Register-ObjectEvent $fsw Changed -SourceIdentifier ev_ch | Out-Null
Register-ObjectEvent $fsw Renamed -SourceIdentifier ev_r | Out-Null
$t_start = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
"WATCHING $dir match=$match started=$t_start"
$first = 0
$end = (Get-Date).AddSeconds($timeoutSec)
while ((Get-Date) -lt $end) {
  $e = Wait-Event -Timeout 5
  if (-not $e) { continue }
  foreach ($x in @($e)) {
    $t1 = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $name = $x.SourceEventArgs.Name
    $type = $x.SourceEventArgs.ChangeType
    Remove-Event -EventIdentifier $x.EventIdentifier
    if ($name -like "*$match*") {
      if ($first -eq 0) { $first = $t1; "FIRST_SEEN $name type=$type t=$t1" }
      "ARRIVED $name type=$type t=$t1"
      exit 0
    }
  }
}
"TIMEOUT"; exit 1
