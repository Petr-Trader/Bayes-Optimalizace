\
    @echo off
    call "%~dp0env_vars_example.cmd"

    REM === Example batch of optimizations (edit/timeframe/obj as needed) ===
    call "%~dp0run_opt.cmd" AUDJPY D1 mar
    call "%~dp0run_opt.cmd" GBPJPY H4 mar
    call "%~dp0run_opt.cmd" EURUSD D1 mar
    call "%~dp0run_opt.cmd" USDCAD H4 mar
    call "%~dp0run_opt.cmd" USDCHF D1 mar
