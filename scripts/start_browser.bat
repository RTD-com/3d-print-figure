@echo off
REM 启动一个带 CDP 调试端口的本机 Edge，供 3d-print-figure 流程连接。
REM 受限沙箱下由用户双击本文件运行（浏览器会在沙箱外启动）；之后登录一次即可。
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_browser.ps1" %*
echo.
pause
