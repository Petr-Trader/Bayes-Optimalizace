
# bayes_optimize_parallel_v5_0.py
# - Keeps logic from v4_1
# - FIX: explicitly sets Expert=... and ExpertParameters=... into INI
# - NEW: derives Symbol/Period from base .set filename (FX_CarryMomentum_<SYMBOL>_<TF>.set) and writes them into INI
# - NEW: --expert CLI arg (default FX_CarryMomentum.ex5)
# - Paths default to Bayes-Optimalizace tree
# - Fallback minimal INI template if TEMPLATE_INI is missing
import argparse, csv, json, os, random, time, math, subprocess, re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

import numpy as np
from bayes_opt import BayesianOptimization
try:
    from bayes_opt import UtilityFunction  # type: ignore
except Exception:
    try:
        from bayes_opt.util import UtilityFunction  # type: ignore
    except Exception:
        class UtilityFunction:  # minimal fallback
            def __init__(self, kind: str, kappa: float = 2.5, xi: float = 0.0):
                self.kind = (kind or "ei").lower(); self.kappa = float(kappa); self.xi = float(xi)
            @staticmethod
            def _norm_pdf(x): import math; return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)
            @staticmethod
            def _norm_cdf(x): import math; return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
            def utility(self, x, gp, y_max):
                mu, sigma = gp.predict(x, return_std=True)
                import numpy as np
                mu = np.asarray(mu, dtype=float); sigma = np.asarray(sigma, dtype=float); sigma = np.maximum(sigma, 1e-12)
                z = (mu - y_max - self.xi) / sigma
                if self.kind == "ucb": return mu + self.kappa * sigma
                vec_pdf = np.vectorize(self._norm_pdf); vec_cdf = np.vectorize(self._norm_cdf)
                if self.kind in ("poi","pi"): return vec_cdf(z)
                return (mu - y_max - self.xi) * vec_cdf(z) + sigma * vec_pdf(z)

from mt5_report_parser import parse_mt5_html_metrics

# ===================== DEFAULT PATHS =====================
TEMPLATE_INI   = r"C:\CLON_Git\Bayes-Optimalizace\reports\bayes\base_tester.ini"
OUT_INI_DIR    = r"C:\CLON_Git\Bayes-Optimalizace\reports\bayes\_jobs"
REL_REPORT_DIR = r"reports\bayes"
RESULTS_DIR    = r"C:\CLON_Git\Bayes-Optimalizace\bayes\results"
AUTO_BASE_DIR  = r"C:\MT5_Portable"
# =========================================================

TF_MAP = {
    'M1':'M1','M5':'M5','M15':'M15','M30':'M30',
    'H1':'H1','H2':'H2','H3':'H3','H4':'H4','H6':'H6','H8':'H8','H12':'H12',
    'D1':'D1','W1':'W1','MN1':'MN1'
}

def ensure_dirs(terminals: List[str]):
    Path(OUT_INI_DIR).mkdir(parents=True, exist_ok=True)
    Path(RESULTS_DIR).mkdir(parents=True, exist_ok=True)
    for term in terminals:
        (Path(term).parent / REL_REPORT_DIR).mkdir(parents=True, exist_ok=True)

