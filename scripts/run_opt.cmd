
@echo off
setlocal ENABLEDELAYEDEXPANSION
REM Usage: run_opt.cmd SYMBOL TF [OBJ] [TOTAL_RUNS]
if "%~1"=="" ( echo Usage: %~n0 SYMBOL TF [OBJ] [TOTAL_RUNS] & exit /b 1 )
if "%~2"=="" ( echo Usage: %~n0 SYMBOL TF [OBJ] [TOTAL_RUNS] & exit /b 1 )
if "%~3"=="" ( set OBJ=mar ) else ( set OBJ=%~3 )
if "%~4"=="" ( set TOTAL_RUNS=5 ) else ( set TOTAL_RUNS=%~4 )

if "%MT5_TERMS%"==""  ( echo [ERR] MT5_TERMS not set & exit /b 2 )
if "%REPO%"==""       ( echo [ERR] REPO not set & exit /b 2 )
if "%SPACE%"==""      ( echo [ERR] SPACE not set & exit /b 2 )
if "%SETS%"==""       ( echo [ERR] SETS not set & exit /b 2 )

set SET_PREFIX=FX_CarryMomentum
set SETFILE=%SETS%\%SET_PREFIX%_%~1_%~2.set
if not exist "%SETFILE%" (
  set SET_PREFIX=CarryMomentum
  set SETFILE=%SETS%\%SET_PREFIX%_%~1_%~2.set
)
if not exist "%SETFILE%" (
  echo [WARN] Baseline set file not found: "%SETFILE%"
  > "%SETFILE%" echo ; TODO baseline params for %~1 %~2
)

set INIT=1
set /a ITERS=%TOTAL_RUNS% - %INIT%
if %ITERS% LSS 0 set ITERS=0

set TERMS_ARGS= --terms %MT5_TERMS%


echo === Running Bayes optimization ===
echo SYMBOL=%~1  TF=%~2  OBJ=%OBJ%
echo MT5_TERMS=%MT5_TERMS%
echo SPACE=%SPACE%
echo SET =%SETFILE%
echo TERMS_ARGS: !TERMS_ARGS!

pushd "%REPO%"
python bayes_optimize_parallel_v5_0.py ^
  !TERMS_ARGS! ^
  --space "%SPACE%" ^
  --set   "%SETFILE%" ^
  --expert FX_CarryMomentum.ex5 ^
  --init_points %INIT% --iters %ITERS% --min_trades 5 --obj %OBJ%
set RC=%ERRORLEVEL%
popd
echo ExitCode=%RC%
exit /b %RC%
