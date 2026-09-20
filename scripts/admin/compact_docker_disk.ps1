# compact_docker_disk.ps1: 도커 데스크톱의 가상 디스크 파일(docker_data.vhdx)을 압축해 C 드라이브 여유를 되찾는다.
# 배경(2026-09-20): 도커가 실제로 쓰는 양은 약 11GB인데 디스크 파일은 19.2GB. 이미지를 지워도 파일은 자동으로 작아지지 않는다.
# 필요 권한: 관리자. 실행은 같은 폴더의 compact_docker_disk.cmd를 마우스 오른쪽 버튼 > "관리자 권한으로 실행"으로 한다.
# 영향: 도커, 웹UI(127.0.0.1:3000), n8n이 약 5~10분 멈춘다. 데이터는 지우지 않는다(압축만). 컨테이너는 자동 재시작 정책으로 다시 켜진다.
# 연습 실행: -DryRun 을 주면 아무것도 멈추지 않고 확인만 한다(관리자 권한 불필요).
param([switch]$DryRun)
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"
$vhd = "C:\Users\PC\AppData\Local\Docker\wsl\disk\docker_data.vhdx"

function Get-Gb($p) { [math]::Round((Get-Item $p).Length / 1GB, 2) }
function Get-CFree { $d = Get-PSDrive C; "{0:N0} GB 여유 ({1:P1})" -f ($d.Free/1GB), ($d.Free/($d.Free+$d.Used)) }

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin -and -not $DryRun) { Write-Host "관리자 권한이 아닙니다. .cmd 파일을 마우스 오른쪽 버튼으로 눌러 '관리자 권한으로 실행'을 고르세요." -ForegroundColor Red; exit 1 }
if (-not (Test-Path $vhd)) { Write-Host "디스크 파일을 찾지 못했습니다: $vhd" -ForegroundColor Red; exit 1 }

Write-Host "=== 시작 전 ===" -ForegroundColor Cyan
Write-Host ("도커 디스크 파일: {0} GB / C 드라이브: {1}" -f (Get-Gb $vhd), (Get-CFree))
if ($DryRun) {
    Write-Host "[연습 실행] 아래 순서로 진행할 예정이며, 지금은 아무것도 멈추지 않았습니다." -ForegroundColor Yellow
    "1) docker desktop stop  2) wsl --shutdown  3) diskpart: attach readonly, compact vdisk, detach  4) docker desktop start  5) 웹UI 응답 확인" | Write-Host
    docker desktop status 2>&1 | Select-Object -First 3 | Write-Host
    exit 0
}

Write-Host "`n도커, 웹UI, n8n이 약 5~10분 멈춥니다. 데이터는 지우지 않고 압축만 합니다." -ForegroundColor Yellow
$ans = Read-Host "계속하려면 Enter, 그만두려면 Ctrl+C"

Write-Host "`n[1/5] 도커 데스크톱 정지..."
docker desktop stop 2>&1 | Out-Null
Start-Sleep -Seconds 5
Get-Process -Name "Docker Desktop","com.docker.backend" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "[2/5] WSL 종료..."
wsl --shutdown
Start-Sleep -Seconds 10

Write-Host "[3/5] 디스크 파일 압축(수 분 걸릴 수 있습니다)..."
$dp = Join-Path $env:TEMP "compact_docker.txt"
@("select vdisk file=`"$vhd`"", "attach vdisk readonly", "compact vdisk", "detach vdisk", "exit") | Set-Content -Path $dp -Encoding ASCII
$out = diskpart /s $dp 2>&1
$out | ForEach-Object { Write-Host "  $_" }
Remove-Item $dp -ErrorAction SilentlyContinue

Write-Host "`n=== 압축 후 ===" -ForegroundColor Cyan
Write-Host ("도커 디스크 파일: {0} GB / C 드라이브: {1}" -f (Get-Gb $vhd), (Get-CFree))

Write-Host "`n[4/5] 도커 데스크톱 시작..."
docker desktop start 2>&1 | Out-Null
$ok = $false
for ($i = 0; $i -lt 48; $i++) { Start-Sleep -Seconds 5; docker info 2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) { $ok = $true; break } }
if (-not $ok) { Write-Host "도커가 4분 안에 시작하지 않았습니다. 도커 데스크톱을 직접 열어 주세요." -ForegroundColor Red; Read-Host "Enter로 닫기"; exit 1 }

Write-Host "[5/5] 웹UI와 n8n 확인..."
Start-Sleep -Seconds 20
docker ps --format "  {{.Names}}  {{.Status}}"
try { $r = Invoke-WebRequest "http://127.0.0.1:3000/" -UseBasicParsing -TimeoutSec 10; Write-Host "웹UI: HTTP $($r.StatusCode)" -ForegroundColor Green }
catch { Write-Host "웹UI가 아직 응답하지 않습니다. 1~2분 뒤 http://127.0.0.1:3000 을 열어 보세요." -ForegroundColor Yellow }
Write-Host "`n끝났습니다. 위 결과를 탐에게 알려 주세요." -ForegroundColor Green
Read-Host "Enter로 닫기"
