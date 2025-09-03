# -*- coding: utf-8 -*-
"""
Robust MT5 Strategy Tester HTML report parser.

- Handles Czech/English labels.
- Correctly parses numbers with thousands separators (space/NBSP) and decimal comma/dot.
- Extracts: ProfitFactor, TotalTrades, MaxDDPercent, NetProfit, OnTester, MaxDDMoney, encoding.
"""
import re
from bs4 import BeautifulSoup

def detect_encoding(data: bytes):
    if data.startswith(b'\xff\xfe') or data.startswith(b'\xfe\xff'):
        return 'utf-16'
    if b'\x00' in data[:2000]:
        return 'utf-16'
    for enc in ('utf-8', 'cp1250', 'latin-1'):
        try:
            data.decode(enc)
            return enc
        except Exception:
            continue
    return 'utf-8'

def _norm_text(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def _get_cell_value_after_label(soup: BeautifulSoup, label_candidates):
    tds = soup.find_all('td')
    for i, td in enumerate(tds):
        txt = td.get_text(' ', strip=True)
        n = _norm_text(txt)
        for lab in label_candidates:
            if lab in n:
                if i+1 < len(tds):
                    return tds[i+1].get_text(' ', strip=True)
    return None

def _parse_first_number(s):
    if not s:
        return None
    # Allow thousands separators (space or NBSP) and optional decimal part.
    pat = r'[-+]?(?:\d{1,3}(?:[ \xa0]\d{3})+|\d+)(?:[.,]\d+)?'
    m = re.search(pat, s.replace('\xa0', ' '))
    if not m:
        return None
    raw = m.group(0)
    val = raw.replace(' ', '').replace('\xa0', '').replace(',', '.')
    try:
        return float(val)
    except Exception:
        return None

def parse_mt5_html_metrics(path):
    from pathlib import Path
    data = Path(path).read_bytes()
    enc = detect_encoding(data)
    txt = data.decode(enc, errors='ignore')
    soup = BeautifulSoup(txt, 'html.parser')

    # Texts
    pf_txt = _get_cell_value_after_label(soup, ['ukazatel zisku', 'profit factor'])
    tt_txt = _get_cell_value_after_label(soup, ['celkem obchodu', 'total trades'])
    dd_txt = _get_cell_value_after_label(soup, [
        'nejvetsi ztrata na zustatku od lokalniho maxima',  # CZ balance
        'maximal drawdown'                                   # EN
    ])
    np_txt = _get_cell_value_after_label(soup, ['cisty zisk celkem', 'net profit'])
    ot_txt = _get_cell_value_after_label(soup, ['ontester vysledek', 'ontester result'])
    ddm_txt = _get_cell_value_after_label(soup, [
        'nejvetsi ztrata na majetku od lokalniho maxima',   # CZ equity
        'maximal drawdown on equity from local high',       # EN (approximate/fallbacks)
        'maximal drawdown on equity'
    ])

    # Parse
    pf = _parse_first_number(pf_txt)
    tt = int(_parse_first_number(tt_txt) or 0) if tt_txt else None

    dd_pct = None
    if dd_txt:
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', dd_txt)
        if m:
            dd_pct = float(m.group(1).replace(',', '.'))
        else:
            dd_pct = _parse_first_number(dd_txt)

    net_profit = _parse_first_number(np_txt)
    ontester = _parse_first_number(ot_txt)
    max_dd_money = _parse_first_number(ddm_txt) if ddm_txt else None

    return {
        'ProfitFactor': pf,
        'TotalTrades': tt,
        'MaxDDPercent': dd_pct,
        'NetProfit': net_profit,
        'OnTester': ontester,
        'MaxDDMoney': max_dd_money,
        'encoding': enc,
    }
