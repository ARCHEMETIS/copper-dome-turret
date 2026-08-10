@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title Copper Dome - 4  AUTO LOCK
color 0A

rem หา root ของโปรเจคให้เจอ ไม่ว่าไฟล์นี้จะถูกวางไว้ที่ไหน (โปรเจค / launch / Desktop)
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" cd /d "%~dp0.."
if not exist "venv\Scripts\python.exe" cd /d "C:\Users\Pc\Desktop\Project III"
if not exist "venv\Scripts\python.exe" (
  color 0C
  echo [ERROR] หา venv ไม่เจอ - แก้ path ในบรรทัด cd /d ของไฟล์ .bat นี้
  pause >nul
  exit /b 1
)

rem แบนเนอร์นี้ขึ้นทันทีที่ดับเบิลคลิก (ก่อน python เริ่มด้วยซ้ำ) — คนกดจะได้รู้ว่า
rem เครื่องรับคำสั่งแล้ว ระหว่างรอ ~1-2 วิ ก่อนจอบูตของโปรแกรมจะขึ้นมาแทน
cls
echo.
echo   ################################################################
echo   #                                                              #
echo   #        C O P P E R   D O M E   ..   FIRE CONTROL             #
echo   #        ARIS PROJECT III   ..   AUTO LOCK ENGAGEMENT          #
echo   #                                                              #
echo   ################################################################
echo.
echo   [BOOT] starting python runtime ...
echo   [BOOT] จอบูตจะขึ้นในอีกไม่กี่วินาที - ห้ามปิดหน้าต่างนี้
echo.

rem จากบรรทัดนี้ไป จอบูต (src/bootscreen.py) เป็นตัวรายงานความคืบหน้าแทน console
venv\Scripts\python.exe src\main_click.py

echo.
echo ==========================================================
echo   จบการทำงาน - กดปุ่มอะไรก็ได้เพื่อปิดหน้าต่าง
echo ==========================================================
pause >nul
