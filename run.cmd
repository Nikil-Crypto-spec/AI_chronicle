@echo off
REM One-shot runner for the weekly newsletter generator.
REM
REM Usage:
REM   run.cmd                       dry-run, opens the resulting HTML
REM   run.cmd --no-open             dry-run, don't auto-open
REM   run.cmd --live                actually send email
REM   run.cmd --since 14 --max-items 20   any extra args go straight to run.py
REM
REM CMD batch files are NOT subject to PowerShell execution policy, so this
REM works on locked-down corporate machines.

setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [run.cmd] Python venv not found at %PYTHON%
    echo Create it first:
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install -e .
    exit /b 1
)

set "DRY_RUN=--dry-run"
set "OPEN_HTML=1"
set "PASSTHROUGH="

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--live" (
    set "DRY_RUN="
    shift
    goto parse_args
)
if /i "%~1"=="--no-open" (
    set "OPEN_HTML=0"
    shift
    goto parse_args
)
set "PASSTHROUGH=!PASSTHROUGH! %~1"
shift
goto parse_args
:args_done

echo.
echo ==^> "%PYTHON%" run.py %DRY_RUN%%PASSTHROUGH%
echo.

"%PYTHON%" run.py %DRY_RUN%%PASSTHROUGH%
set "EXITCODE=%ERRORLEVEL%"

if not "%DRY_RUN%"=="" (
    if "%OPEN_HTML%"=="1" (
        REM Find newest newsletter-*.html in out\ and open it.
        set "LATEST="
        for /f "delims=" %%F in ('dir /b /a-d /o-d "out\newsletter-*.html" 2^>nul') do (
            if not defined LATEST set "LATEST=%%F"
        )
        if defined LATEST (
            echo.
            echo Latest newsletter: %CD%\out\!LATEST!
            start "" "%CD%\out\!LATEST!"
        ) else (
            echo.
            echo [run.cmd] No newsletter HTML found in out\
        )
    )
) else (
    echo.
    echo Live run finished. Email dispatched ^(check logs\run.log if unsure^).
)

exit /b %EXITCODE%
