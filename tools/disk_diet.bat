@echo off
chcp 65001 >nul
title 목회자 전용 C드라이브 다이어트 도구 실행기
echo ========================================================
echo   ⛪ 목회자 전용 윈도우 C드라이브 다이어트 도구 실행 중...
echo   (관리자 권한 요청 창이 뜨면 '예'를 눌러주세요)
echo ========================================================

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& {Start-Process powershell.exe -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"\"%~dp0disk_diet.ps1\"\"' -Verb RunAs}"
