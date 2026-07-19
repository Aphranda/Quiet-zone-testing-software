@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_catr_loss_calibrator.ps1" %*
exit /b %ERRORLEVEL%
