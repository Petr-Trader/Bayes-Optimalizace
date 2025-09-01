\
    @echo off
    setlocal ENABLEDELAYEDEXPANSION

    REM Usage: run_opt.cmd SYMBOL TF [OBJ]
    REM Requires env vars:
    REM   MT5_TERMS  -> path to terminal64.exe
    REM   REPO       -> repo root (e.g., C:\CLON_Git\Bayes-Optimalizace)
    REM   SPACE      -> path to bayes\space\carrymomentum_space.json
    REM   SETS       -> path to sets\baseline

    if "%~1"=="" (
      echo Usage: %~n0 SYMBOL TF [OBJ]
      echo Example: %~n0 AUDJPY D1 mar
      exit /b 1
    )
    if "%~2"=="" (
      echo Usage: %~n0 SYMBOL TF [OBJ]
      exit /b 1
    )

    if "%~3"=="" ( set OBJ=mar ) else ( set OBJ=%~3 )

    if "%MT5_TERMS%"==""  ( echo ^[ERR^] MT5_TERMS not set & exit /b 2 )
    if "%REPO%"==""       ( echo ^[ERR^] REPO not set & exit /b 2 )
    if "%SPACE%"==""      ( echo ^[ERR^] SPACE not set & exit /b 2 )
    if "%SETS%"==""       ( echo ^[ERR^] SETS not set & exit /b 2 )

    set SETFILE=%SETS%\CarryMomentum_%~1_%~2.set
    if not exist "%SETFILE%" (
      echo ^[WARN^] Baseline set file not found: "%SETFILE%"
      echo Creating a placeholder...
      echo ; TODO: fill baseline params for %~1 %~2> "%SETFILE%"
    )

    echo.
    echo === Running Bayes optimization ===
    echo SYMBOL=%~1  TF=%~2  OBJ=%OBJ%
    echo MT5_TERMS=%MT5_TERMS%
    echo SPACE=%SPACE%
    echo SET =%SETFILE%
    echo.

    pushd "%REPO%"
    where python
    if errorlevel 1 (
      echo ^[ERR^] Python not found in PATH
      popd
      exit /b 3
    )

    python bayes_optimize_parallel_v4_1.py ^
      --terms "%MT5_TERMS%" ^
      --space "%SPACE%" ^
      --set   "%SETFILE%" ^
      --init_points 10 --iters 90 --min_trades 60 --obj %OBJ%

    set RC=%ERRORLEVEL%
    popd
    echo.
    echo ExitCode=%RC%
    exit /b %RC%