def kill_mt5_all():
    for exe in ("terminal64.exe", "terminal.exe"):
        subprocess.run(["taskkill", "/F", "/IM", exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def read_text(p: str) -> str:
    return Path(p).read_text(encoding="utf-8", errors="ignore")

def write_text(p: str, s: str):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(s, encoding="utf-8")

def load_template_text() -> str:
    p = Path(TEMPLATE_INI)
    if p.exists():
        try:
            return read_text(str(p))
        except Exception:
            pass
    # Minimal working template if user doesn't provide base ini
    return """[Tester]
Login=0
Password=
Expert=FX_CarryMomentum.ex5
ExpertParameters=auto_bayes.set
Symbol=EURUSD
Period=H4
Model=0
Optimization=1
ReplaceReport=1
ShutdownTerminal=1
Report=reports\\bayes\\auto.html
"""

def tweak_ini(template_text: str, replacements: Dict) -> str:
    lines = template_text.splitlines()
    out = []
    keys = dict(replacements)  # copy
    for ln in lines:
        if "=" in ln:
            k = ln.split("=", 1)[0].strip()
            if k in keys:
                out.append(f"{k}={keys.pop(k)}")
                continue
        out.append(ln)
    for k, v in keys.items():  # append missing
        out.append(f"{k}={v}")
    existing = {l.split("=",1)[0].strip() for l in out if "=" in l}
    if "ReplaceReport" not in existing: out.append("ReplaceReport=1")
    if "ShutdownTerminal" not in existing: out.append("ShutdownTerminal=1")
    return "\n".join(out) + "\n"

def read_set(path: str):
    for enc in ("utf-16", "utf-8", "cp1250", "latin-1"):
        try:
            return Path(path).read_text(encoding=enc, errors="ignore").splitlines(True)
        except Exception:
            pass
    return Path(path).read_text(encoding="utf-16", errors="ignore").splitlines(True)

def save_set(base_lines, overrides: Dict, out_path: str):
    out_lines = []
    for ln in base_lines:
        if "=" in ln:
            k, v = ln.split("=", 1); k_stripped = k.strip()
            if k_stripped in overrides:
                out_lines.append(f"{k_stripped}={overrides[k_stripped]}\n"); continue
        out_lines.append(ln)
    Path(out_path).write_text("".join(out_lines), encoding="utf-16")

def parse_space(path: str) -> Dict:
    space = json.loads(Path(path).read_text(encoding="utf-8"))
    norm = {}
    for k, cfg in space.items():
        t = (cfg.get("type") or "float").lower()
        lo = float(cfg["low"]); hi = float(cfg["high"]); step = cfg.get("step")
        norm[k] = {"type": t, "low": lo, "high": hi, "step": step}
    return norm

def cast_param(name: str, val: float, pinfo: Dict):
    t = pinfo["type"]; step = pinfo.get("step")
    if t == "int":
        if step: return int(round(val / float(step)) * float(step))
        return int(round(val))
    else:
        if step: s = float(step); return round(round(val / s) * s, 10)
        return float(val)

def smooth_trades_bonus(trades: int, target: int) -> float:
    if target <= 0: return 1.0
    return 1.0 - math.exp(-max(0.0, float(trades)) / float(target))

def score_from_metrics(m: Dict, obj: str, maxdd_cap=8.0, min_trades=0, target_trades=400, dd_lambda=0.2):
    trades = int(float(m.get("TotalTrades") or 0))
    if trades < min_trades: return -1e9
    pf = float(m.get("ProfitFactor") or 0.0)
    dd_pct = float(m.get("MaxDDPercent") or 0.0)
    net = float(m.get("NetProfit") or 0.0)
    dd_money = float(m.get("MaxDDMoney") or 0.0)

    if obj == "pf":
        penalty = max(0.0, dd_pct - maxdd_cap) / 10.0
        return pf - penalty

    if obj == "pf_trades":
        penalty = max(0.0, dd_pct - maxdd_cap) / 10.0
        bonus = smooth_trades_bonus(trades, target_trades)
        return (pf - penalty) * (0.5 + 0.5 * bonus)

    if obj == "netdd":
        return net - dd_lambda * dd_money

    return net / (1.0 + dd_money)

def _term_set_dir(term_exe: str) -> Path:
    return Path(term_exe).parent / "MQL5" / "Profiles" / "Tester"

def _resolve_report_path(term_exe: str, report_rel: str) -> str:
    term_dir = Path(term_exe).parent
    for p in [term_dir / report_rel, term_dir / "Tester" / report_rel, term_dir / "MQL5" / "Tester" / report_rel]:
        if p.exists(): return str(p)
    return str(term_dir / report_rel)

def _detect_symbol_tf_from_set(base_set_path: str):
    base = Path(base_set_path).name
    name = base.rsplit(".",1)[0]
    import re
    parts = re.split(r"[ _\-]+", name)
    tf = None; symbol = None
    TF_MAP = {'M1','M5','M15','M30','H1','H2','H3','H4','H6','H8','H12','D1','W1','MN1'}
    for i, t in enumerate(parts):
        if t.upper() in TF_MAP:
            tf = t.upper()
            if i>0: symbol = parts[i-1].upper()
            break
    if tf is None: tf = "H4"
    if symbol is None: symbol = "EURUSD"
    return symbol, tf

def run_one(term_exe: str, template_text: str, base_set_path: str, expert: str, params: Dict,
            rel_report_dir: str, min_trades: int, maxdd_cap: float, obj: str, target_trades: int, dd_lambda: float) -> Dict:
    set_dir = _term_set_dir(term_exe); set_dir.mkdir(parents=True, exist_ok=True)
    base_lines = read_set(base_set_path)

    iter_id = int(time.time() * 1000) % 1_000_000_000
    set_name = f"auto_bayes_{iter_id}.set"
    set_path = str(set_dir / set_name)

    overrides = dict(params); save_set(base_lines, overrides, set_path)

    symbol, period = _detect_symbol_tf_from_set(base_set_path)

    slug = f"bayes_{iter_id}"
    report_rel = str(Path(rel_report_dir) / f"{slug}.html")
    ini_out = str(Path(OUT_INI_DIR) / f"{slug}.ini")
    ini_text = tweak_ini(template_text, {
        "Expert": expert,
        "ExpertParameters": set_path,
        "Symbol": symbol,
        "Period": period,
        "Report": report_rel,
    })
    write_text(ini_out, ini_text)

    start = time.time()
    try:
        subprocess.run([term_exe, "/portable", f"/config:{ini_out}"], check=False)
    except Exception as e:
        secs = time.time() - start
        return {"slug": slug, "term": Path(term_exe).parent.name, "set_name": set_name,
                "report": "", "rc": -1, "secs": secs, "params": overrides,
                "metrics": {"ProfitFactor":0.0,"MaxDDPercent":0.0,"TotalTrades":0},"score": -1e9,
                "note": f"RUN_ERR:{e.__class__.__name__}"}
    secs = time.time() - start

    report_abs = _resolve_report_path(term_exe, report_rel)
    deadline = time.time() + 300
    while not Path(report_abs).exists() and time.time() < deadline:
        time.sleep(1.0)

    note = "NO_REPORT"
    metrics = {"ProfitFactor":0.0,"MaxDDPercent":0.0,"TotalTrades":0,"NetProfit":0.0,"GrossProfit":0.0,"GrossLoss":0.0,
               "Commissions":0.0,"Swap":0.0,"MaxDDMoney":0.0,"SharpeRatio":0.0}
    if Path(report_abs).exists():
        try:
            m = parse_mt5_html_metrics(report_abs)
            for k in metrics.keys():
                if k in m and m[k] is not None:
                    metrics[k] = float(m[k]) if k != "TotalTrades" else int(m[k])
            note = "PARSED"
        except Exception as e:
            note = f"PARSE_ERR:{e.__class__.__name__}"

    score = score_from_metrics(metrics, obj=obj, maxdd_cap=maxdd_cap, min_trades=min_trades,
                               target_trades=target_trades, dd_lambda=dd_lambda)
    return {"slug": slug, "term": Path(term_exe).parent.name, "set_name": set_name, "report": report_abs, "rc": 0,
            "secs": secs, "params": overrides, "metrics": metrics, "score": score, "note": note}

def detect_terminals_auto():
    base = Path(r"C:\MT5_Portable")
    if not base.exists(): return []
    term_paths = []
    for p in base.iterdir():
        exe = p / "terminal64.exe"
        if exe.exists(): term_paths.append(str(exe))
    term_paths.sort()
    return term_paths

def open_log_for_write(append: bool = False):
    base_log = Path(r"C:\CLON_Git\Bayes-Optimalizace\bayes\results") / "bayes_opt_log.csv"
    if append and base_log.exists():
        f = open(base_log, "a", newline="", encoding="utf-8-sig"); return f, str(base_log), False
    try:
        f = open(base_log, "w", newline="", encoding="utf-8-sig"); return f, str(base_log), True
    except PermissionError:
        ts = time.strftime("%Y%m%d_%H%M%S"); alt = base_log.parent / f"bayes_opt_log_{ts}.csv"
        f = open(alt, "w", newline="", encoding="utf-8-sig"); print(f"[warn] {base_log} locked; using {alt}"); return f, str(alt), True

def clamp_to_bounds(params, pbounds):
    out = {}
    for k, v in params.items():
        if k not in pbounds: continue
        lo, hi = pbounds[k]
        try: fv = float(v)
        except Exception: continue
        if fv < lo: fv = lo
        if fv > hi: fv = hi
        out[k] = fv
    return out

def parse_float_safe(x):
    try: return float(x)
    except Exception: return None

def iter_resume_logs(spec: str):
    import glob
    paths = []
    for part in spec.split(";"):
        part = part.strip()
        if not part: continue
        if any(ch in part for ch in "*?"):
            for s in sorted(glob.glob(part)):
                p = Path(s)
                if p.exists() and p.is_file() and p.suffix.lower() == ".csv":
                    paths.append(p)
            continue
        p = Path(part)
        if p.exists():
            if p.is_dir(): paths.extend(sorted(p.glob("*.csv"), key=lambda t: t.stat().st_mtime))
            elif p.is_file() and p.suffix.lower() == ".csv": paths.append(p)
    return paths

def seed_from_logs(optimizer, logs, space, pbounds):
    seeded = 0; used = set()
    for log in logs:
        try:
            import csv
            with open(log, "r", encoding="utf-8-sig") as f:
                rdr = csv.reader(f)
                header = next(rdr, None)
                if not header: continue
                try: score_idx = header.index("score")
                except ValueError: score_idx = 6 if len(header) > 6 and header[6] == "score" else None
                if score_idx is None: continue
                param_indices = {k: header.index(k) for k in space.keys() if k in header}
                for row in rdr:
                    if not row or len(row) <= score_idx: continue
                    sc = parse_float_safe(row[score_idx]); if sc is None or sc <= -1e8: continue
                    params = {}
                    for k, idx in param_indices.items():
                        if idx < len(row):
                            val = parse_float_safe(row[idx]); 
                            if val is not None: params[k] = val
                    if not params: continue
                    params = clamp_to_bounds(params, pbounds)
                    key = tuple(sorted(params.items()))
                    if key in used: continue
                    try: optimizer.register(params=params, target=sc); used.add(key); seeded += 1
                    except Exception: pass
        except Exception: pass
    return seeded

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--terms", required=True, help="';' separated terminal64.exe paths OR 'auto' to scan C:\\MT5_Portable")
    ap.add_argument("--space", default=r"C:\CLON_Git\Bayes-Optimalizace\bayes\space\carrymomentum_space.json")
    ap.add_argument("--set", dest="base_set", required=True, help="Path to baseline .set")
    ap.add_argument("--expert", default="FX_CarryMomentum.ex5")
    ap.add_argument("--init_points", type=int, default=60)
    ap.add_argument("--iters", type=int, default=390)
    ap.add_argument("--min_trades", type=int, default=200)
    ap.add_argument("--maxdd_cap", type=float, default=8.0)
    ap.add_argument("--acq", default="ei", choices=["ei","ucb","poi"])
    ap.add_argument("--kappa", type=float, default=2.5)
    ap.add_argument("--xi", type=float, default=0.0)
    ap.add_argument("--obj", default="mar", choices=["pf","pf_trades","mar","netdd"])
    ap.add_argument("--target_trades", type=int, default=400)
    ap.add_argument("--dd_lambda", type=float, default=0.2)
    ap.add_argument("--patience", type=int, default=120)
    ap.add_argument("--tol", type=float, default=0.01)
    ap.add_argument("--min_evals", type=int, default=200)
    ap.add_argument("--resume_from_log", default="")
    ap.add_argument("--append_log", action="store_true")
    args = ap.parse_args()

    if args.terms.strip().lower() == "auto":
        terminals = detect_terminals_auto()
        if not terminals: raise SystemExit(f"[ERR] Auto-scan nenasel zadne terminal64.exe v C:\\MT5_Portable")
        print("[info] Auto-detekovane terminaly:"); [print("  -", t) for t in terminals]
    else:
        terminals = [t for t in args.terms.split(";") if t.strip()]
    if not terminals: raise SystemExit("No terminals provided.")

    ensure_dirs(terminals); kill_mt5_all()

    template_text = load_template_text()
    space = parse_space(args.space)
    pbounds = {k: (cfg["low"], cfg["high"]) for k, cfg in space.items()}

    optimizer = BayesianOptimization(f=None, pbounds=pbounds, verbose=2, allow_duplicate_points=True)
    try:
        util = UtilityFunction(kind=args.acq, kappa=args.kappa, xi=args.xi)
        def suggest_next():
            try: return optimizer.suggest(util)
            except TypeError: return optimizer.suggest()
    except Exception:
        def suggest_next():
            try: return optimizer.suggest()
            except Exception:
                return {k: random.uniform(lo, hi) for k, (lo, hi) in pbounds.items()}

    seeded = 0
    if args.resume_from_log.strip():
        logs = iter_resume_logs(args.resume_from_log.strip())
        if logs:
            print(f"[resume] Found {len(logs)} log file(s) to seed.")
            seeded = seed_from_logs(optimizer, logs, space, pbounds)
            print(f"[resume] Seeded {seeded} previous evaluations into optimizer.")
        else:
            print("[resume] No matching logs found. Starting fresh.")

    Path(r"C:\CLON_Git\Bayes-Optimalizace\bayes\results").mkdir(parents=True, exist_ok=True)
    f = open(Path(r"C:\CLON_Git\Bayes-Optimalizace\bayes\results") / "bayes_opt_log.csv", "a", newline="", encoding="utf-8-sig")
    w = csv.writer(f)
    if f.tell() == 0:
        header = ["slug", "term", "set_file", "report_path", "returncode", "secs", "score", "note"]
        header += list(space.keys())
        header += ["ProfitFactor","MaxDDPercent","TotalTrades","NetProfit","GrossProfit","GrossLoss","Commissions","Swap","MaxDDMoney","SharpeRatio"]
        w.writerow(header)

    best_score = -1e18; stagnation = 0
    def cast_all(params_floats):
        return {k: cast_param(k, v, space[k]) for k, v in params_floats.items()}

    total_needed = args.init_points + args.iters
    submitted = 0; completed = 0; running = {}

    def submit_point(executor, params_floats, tag):
        nonlocal submitted
        if submitted >= total_needed: return False
        casted = cast_all(params_floats)
        term = terminals[submitted % len(terminals)]
        fut = executor.submit(run_one, term, template_text, args.base_set, args.expert, casted, REL_REPORT_DIR,
                              args.min_trades, args.maxdd_cap, args.obj, args.target_trades, args.dd_lambda)
        running[fut] = (tag, casted); submitted += 1; return True

    with ThreadPoolExecutor(max_workers=len(terminals)) as ex:
        while len(running) < len(terminals) and submitted < total_needed and submitted < args.init_points:
            rnd = {k: random.uniform(lo, hi) for k, (lo, hi) in pbounds.items()}
            submit_point(ex, rnd, "RND")

        while completed < total_needed:
            done_any = False
            for fut in list(running.keys()):
                if fut.done():
                    tag, casted = running.pop(fut)
                    try: res = fut.result()
                    except Exception as e:
                        print("[ERR] worker failed:", e); completed += 1; done_any = True; continue

                    optimizer.register(params=casted, target=res["score"])
                    row = [res["slug"], res["term"], res["set_name"], res["report"], res["rc"], f"{res['secs']:.1f}", res["score"], res["note"]]
                    for k in space.keys(): row.append(casted.get(k))
                    for k in ("ProfitFactor","MaxDDPercent","TotalTrades","NetProfit","GrossProfit","GrossLoss","Commissions","Swap","MaxDDMoney","SharpeRatio"):
                        row.append(res["metrics"].get(k, ""))
                    w.writerow(row); f.flush()

                    completed += 1
                    print(f"[{completed}/{total_needed}] {tag} score={res['score']:.4f} PF={res['metrics'].get('ProfitFactor')} DD%={res['metrics'].get('MaxDDPercent')} Net={res['metrics'].get('NetProfit')} Trades={res['metrics'].get('TotalTrades')} via {res['term']}")

                    if res["score"] > best_score * (1.0 + args.tol): best_score = res["score"]; stagnation = 0
                    else: stagnation += 1

                    still_need = (submitted < total_needed)
                    if still_need:
                        if submitted < args.init_points:
                            rnd = {k: random.uniform(lo, hi) for k, (lo, hi) in pbounds.items()}
                            submit_point(ex, rnd, "RND")
                        else:
                            try: sug = optimizer.suggest(util)
                            except Exception: sug = {k: random.uniform(lo, hi) for k, (lo, hi) in pbounds.items()}
                            submit_point(ex, sug, "SUG")

                    done_any = True

            if completed >= args.min_evals and stagnation >= args.patience:
                print(f"[early-stop] No improvement > {args.tol*100:.1f}% over last {stagnation} evals (min_evals reached). Stopping.")
                break

            if not done_any: time.sleep(0.5)

    f.close()
    best = optimizer.max
    Path(r"C:\CLON_Git\Bayes-Optimalizace\bayes\results\bayes_opt_best.json").write_text(json.dumps(best, indent=2), encoding="utf-8")
    print("Best:", best)
    print("Log:", str(Path(r"C:\CLON_Git\Bayes-Optimalizace\bayes\results") / "bayes_opt_log.csv"))
    print("Seeded from logs:", 0)

if __name__ == "__main__":
    main()
