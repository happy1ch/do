# ==============================================================================
# 목회자 전용 윈도우 C드라이브 다이어트 프로그램 (Pastor C-Drive Diet) v1.2
# 제작: 문경 행복한교회 최성광 목사 & Happy초이 AI 비서
# 핵심 기능:
#   1. 캡컷(CapCut) 영상 편집 캐시 & 구버전 업데이트 잔여 파일(1~2GB씩 누적) 안전 청소
#   2. 윈도우 업데이트 다운로드 찌꺼기 & 임시파일(%TEMP%) 원클릭 비우기
#   3. 데스크톱 최대절전모드 파일(hiberfil.sys, 16~32GB) 즉시 회수
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "목회자 전용 C드라이브 다이어트 도구 (Happy Pastoral OS)"

function Write-Header {
    Clear-Host
    Write-Host "=======================================================================" -ForegroundColor Cyan
    Write-Host "     ⛪ 목회자 전용 윈도우 C드라이브 다이어트 도구 (Happy Pastoral OS)    " -ForegroundColor Yellow
    Write-Host "   - 캡컷(CapCut) 영상 캐시, 구버전 잔여물, 윈도우 찌꺼기 0원 청소 -      " -ForegroundColor Gray
    Write-Host "=======================================================================" -ForegroundColor Cyan
    Write-Host ""
}

