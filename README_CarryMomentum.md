# CarryMomentum – Bayes Optimalizace (Starter v1.00)

Tento balíček je šablona, která sjednotí workflow mezi DOMA a PRÁCE (bez PowerShellu).
Vše běží přes CMD `.cmd` skripty a Git.

## 1) Doporučená větev
- Vytvoř si větev `cm/bootstrap` v repo Bayes-Optimalizace a soubory z této šablony tam nahraj.
- Doma: commit + push.
- V práci: `git fetch` + `git checkout -B cm/bootstrap origin/cm/bootstrap`.

## 2) Důležité cesty (edituj ve `scripts/env_vars_example.cmd`)
- `REPO=C:\CLON_Git\Bayes-Optimalizace`
- `MT5_TERMS=C:\MT5_Portable\MT5_A\terminal64.exe`
- `SPACE=%REPO%\bayes\space\carrymomentum_space.json`
- `SETS=%REPO%\sets\baseline`

## 3) Portfolio
Upravit `config/carry_portfolio.yaml`. Výchozí:
- AUDJPY D1, GBPJPY H4, EURUSD D1, USDCAD H4, USDCHF D1

## 4) Spuštění (CMD)
- Otevři `cmd.exe`
- `cd %REPO%\scripts`
- `call env_vars_example.cmd`
- Jednotlivě: `call run_opt.cmd AUDJPY D1 mar`
- Batch: `call run_all_example.cmd`

## 5) EMA Guard (aby Fast < Slow)
- Vložit patch z `patches/ema_guard.diff` do `bayes_optimize_parallel_v4_1.py` (sekce objective).
- Pokud používáš jiné jméno souboru, přenes princip: když `fast >= slow`, vrať penalizované skóre.

## 6) .set soubory
- Vyplň baseliny v `sets/baseline/*.set` (správné defaulty, money-management atd.).
- Výstupní best .set ukládej do `sets/best/` (vytvoříš si adresář).

## 7) Doporučená disciplína s Gitem
- Každá úprava = commit s jasným message, např. `feat(cm): ema-guard in objective`
- Před prací na druhém stroji: `git pull`
- Nikdy neupravuj lokální soubory bez commitu/pushnutí, jinak se verze rozjedou.

## 8) Kontrola prostředí
- `scripts/verify_versions.cmd` vypíše verzi Pythonu a Gitu, funguje i v práci.

---
Šablona je minimální – přidej si vlastní report/leaderboard kroky, které už máš.
