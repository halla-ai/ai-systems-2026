#!/usr/bin/env pwsh
# PowerShell 스크립트로 파이프라인 실행

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Multi-Agent QA Pipeline 실행" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# API 키 확인
if (-not $env:ANTHROPIC_API_KEY) {
    Write-Host "[오류] ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다." -ForegroundColor Red
    Write-Host ""
    Write-Host "설정 방법:" -ForegroundColor Yellow
    Write-Host '  $env:ANTHROPIC_API_KEY = "sk-ant-your-api-key-here"' -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "[확인] API 키가 설정되어 있습니다." -ForegroundColor Green
Write-Host ""

# 패키지 확인
Write-Host "[확인] 필요한 패키지 설치 확인 중..." -ForegroundColor Yellow
try {
    python -c "import anthropic; import pytest" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw
    }
    Write-Host "[확인] 모든 패키지가 설치되어 있습니다." -ForegroundColor Green
} catch {
    Write-Host "[설치] anthropic 및 pytest 설치 중..." -ForegroundColor Yellow
    pip install anthropic pytest
}

Write-Host ""
Write-Host "[실행] 파이프라인 시작..." -ForegroundColor Cyan
Write-Host ""

# 파이프라인 실행
python pipeline.py

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "파이프라인 완료" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 생성된 파일 확인
Write-Host "생성된 파일:" -ForegroundColor Yellow
$files = @(
    "architecture.md",
    "task_queue.json",
    "pipeline-state.json",
    "review-results.json",
    "src/calculator.py",
    "tests/test_calculator.py"
)

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "  ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $file (없음)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "리뷰 결과 확인: review-results.json" -ForegroundColor Cyan
Write-Host "파이프라인 상태: pipeline-state.json" -ForegroundColor Cyan
