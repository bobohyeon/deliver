# 책임: Tasqra의 현재 로고 크기와 무관하게 메인 44px·사이드바 34px로 맞춘다.
# 관계: dashboard-deliverable-polish.patch를 이미 일부 또는 전부 적용한 로컬 팀 저장소에 후속 교정만 적용한다.
# Spring 비교: 기존 엔티티 상태를 읽고 목표 상태로 멱등 갱신한 뒤 다시 조회해 검증하는 보정 작업이다.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoPath
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath $RepoPath).Path
$landingPath = Join-Path $repo 'frontend\src\styles\landing.css'
$sidebarPath = Join-Path $repo 'frontend\src\features\projects\ProjectSidebar.jsx'

if (-not (Test-Path -LiteralPath $landingPath)) {
    throw "파일을 찾을 수 없습니다: $landingPath"
}
if (-not (Test-Path -LiteralPath $sidebarPath)) {
    throw "파일을 찾을 수 없습니다: $sidebarPath"
}

Push-Location $repo
try {
    $branch = (git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or $branch -ne 'fix/dashboard-deliverable-polish') {
        throw "Tasqra 브랜치를 확인하세요. 현재 브랜치: $branch"
    }

    $landing = [System.IO.File]::ReadAllText($landingPath)
    $sidebar = [System.IO.File]::ReadAllText($sidebarPath)

    $landingPattern = '\.landing \.app-header__brand \.logo-mark\{width:\d+px;height:\d+px\}'
    $sidebarPattern = '<BrandMark className="project-sidebar__logo" size=\{\d+\}/>'
    $landingMatches = [regex]::Matches($landing, $landingPattern)
    $sidebarMatches = [regex]::Matches($sidebar, $sidebarPattern)

    if ($landingMatches.Count -ne 1) {
        throw "랜딩 로고 크기 규칙을 정확히 한 곳 찾지 못했습니다. 발견: $($landingMatches.Count)"
    }
    if ($sidebarMatches.Count -ne 1) {
        throw "사이드바 로고 태그를 정확히 한 곳 찾지 못했습니다. 발견: $($sidebarMatches.Count)"
    }

    $landingBefore = $landingMatches[0].Value
    $sidebarBefore = $sidebarMatches[0].Value
    $landingTarget = '.landing .app-header__brand .logo-mark{width:44px;height:44px}'
    $sidebarTarget = '<BrandMark className="project-sidebar__logo" size={34}/>'

    $landingUpdated = $landing.Replace($landingBefore, $landingTarget)
    $sidebarUpdated = $sidebar.Replace($sidebarBefore, $sidebarTarget)
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)

    [System.IO.File]::WriteAllText($landingPath, $landingUpdated, $utf8NoBom)
    [System.IO.File]::WriteAllText($sidebarPath, $sidebarUpdated, $utf8NoBom)

    # 성공 메시지 전에 디스크에서 다시 읽어 실제 저장 결과를 검증한다.
    $landingSaved = [System.IO.File]::ReadAllText($landingPath)
    $sidebarSaved = [System.IO.File]::ReadAllText($sidebarPath)
    if ([regex]::Matches($landingSaved, [regex]::Escape($landingTarget)).Count -ne 1) {
        throw '저장 후 검증 실패: 메인 로고가 44px이 아닙니다.'
    }
    if ([regex]::Matches($sidebarSaved, [regex]::Escape($sidebarTarget)).Count -ne 1) {
        throw '저장 후 검증 실패: 사이드바 로고가 34px이 아닙니다.'
    }

    git diff --check
    if ($LASTEXITCODE -ne 0) {
        throw 'git diff --check에 실패했습니다.'
    }

    Write-Host "메인 로고: $landingBefore -> $landingTarget"
    Write-Host "사이드바 로고: $sidebarBefore -> $sidebarTarget"
    Write-Host '저장 후 재검증 완료: 메인 44px / 사이드바 34px'
    git status --short
}
finally {
    Pop-Location
}
