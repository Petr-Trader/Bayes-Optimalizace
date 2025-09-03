@echo off
REM === Set your environment variables here (edit paths) ===
set REPO=C:\CLON_Git\Bayes-Optimalizace
REM Single terminal (recommended to quote paths with spaces):
REM set MT5_TERMS="C:\MT5_Portable\MT5_testA\terminal64.exe"
REM Multiple terminals (semicolon-separated; each quoted):
REM set MT5_TERMS="C:\MT5_Portable\MT5_testA\terminal64.exe";"C:\MT5_Portable\MT5_testB\terminal64.exe";"C:\MT5_Portable\MT5_testC\terminal64.exe"
set MT5_TERMS="C:\MT5_Portable\MT5_testA\terminal64.exe"

set SPACE=%REPO%\bayes\space\carrymomentum_space_v1_02.json
set SETS=%REPO%\sets\baseline

echo REPO=%REPO%
echo MT5_TERMS=%MT5_TERMS%
echo SPACE=%SPACE%
echo SETS=%SETS%
