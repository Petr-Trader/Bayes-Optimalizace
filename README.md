# README.md
// filepath: c:\CLON_Git\Bayes-Optimalizace\README.md

# Bayes-Optimalizace FX_CarryMomentum

## Popis projektu
Optimalizace parametrů FX carry/momentum strategie v MetaTrader 5 pomocí Bayesovské optimalizace v Pythonu.  
Strategie kombinuje trendové indikátory (EMA) a úrokový diferenciál (carry).

## Workflow
1. **Definice portfolia**: `config/carry_portfolio.yaml`
2. **Parametry strategie**: `sets/baseline/*.set`
3. **Optimalizační prostor**: `bayes/space/*.json`
4. **Spuštění optimalizace**: `scripts/run_opt.cmd` nebo `bayes_optimize_parallel_v5_0.py`
5. **Parsování výsledků**: `mt5_report_parser.py`
6. **Výsledky**: `bayes/results/`

## Jak začít
- Otevři projekt ve VS Code.
- Synchronizuj změny přes Git (`pull` před prací, `push` po práci).
- Spouštěj skripty v integrovaném terminálu (CMD).
- Piš poznámky do TODO.md.

## Doporučená rozšíření VS Code
- Python
- YAML
- GitLens
- Markdown All in One

## Dokumentace strategie
Viz soubor: `Charakteristika strategie FX_CarryMomentum.mnd`