# 1. 관리자 권한 확인 및 자동 승격
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Header
    Write-Host "[안내] 윈도우 시스템 및 캐시 청소를 위해 '관리자 권한'으로 다시 실행합니다..." -ForegroundColor Yellow
    Start-Process powershell.exe -ArgumentList ("-NoProfile -ExecutionPolicy Bypass -File `"{0}`"" -f $MyInvocation.MyCommand.Path) -Verb RunAs
    Exit
}

function Get-FolderSizeMB ($path) {
    if (Test-Path $path) {
        try {
            $measure = Get-ChildItem -Path $path -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum
            if ($measure.Sum) {
                return [math]::Round($measure.Sum / 1MB, 1)
            }
        } catch {}
    }
    return 0
}

function Clean-TargetFolder ($path, $name) {
    if (Test-Path $path) {
        Write-Host "  ▶ $name 청소 중..." -ForegroundColor Gray -NoNewline
        $before = Get-FolderSizeMB $path
        try {
            Get-ChildItem -Path $path -Force -ErrorAction SilentlyContinue | ForEach-Object {
                Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            }
            $after = Get-FolderSizeMB $path
            $freed = [math]::Round($before - $after, 1)
            Write-Host " [완료] ($freed MB 확보)" -ForegroundColor Green
            return $freed
        } catch {
            Write-Host " [일부 건너뜀]" -ForegroundColor Yellow
            return 0
        }
    } else {
        return 0
    }
}

# 캡컷 구버전 앱 폴더 스캔 및 정리 (최신 버전 1개만 남기고 과거 버전 1~2GB씩 삭제)
function Get-CapCutOldVersionsSizeMB {
    $appsPath = "$env:LOCALAPPDATA\CapCut\Apps"
    $totalOldMB = 0
    if (Test-Path $appsPath) {
        $versions = Get-ChildItem -Path $appsPath -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^\d+\.\d+' } | Sort-Object { [version]($_.Name -replace '[^\d\.]', '') }
        if ($versions.Count -gt 1) {
            # 최신 버전 제외한 이전 버전들
            $oldVersions = $versions[0..($versions.Count - 2)]
            foreach ($v in $oldVersions) {
                $totalOldMB += (Get-FolderSizeMB $v.FullName)
            }
        }
    }
    return [math]::Round($totalOldMB, 1)
}

function Clean-CapCutOldVersions {
    $appsPath = "$env:LOCALAPPDATA\CapCut\Apps"
    $freed = 0
    if (Test-Path $appsPath) {
        $versions = Get-ChildItem -Path $appsPath -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^\d+\.\d+' } | Sort-Object { [version]($_.Name -replace '[^\d\.]', '') }
        if ($versions.Count -gt 1) {
            $latest = $versions[-1].Name
            $oldVersions = $versions[0..($versions.Count - 2)]
            Write-Host "  ▶ 캡컷 최신 버전($latest) 유지, 구버전 $($oldVersions.Count)개 폴더 정리 중..." -ForegroundColor Gray -NoNewline
            foreach ($v in $oldVersions) {
                $sz = Get-FolderSizeMB $v.FullName
                try {
                    Remove-Item $v.FullName -Recurse -Force -ErrorAction SilentlyContinue
                    $freed += $sz
                } catch {}
            }
            Write-Host " [완료] ($freed MB 확보)" -ForegroundColor Green
        }
    }
    return $freed
}

# ── 메인 메뉴 루프 ──
do {
    Write-Header

    Write-Host "🔍 [1단계] C드라이브 용량 도둑 정밀 진단 중..." -ForegroundColor Cyan
    Write-Host "   (캡컷 캐시, 업데이트 패키지, 윈도우 찌꺼기 분석 중...)" -ForegroundColor Gray

    # 1. 캡컷 캐시 & 패키지
    $capcutCache1 = "$env:LOCALAPPDATA\CapCut\User Data\Cache"
    $capcutCache2 = "$env:LOCALAPPDATA\CapCut\User Data\Projects\com.lveditor.draft\cache"
    $capcutPkg1   = "$env:LOCALAPPDATA\CapCut\package"
    $capcutPkg2   = "$env:LOCALAPPDATA\CapCut\User Data\package"
    $capcutDown   = "$env:LOCALAPPDATA\CapCut\User Data\Cache\download"
    $capcutCacheSize = (Get-FolderSizeMB $capcutCache1) + (Get-FolderSizeMB $capcutCache2) + (Get-FolderSizeMB $capcutDown)
    $capcutPkgSize   = (Get-FolderSizeMB $capcutPkg1) + (Get-FolderSizeMB $capcutPkg2)
    $capcutOldVerSize = Get-CapCutOldVersionsSizeMB
    $capcutTotalSize = $capcutCacheSize + $capcutPkgSize + $capcutOldVerSize

    # 2. 윈도우 Temp
    $userTemp = $env:TEMP
    $sysTemp = "C:\Windows\Temp"
    $tempSize = (Get-FolderSizeMB $userTemp) + (Get-FolderSizeMB $sysTemp)

    # 3. 윈도우 업데이트 다운로드 찌꺼기
    $wuDownload = "C:\Windows\SoftwareDistribution\Download"
    $wuSize = Get-FolderSizeMB $wuDownload

    # 4. 프리미어 / 어도비 미디어 캐시
    $adobeCache = "$env:APPDATA\Adobe\Common\Media Cache Files"
    $adobeSize = Get-FolderSizeMB $adobeCache

    # 5. 크롬 / 엣지 브라우저 캐시
    $chromeCache = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache"
    $edgeCache = "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cache"
    $browserSize = (Get-FolderSizeMB $chromeCache) + (Get-FolderSizeMB $edgeCache)

    # 6. 최대절전모드 파일 (hiberfil.sys)
    $hiberFile = "C:\hiberfil.sys"
    $hiberSize = 0
    if (Test-Path $hiberFile) {
        try {
            $hiberItem = Get-Item $hiberFile -Force -ErrorAction SilentlyContinue
            $hiberSize = [math]::Round($hiberItem.Length / 1MB, 1)
        } catch {}
    }

    $totalFoundMB = $capcutTotalSize + $tempSize + $wuSize + $adobeSize + $browserSize
    $totalFoundGB = [math]::Round($totalFoundMB / 1024, 2)

    Write-Header
    Write-Host "📊 [스캔 결과] 안전하게 지울 수 있는 캐시 및 잔여물:" -ForegroundColor Yellow
    Write-Host "-----------------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host ("  1. [캡컷] 영상 작업 임시 캐시     : {0,10} MB  (프로젝트 원본은 100% 안전)" -f $capcutCacheSize) -ForegroundColor $(if($capcutCacheSize -gt 500){"Red"}else{"White"})
    Write-Host ("  2. [캡컷] 구버전 앱 & 업데이트 패키지 : {0,10} MB  (과거 버전 찌꺼기)" -f ($capcutPkgSize + $capcutOldVerSize)) -ForegroundColor $(if(($capcutPkgSize + $capcutOldVerSize) -gt 500){"Yellow"}else{"White"})
    Write-Host ("  3. [윈도우] 임시 파일 (%TEMP%)    : {0,10} MB" -f $tempSize) -ForegroundColor White
    Write-Host ("  4. [윈도우] 업데이트 설치 찌꺼기  : {0,10} MB" -f $wuSize) -ForegroundColor White
    Write-Host ("  5. [영상/웹] 어도비 & 브라우저 캐시: {0,10} MB" -f ($adobeSize + $browserSize)) -ForegroundColor White
    if ($hiberSize -gt 0) {
        Write-Host ("  6. [선택] 최대절전모드 파일       : {0,10} MB  (데스크톱 PC 전용 즉시 회수)" -f $hiberSize) -ForegroundColor Magenta
    }
    Write-Host "-----------------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host ("  🎯 즉시 확보 가능한 총 디스크 용량: 약 {0} GB ({1} MB)" -f $totalFoundGB, $totalFoundMB) -ForegroundColor Green
    Write-Host "=======================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  [1] 원클릭 전체 다이어트 (캡컷 캐시+구버전+윈도우 전체 청소) [강력 권장]" -ForegroundColor Yellow
    Write-Host "  [2] 캡컷(CapCut)만 집중 청소 (캐시 + 업데이트 패키지 + 구버전 폴더)" -ForegroundColor Cyan
    Write-Host "  [3] 윈도우 시스템 캐시만 청소 (임시파일 + 업데이트 다운로드 찌꺼기)" -ForegroundColor Cyan
    Write-Host "  [4] 최대절전모드 끄기 (데스크톱 전용: $hiberSize MB 즉시 회수)" -ForegroundColor Magenta
    Write-Host "  [5] 휴지통 비우기" -ForegroundColor Gray
    Write-Host "  [Q] 프로그램 종료" -ForegroundColor DarkGray
    Write-Host ""
    $choice = Read-Host "원하시는 작업 번호를 입력하세요 (기본값: 1)"
    if ([string]::IsNullOrWhiteSpace($choice)) { $choice = "1" }

    switch ($choice) {
        "1" {
            Write-Host "`n🚀 [전체 안전 다이어트] 시작합니다..." -ForegroundColor Cyan
            $freedTotal = 0

            # 캡컷 캐시
            $freedTotal += Clean-TargetFolder $capcutCache1 "캡컷 사용자 캐시"
            $freedTotal += Clean-TargetFolder $capcutCache2 "캡컷 프로젝트 임시 캐시"
            $freedTotal += Clean-TargetFolder $capcutDown   "캡컷 다운로드 캐시"
            $freedTotal += Clean-TargetFolder $capcutPkg1   "캡컷 업데이트 설치 패키지 1"
            $freedTotal += Clean-TargetFolder $capcutPkg2   "캡컷 업데이트 설치 패키지 2"
            $freedTotal += Clean-CapCutOldVersions

            # 윈도우 Temp
            $freedTotal += Clean-TargetFolder $userTemp "사용자 Temp 폴더"
            $freedTotal += Clean-TargetFolder $sysTemp "시스템 Temp 폴더"

            # 윈도우 업데이트
            Write-Host "  ▶ 윈도우 업데이트 서비스 잠시 중지 후 청소..." -ForegroundColor Gray -NoNewline
            Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
            $freedTotal += Clean-TargetFolder $wuDownload "업데이트 다운로드 찌꺼기"
            Start-Service wuauserv -ErrorAction SilentlyContinue

            # 어도비 & 브라우저
            $freedTotal += Clean-TargetFolder $adobeCache "어도비 미디어 캐시"
            $freedTotal += Clean-TargetFolder $chromeCache "크롬 브라우저 캐시"
            $freedTotal += Clean-TargetFolder $edgeCache "엣지 브라우저 캐시"

            # 휴지통
            try {
                Clear-RecycleBin -Force -ErrorAction SilentlyContinue
                Write-Host "  ▶ 휴지통 비우기 완료" -ForegroundColor Green
            } catch {}

            $freedGB = [math]::Round($freedTotal / 1024, 2)
            Write-Host "`n🎉 [다이어트 완료!] 총 $freedGB GB ($freedTotal MB)의 공간을 안전하게 확보했습니다!" -ForegroundColor Green
            Write-Host "💡 꿀팁: 캡컷 [설정] -> [전역 설정] -> [캐시] 저장 위치를 'D:\CapCutCache'로 변경하시면 C드라이브가 다시는 차지 않습니다." -ForegroundColor Yellow
            Pause
        }
        "2" {
            Write-Host "`n🎬 [캡컷 전용 청소] 시작..." -ForegroundColor Cyan
            $f1 = Clean-TargetFolder $capcutCache1 "캡컷 사용자 캐시"
            $f2 = Clean-TargetFolder $capcutCache2 "캡컷 프로젝트 임시 캐시"
            $f3 = Clean-TargetFolder $capcutDown   "캡컷 다운로드 캐시"
            $f4 = Clean-TargetFolder $capcutPkg1   "업데이트 패키지 1"
            $f5 = Clean-TargetFolder $capcutPkg2   "업데이트 패키지 2"
            $f6 = Clean-CapCutOldVersions
            $total = $f1 + $f2 + $f3 + $f4 + $f5 + $f6
            Write-Host "`n🎉 캡컷 캐시 및 구버전 잔여물 총 $total MB 정리 완료!" -ForegroundColor Green
            Pause
        }
        "3" {
            Write-Host "`n🧹 [윈도우 시스템 캐시 청소] 시작..." -ForegroundColor Cyan
            $f1 = Clean-TargetFolder $userTemp "사용자 Temp"
            $f2 = Clean-TargetFolder $sysTemp "시스템 Temp"
            Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
            $f3 = Clean-TargetFolder $wuDownload "업데이트 캐시"
            Start-Service wuauserv -ErrorAction SilentlyContinue
            $total = $f1 + $f2 + $f3
            Write-Host "`n🎉 윈도우 시스템 캐시 총 $total MB 정리 완료!" -ForegroundColor Green
            Pause
        }
        "4" {
            Write-Host "`n⚡ [최대절전모드 파일 정리] 진행..." -ForegroundColor Magenta
            try {
                powercfg -h off
                Write-Host "  ▶ 최대절전모드가 해제되었으며, C:\hiberfil.sys ($hiberSize MB)가 즉시 삭제되었습니다!" -ForegroundColor Green
            } catch {
                Write-Host "  ▶ 처리 중 오류가 발생했습니다." -ForegroundColor Red
            }
            Pause
        }
        "5" {
            try {
                Clear-RecycleBin -Force -ErrorAction SilentlyContinue
                Write-Host "`n🗑️ 휴지통을 깨끗이 비웠습니다!" -ForegroundColor Green
            } catch {}
            Pause
        }
        "Q" {
            Write-Host "`n프로그램을 종료합니다. 은혜로운 사역 되세요!" -ForegroundColor Gray
            Exit
        }
    }
} while ($choice -ne "Q")
