@echo off
REM Windows Batch 스크립트로 파이프라인 실행

echo ============================================================
echo Multi-Agent QA Pipeline 실행
echo ============================================================
echo.

REM API 키 확인
if "%ANTHROPIC_API_KEY%"=="" (
    echo [오류] ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.
    echo.
    echo 설정 방법:
    echo   set ANTHROPIC_API_KEY=sk-ant-your-api-key-here
    echo   또는
    echo   PowerShell: $env:ANTHROPIC_API_KEY = "sk-ant-your-api-key-here"
    echo.
    pause
    exit /b 1
)

echo [확인] API 키가 설정되어 있습니다.
echo.

REM 패키지 확인
echo [확인] 필요한 패키지 설치 확인 중...
python -c "import anthropic; import pytest" 2>nul
if errorlevel 1 (
    echo [설치] anthropic 및 pytest 설치 중...
    pip install anthropic pytest
)

echo.
echo [실행] 파이프라인 시작...
echo.

REM 파이프라인 실행
python pipeline.py

echo.
echo ============================================================
echo 파이프라인 완료
echo ============================================================
echo.
echo 생성된 파일:
dir /b architecture.md task_queue.json pipeline-state.json review-results.json 2>nul
dir /b src\calculator.py tests\test_calculator.py 2>nul

pause
