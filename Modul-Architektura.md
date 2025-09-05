1) Moduly a jejich jasné rozhraní

Každý modul je samostatně spustitelný (CLI), čitelný (logy), testovatelný (pytest) a generuje/čte kontrakt – soubory s definovaným schématem. Tím se minimalizují „skryté“ závislosti.

env_check

Co dělá: ověří prostředí (cesty k terminálům, oprávnění, Python verzi, přítomnost MT5, existenci adresářů reportů, volné místo).

Vstup: config/env.yaml

Výstup: results/env_check.json (detailní report + doporučení).

universe_builder

Co dělá: skládá obchodní univerzum (symboly, TF, broker specifika: suffixy, lot step, point, povolené času/Session).

Vstup: config/universe.yaml

Výstup: artifacts/universe.parquet (nebo .json), aby se dalo znovu načíst 1:1.

indicator_catalog (tvoje YAML knihovna – „jediný zdroj pravdy“)

Co dělá: drží přesné názvy indikátorů/parametrů tak, jak je chápe MT5/EA, jejich aliasy, typy, rozsahy, defaulty, step, validátory.

Vstup/Výstup: catalog/indicators.yaml (verzované, lintované).

space_generator

Co dělá: z indicators.yaml a zvoleného EA profilu vygeneruje optimalizační prostor (Bayes/Optuna). Umí „rozumné“ default rozsahy per TF/symbol.

Vstup: profiles/EA_<name>.yaml + catalog/indicators.yaml

Výstup: bayes/space.json (jednotný formát pro optimizer).

set_builder

Co dělá: z profilu a konkrétní navržené sady hyperparametrů vyrobí .set pro MT5 (100% shoda názvů s EA Inputs).

Vstup: profiles/EA_<name>.yaml + vzorek params.json

Výstup: sets/generated/EA_<name>__<symbol>_<TF>__<run_id>.set

runner_mt5

Co dělá: orchestrace paralelního spuštění Strategy Testeru v MT5_A/B/C…, kontrola návratových kódů, retry logika, timeouts, throttle (aby se nesejmul disk).

