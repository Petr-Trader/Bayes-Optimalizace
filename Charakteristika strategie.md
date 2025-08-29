Co je „FX carry / momentum“ strategie

Momentum část = „kupuj sílu, prodávej slabost“.
Sleduješ trendy v měnových párech, typicky přes EMA (např. EMA50 vs EMA200, nebo prostě sklon EMA).

Pokud máš měnu, která je např. proti USD stabilně nad EMA → je považovaná za „silnou“.

Naopak pokud měna propadá pod EMA → „slabá“.

Carry část = když k tomu přidáš úrokový diferenciál (swap), dostaneš bonus.
– Např. dlouhodobě se obchoduje „carry trade“ tak, že se nakupuje měna s vyšším úrokem (AUD, NZD) a shortuje měna s nízkým úrokem (JPY, CHF).
– Pokud tvůj broker platí slušný swap, může to být edge navíc, i když trend stojí.

2️⃣ Jak to může fungovat prakticky

Vezmeš koš párů (třeba ty, co jsem napsal: EURUSD, GBPJPY, AUDUSD, USDCHF).

Na timeframe H4 nebo D1 vyhodnotíš trend pomocí EMA (např. EMA50 > EMA200 → trend nahoru).

Long tam, kde měna „síla“ > „slabost“.

Short obráceně.

Příklad:

Pokud GBPJPY má svíčky stabilně nad EMA a zároveň GBP je v jiných párech taky silná → kupuješ GBPJPY.

Pokud USDCHF padá a USD je slabý i jinde → short USDCHF.

3️⃣ Proč to dává smysl do miniportfolia

Nízká korelace vůči akciím (funguje v jiném prostředí než stock strategie).

Trendové chování měn je celkem stabilní (hlavně na D1).

Pokud přidáš „carry“ filtr (obchoduješ jen směry, kde swap pracuje pro tebe), máš extra výhodu.

Dá se dobře řídit riziko (typicky 1–2 % na obchod, SL pod/na EMA).

4️⃣ Jak to testovat

Udělej jednoduché pravidlo v AmiBrokeru nebo MT5:

Koupit: Close > EMA50 a EMA50 > EMA200.

Prodat: Close < EMA50 a EMA50 < EMA200.

Testovat na H4 a D1.

Vyhodnocovat Sharpe, MAR, drawdown.

Porovnat verzi s carry filtrem (obchody jen, když swap je kladný) vs. bez.

👉 Tahle strategie je fakt minimalistická, ale pro portfolio smysl dává – protože:

Akcie máš přes momentum/mean reversion,

Komodity můžeš mít přes trend-follow,

A měny takhle přes carry/momentum.