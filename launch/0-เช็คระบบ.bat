@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title Copper Dome - 0  SYSTEM CHECK

rem หา root ของโปรเจคให้เจอ ไม่ว่าไฟล์นี้จะถูกวางไว้ที่ไหน (โปรเจค / launch / Desktop)
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" cd /d "%~dp0.."
if not exist "venv\Scripts\python.exe" cd /d "C:\Users\Pc\Desktop\Project III"
if not exist "venv\Scripts\python.exe" (
  echo [ERROR] หา venv ไม่เจอ - แก้ path ในบรรทัด cd /d ของไฟล์ .bat นี้
  pause >nul
  exit /b 1
)

echo ==========================================================
echo   0  SYSTEM CHECK
echo   ไม่ต้องต่ออะไรเลย - เช็คว่าโค้ด+โมเดลยังดีอยู่
echo ==========================================================
echo.
venv\Scripts\python.exe tools\smoke_test.py

echo.
echo ==========================================================
echo   จบการทำงาน - กดปุ่มอะไรก็ได้เพื่อปิดหน้าต่าง
echo ==========================================================
pause >nul