Vstup: sets/generated/*.set + bayes/space.json

Výstup: reports/raw/*.html, logs/mt5/*.log

report_parser

Co dělá: robustní parser MT5 HTML/CSV (PF, Net, DD%, MAR…), validace, detekce chybných běhů.

Vstup: reports/raw/*.html

Výstup: results/parsed.parquet (nebo .csv v utf-8-sig), s klíči run_id, symbol, tf, params_hash.

objective_scorer

Co dělá: spočítá cíle pro Bayes (MAR, PF, robustní penalizace za málo obchodů, outlier handling), podporuje více objektivů (váhy/pareto).

Vstup: results/parsed.parquet

Výstup: results/scored.parquet + results/best.json

leaderboard_maker

Co dělá: generuje přehled (HTML/CSV) + barevné zvýraznění (top N, min trades, filtry), kopíruje nejlepší .set do sets/deploy.

Vstup: results/scored.parquet

Výstup: results/leaderboard.html, sets/deploy/*.set

deployer

Co dělá: připraví final .set pro živé/dema, pojmenuje dle konvence (symbol-TF-Magic-verze), ověří kompatibilitu s EA verzí.

Vstup: sets/deploy/*.set

Výstup: deploy/… + krátký „runbook“ (kroky nasazení).

monitor_live (volitelné, později)

Co dělá: čte živé výpisy/MT5 journaly/účty a kontroluje drift vs. backtest metriky, varuje.

Každý modul má: cli.py, core.py, schema.py, testy v tests/…, a jasně definované schéma vstupů/výstupů (pydantic).

2) YAML knihovna indikátorů – „jediný zdroj pravdy“

Cíl: sjednotit názvy přesně tak, jak je čte EA/MT5. Včetně aliasů, typů a rozsahů podle TF a sensible defaults.

# catalog/indicators.yaml  (verze: 1.00)
version: "1.00"
indicators:
  RSI:
    mt5_name: "RSI"                 # název v MT5 i v EA
    aliases: ["RelativeStrengthIndex", "iRSI"]
    inputs:
      Period:
        type: int
        default: 14
        range:
          H1:   {min: 5,  max: 40, step: 1}
          H4:   {min: 5,  max: 50, step: 1}
          D1:   {min: 5,  max: 60, step: 1}
      AppliedPrice:
        type: enum
        allowed: ["CLOSE","OPEN","HIGH","LOW","MEDIAN","TYPICAL","WEIGHTED"]
        default: "CLOSE"
  ADX:
    mt5_name: "ADX"
    aliases: ["AverageDirectionalMovementIndex", "iADX"]
    inputs:
      Period:
        type: int
        default: 14
        range:
          H1: {min: 7, max: 40, step: 1}
          H4: {min: 7, max: 50, step: 1}
      Price:
        type: enum
        allowed: ["CLOSE","HIGH_LOW"]
        default: "HIGH_LOW"


Pozn.: YAML drží jen „fakta o indikátorech“. Mapování na EA inputs (např. InpRsiPeriod) dej do profilu EA.

3) Profil EA = mapování na konkrétní Inputs + business logika

Profil říká, které části katalogu se opravdu používají, jak se jmenují v tom EA, a jaké jsou rozsahy pro optimalizaci.

# profiles/EA_FX_CarryMomentum.yaml  (v1.14)
ea:
  name: "FX_CarryMomentum"
  version: "1.14"
  inputs:
    InpRsiPeriod:
      from_indicator: "RSI"
      field: "Period"
      override_range:
        H4: {min: 8, max: 35, step: 1}
    InpRsiAppliedPrice:
      from_indicator: "RSI"
      field: "AppliedPrice"
    InpAdxPeriod:
      from_indicator: "ADX"
      field: "Period"
    InpLotSize:
      type: float
      default: 0.10
      range: {min: 0.01, max: 1.00, step: 0.01}
  constraints:
    min_trades: 50
    max_dd_pct: 35
  objective:
    primary: "MAR"
    secondary: "PF"
universe_ref: "../config/universe.yaml"

4) Generování Bayes prostoru (automaticky z profilu)

space_generator přečte profily + katalog → vytvoří bayes/space.json s typy (int/float/categorical), rozsahy podle TF, případné log-uniform pro citlivé parametry (např. ATR multipliers).

Výhoda: Rozpory mezi kódy zmizí – názvy a typy jdou z jednoho zdroje.

5) .set soubory bez chyb v názvech

set_builder vytvoří .set přesně podle ea.inputs.

Validační krok: porovná klíče .set s odvoditelným seznamem extern inputů EA (máme-li šablonu) → při neshodě fail fast s přesnou zprávou.

Konvence názvu:
EA_<name>__<SYMBOL>_<TF>__run-<iter>__magic-<id>__v<ea_version>.set

6) Robustní běh a reproducibilita

Seeds & run_id: Každý běh má run_id, params_hash, timestamp, verzi katalogu/profilu, verzi EA a MT5 build.

Cache: stejné params_hash + data span + EA version → skip.

Retry: MT5 run, když padne (timeout/exit code), 2× retry se zvětšujícím se backoff.

UTF-8-SIG pro CSV exporty (pro Excel).

7) Testy (rychlé, spustitelné v CI)

tests/test_catalog_schema.py – validace YAML proti pydantic schématu, duplicity aliasů, allowed hodnoty.

tests/test_space_generator.py – že se vygenerují správné typy a rozsahy.

tests/test_set_builder.py – syntéza .set, kontrola názvů a typů.

tests/test_report_parser.py – na vzorových HTML extrahuje správné metriky.

tests/test_objective_scorer.py – MAR/PF/min_trades penalizace.

„smoke test“ pipeline na mockovaných datech (bez MT5).

8) CI a verzování

CI (GitHub Actions): ruff + mypy + pytest (rychlé subsety), validace YAML.

Semver pro katalog (catalog v1.00 → v1.01) a profily EA.

Changelogs: co se změnilo v rozsazích/defaults (a proč).

9) Sjednocení názvosloví (aliasy → canonical)

V katalogu udržuj seznam aliasů (např. RSI, RelativeStrengthIndex, iRSI) → vše mapuj na mt5_name.

V profilech už používej jen canonical.

Pokud v MQL5 přejmenuješ Input, aktualizuješ pouze profil (ne kód u 100 skriptů).

10) „Rozumné rozsahy“ (min/max) – jak je nastavit chytře

V katalogu může být per-TF baseline.

space_generator může mít policy:

safe (užší, rychlé hledání),

wide (objevné),

informed (z dat: spočti průměrné/mediánové hodnoty z „rychlé grid-scan“ pre-fáze a zuž param. okna o ±k st.dev).

Pro některé parametry použij log-scale (např. ATR multipliers).

11) Nasazení po optimalizaci (bez chaosu)

deployer vygeneruje .set + „manifest“ (JSON): symbol, TF, Magic, EA verze, datum optimalizace, metriky, katalog/profil verze.

Manifest uloží do deploy/<EA>/<SYMBOL>/<TF>/manifest.json → máš úplnou historii.

Magic: Jeden EA × symbol × TF → unikátní Magic. Správa v config/magic_registry.yaml + kontrola kolizí před nasazením.

12) Co doplnit / na co jsi (možná) zapomněl

EA introspection (volitelně): jednoduchý „header“ nebo auto-export Inputů z EA do JSON (např. při kompilaci), aby set_builder mohl strojově ověřit dostupné Inputs a typy.

Broker quirks: suffixy symbolů, trading hours, minimální lot, tick size – dej do config/broker/<darwinex>.yaml a zahrň do validací.

Data span „IS/OOS“: Nadiktuj povinný split (např. IS 2020-2023, OOS 2024-2025H1) a penalizuj velký drop OOS vs. IS.

Early stop kritéria (stagnace zlepšení × iterace) přímo v objective_scorer.

Resource guard: limiter CPU/IO, aby paralelní běhy neničily disk.

Telemetry: krátká HTML dashboardka s průběhem (iterace, nejlepší skóre, heatmapy parametrů).

# ...existing code...
13) Návrh struktury repo (jen jádro)
Modul-Bayes/
  catalog/
    indicators.yaml
  profiles/
    EA_FX_CarryMomentum.yaml
    EA_FollowTrend.yaml
  config/
    env.yaml
    universe.yaml
    broker/darwinex.yaml
    magic_registry.yaml
  bayes/
    space.json
  sets/
    baseline/
    generated/
    deploy/
  reports/
    raw/
  results/
    parsed.parquet
    scored.parquet
    leaderboard.html
  logs/
  modules/
    env_check/
    universe_builder/
    indicator_catalog/
    space_generator/
    set_builder/
    runner_mt5/
    report_parser/
    objective_scorer/
    leaderboard_maker/
    deployer/
  tests/
  pyproject.toml
  README.md
# ...existing code...

14) Mini příklady rozhraní (konzistentní CLI)

python -m modules.space_generator --ea profiles/EA_FX_CarryMomentum.yaml --tf H4 --policy informed --out bayes/space.json

python -m modules.set_builder --ea profiles/...yaml --symbol EURUSD --tf H4 --params params.json --out sets/generated/...set

python -m modules.runner_mt5 --sets sets/generated --terms "C:\MT5_A\terminal64.exe;C:\MT5_B\terminal64.exe" --max-parallel 2

python -m modules.leaderboard_maker --in results/parsed.parquet --score results/scored.parquet --top 50 --copy-sets sets/deploy

15) Co ti to přinese hned teď

Konec rozcházejících se názvů: YAML katalog + profily EA → jeden zdroj pravdy.

Determinismus: Každý krok má kontrakt (soubor), takže snadno dohledáš, kde se něco pokazilo.

Rychlejší ladění: Testy a lint pro YAML odhalí chyby dřív, než spustíš MT5.

Škálování: Přidat nový EA/symbol/TF = přidat profil/yaml, nemusíš přepisovat kód.

16) Navržené „další kroky“ (stručně)

Vytvořím pydantic schéma pro indicators.yaml + profiles/*.yaml.

Připravím první verzi katalogu pro RSI/ADX/EMA/ATR (H1/H4/D1 rozsahy).

Nadefinuju space_generator v1.00 a set_builder v1.00 (nejvíc pálí).

Přidám tests pro katalog, space a set builder.

Přepojíme tvůj současný Bayes skript, aby bral bayes/space.json a .set z builderu.

Zprovozníme leaderboard_maker nad tvými parsovanými reporty (ponecháme utf-8-sig).