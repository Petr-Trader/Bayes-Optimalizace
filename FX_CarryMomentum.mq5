//+------------------------------------------------------------------+
//|                                               FX_CarryMomentum.mq5
//|                                   v1.00 (skeleton) – 2025-08-29
//|  Logika: EMA momentum (fast>slow = long, fast<slow = short)
//|          + volitelný carry filtr (swap musí být ve směru >= min)
//|  Multi-symbol EA (správa více FX párů z jednoho grafu přes OnTimer)
//+------------------------------------------------------------------+
#property strict
#property version   "1.00"
#property description "EMA momentum + volitelný carry (swap) filtr na H4/D1, multi-symbol"
#property description "Připraveno na optimalizaci v MT5 Strategy Testeru"

//--- obchodní knihovna
#include <Trade/Trade.mqh>
CTrade trade;

//========================= VSTUPY / PARAMETRY =======================
//--- univerzum
input string  InpSymbolsCSV         = "EURUSD,GBPJPY,AUDUSD,USDCHF,USDJPY,USDCAD,EURJPY,GBPUSD"; // seznam symbolů (čárkami oddělený)
input bool    InpUseMarketWatchOnly = true;         // pokud true: použije jen symboly z MarketWatch (CSV jako whitelist)
input bool    InpAutoSubscribe      = true;         // SymbolSelect(symbol,true) při startu

//--- timeframe & indikátory
input ENUM_TIMEFRAMES InpTF         = PERIOD_D1;    // signální TF (PERIOD_H4 / PERIOD_D1)
input int     InpEMAFast            = 50;           // rychlá EMA
input int     InpEMASlow            = 200;          // pomalá EMA
input int     InpATRPeriod          = 14;           // ATR pro SL/TP/trailing

//--- carry filtr (swap)
input bool    InpUseSwapFilter      = true;         // vynucovat kladný swap ve směru obchodu?
input double  InpMinSwap            = 0.0;          // minimální swap (v nativní jednotce symbolu), např. >=0.0

//--- risk management
input double  InpRiskPctPerTrade    = 1.0;          // % z Balance na jeden obchod (riziko do SL)
input double  InpATRmultSL          = 2.0;          // SL = ATR * násobek
input double  InpATRmultTP          = 4.0;          // TP = ATR * násobek (0 = bez TP)
input bool    InpUseTrailATR        = true;         // trailing SL podle ATR?
input double  InpATRmultTrail       = 2.0;          // trailing SL = ATR * násobek

//--- limity / filtry
input int     InpMaxGlobalPositions = 6;            // max. otevřených pozic celkem (magické číslo EA)
input int     InpMaxPerSymbol       = 1;            // max. pozic na jeden symbol (směr agregovaně)
input double  InpMaxSpreadPoints    = 30;           // max. spread (points) pro vstup
input bool    InpCloseOnTrendFlip   = true;         // zavírat při otočení trendu (fast < slow pro long apod.)
input bool    InpAvoidFridayClose   = true;         // v pátek neotevírat po určité hodině
input int     InpFridayHourCutoff   = 18;           // cutoff (server time)

//--- řízení exekuce
input int     InpTimerSeconds       = 60;           // jak často skenovat (OnTimer)
input ulong   InpMagic              = 26082025;     // magic
input int     InpSlippagePoints     = 5;            // slippage
input bool    InpEnableTrading      = true;         // master switch (backtest: zapnout)

//--- debug
input bool    InpVerbose            = true;

//========================= STRUKTURY / STAV =========================
struct SymbolCtx {
   string    sym;
   int       hEmaFast;
   int       hEmaSlow;
   int       hATR;
   datetime  lastBarSeen; // time z iTime(sym, TF, 0) naposledy zpracované svíčky
};
SymbolCtx  g_ctx[];

//========================= POMOCNÉ FUNKCE ===========================

string Trim(const string s) {
   string t = s;
   StringTrimLeft(t); StringTrimRight(t);
   return t;
}

void SplitCSV(const string csv, string &out[]) {
   StringSplit(csv, ',', out);
   for (int i=0;i<ArraySize(out);++i) out[i]=Trim(out[i]);
}

bool InMarketWatch(const string sym) {
   long vis = 0;
   return(SymbolInfoInteger(sym, SYMBOL_VISIBLE, vis) && vis==1);
}

bool SubscribeSymbol(const string sym) {
   if(!SymbolInfoInteger(sym, SYMBOL_SELECT)) {
      if(!SymbolSelect(sym, true)) return false;
   }
   return true;
}

bool BuildUniverse(string &univ[]) {
   string list[];
   SplitCSV(InpSymbolsCSV, list);

   // whitelisting přes CSV (pokud prázdné, bereme vše z MW)
   if(InpUseMarketWatchOnly) {
      // projít MarketWatch
      int total = SymbolsTotal(true);
      for(int i=0;i<total;++i){
         string s = SymbolName(i,true);
         // pokud CSV není prázdné, ber jen ty, které se v CSV vyskytují
         if(ArraySize(list)>0){
            bool ok=false;
            for(int k=0;k<ArraySize(list);++k)
               if(list[k]==s){ ok=true; break; }
            if(!ok) continue;
         }
         // Pro jistotu jen měnové páry
         long sect=0;
         if(SymbolInfoInteger(s, SYMBOL_TRADE_CALC_MODE, sect)) {
            // nic, čistě informativní
         }
         if(InMarketWatch(s)) {
            int idx = ArraySize(univ);
            ArrayResize(univ, idx+1);
            univ[idx]=s;
         }
      }
   } else {
      // použij CSV bez ohledu na MW
      for(int k=0;k<ArraySize(list);++k){
         string s = list[k];
         if(s=="") continue;
         int idx = ArraySize(univ);
         ArrayResize(univ, idx+1);
         univ[idx]=s;
      }
   }
   return (ArraySize(univ)>0);
}

bool MakeHandles(SymbolCtx &c) {
   if(InpAutoSubscribe && !SubscribeSymbol(c.sym)) return false;
   c.hEmaFast = iMA(c.sym, InpTF, InpEMAFast, 0, MODE_EMA, PRICE_CLOSE);
   c.hEmaSlow = iMA(c.sym, InpTF, InpEMASlow, 0, MODE_EMA, PRICE_CLOSE);
   c.hATR     = iATR(c.sym, InpTF, InpATRPeriod);
   if(c.hEmaFast==INVALID_HANDLE || c.hEmaSlow==INVALID_HANDLE || c.hATR==INVALID_HANDLE) return false;
   c.lastBarSeen = 0;
   return true;
}

void ReleaseHandles(SymbolCtx &c){
   if(c.hEmaFast!=INVALID_HANDLE) IndicatorRelease(c.hEmaFast);
   if(c.hEmaSlow!=INVALID_HANDLE) IndicatorRelease(c.hEmaSlow);
   if(c.hATR    !=INVALID_HANDLE) IndicatorRelease(c.hATR);
   c.hEmaFast=c.hEmaSlow=c.hATR=INVALID_HANDLE;
}

bool GetEMA(const SymbolCtx &c, double &fast, double &slow, int shift=1){
   double b1[], b2[];
   if(CopyBuffer(c.hEmaFast,0,shift,1,b1)!=1) return false;
   if(CopyBuffer(c.hEmaSlow,0,shift,1,b2)!=1) return false;
   fast=b1[0]; slow=b2[0];
   return true;
}

bool GetATR(const SymbolCtx &c, double &atr_val, int shift=1){
   double a[];
   if(CopyBuffer(c.hATR,0,shift,1,a)!=1) return false;
   atr_val=a[0];
   return true;
}

bool GetClose(const string sym, double &cl, int shift=1){
   double arr[];
   if(CopyClose(sym, InpTF, shift, 1, arr)!=1) return false;
   cl=arr[0];
   return true;
}

bool NewClosedBar(SymbolCtx &c){
   datetime t0 = iTime(c.sym, InpTF, 0);
   if(t0==0) return false;
   if(t0!=c.lastBarSeen){
      c.lastBarSeen=t0;
      return true;
   }
   return false;
}

double OnePointValuePerLot(const string sym){
   double tick_val = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE);
   double tick_sz  = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
   double point    = SymbolInfoDouble(sym, SYMBOL_POINT);
   if(tick_sz<=0) return 0.0;
   // hodnota 1 pointu na 1 lot
   return (tick_val / tick_sz) * point;
}

double NormalizeLots(const string sym, double lots){
   double minl = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double maxl = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   if(lots<minl) lots=minl;
   if(lots>maxl) lots=maxl;
   int steps = (int)MathFloor((lots - minl + 1e-10)/step);
   return (minl + steps*step);
}

int CountOpenByMagic(){
   int total=0;
   for(int i=0;i<PositionsTotal();++i){
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)==InpMagic) ++total;
   }
   return total;
}

int CountOpenForSymbol(const string sym){
   int total=0;
   for(int i=0;i<PositionsTotal();++i){
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      string psym = PositionGetString(POSITION_SYMBOL);
      if(psym==sym) ++total;
   }
   return total;
}

bool HasPositionDirection(const string sym, int dir /*+1 long, -1 short*/){
   for(int i=0;i<PositionsTotal();++i){
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL)!=sym) continue;
      long type = PositionGetInteger(POSITION_TYPE);
      if(dir>0 && type==POSITION_TYPE_BUY) return true;
      if(dir<0 && type==POSITION_TYPE_SELL) return true;
   }
   return false;
}

bool SpreadOK(const string sym){
   double point = SymbolInfoDouble(sym, SYMBOL_POINT);
   double bid   = SymbolInfoDouble(sym, SYMBOL_BID);
   double ask   = SymbolInfoDouble(sym, SYMBOL_ASK);
   if(point<=0 || bid==0 || ask==0) return false;
   double spread_pts = (ask - bid)/point;
   return (spread_pts <= InpMaxSpreadPoints);
}

bool FridayCutoff(){
   if(!InpAvoidFridayClose) return false;
   MqlDateTime dt; TimeCurrent(dt);
   if(dt.day_of_week==5 /*Friday*/ && dt.hour>=InpFridayHourCutoff) return true;
   return false;
}

bool CarryAllowed(const string sym, int dir){
   if(!InpUseSwapFilter) return true;
   double sw_long = SymbolInfoDouble(sym, SYMBOL_SWAP_LONG);
   double sw_short= SymbolInfoDouble(sym, SYMBOL_SWAP_SHORT);
   if(dir>0) return (sw_long >= InpMinSwap);
   else      return (sw_short>= InpMinSwap);
}

double CalcLotsByRisk(const string sym, double stop_distance_price){
   if(stop_distance_price<=0) return 0.0;
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_money= balance * (InpRiskPctPerTrade/100.0);
   double point_val = OnePointValuePerLot(sym);
   double point     = SymbolInfoDouble(sym, SYMBOL_POINT);
   if(point_val<=0 || point<=0) return 0.0;
   double stop_points = stop_distance_price / point;
   double risk_per_lot= stop_points * point_val;
   if(risk_per_lot<=0) return 0.0;
   double lots = risk_money / risk_per_lot;
   return NormalizeLots(sym, lots);
}

bool CloseOnTrendFlip(const SymbolCtx &c){
   // uzavře pozice, pokud se trend otočil proti
   double fast, slow, close1;
   if(!GetEMA(c, fast, slow, 1)) return false;
   if(!GetClose(c.sym, close1, 1)) return false;

   for(int i=PositionsTotal()-1;i>=0;--i){
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL)!=c.sym) continue;

      long   type  = PositionGetInteger(POSITION_TYPE);
      double price = PositionGetDouble(POSITION_PRICE_OPEN);

      if(type==POSITION_TYPE_BUY){
         if(fast<slow || close1<slow){
            if(InpVerbose) Print("Close BUY (flip) ", c.sym);
            trade.PositionClose(c.sym);
         }
      } else if(type==POSITION_TYPE_SELL){
         if(fast>slow || close1>slow){
            if(InpVerbose) Print("Close SELL (flip) ", c.sym);
            trade.PositionClose(c.sym);
         }
      }
   }
   return true;
}

bool TrailPositionsATR(const SymbolCtx &c){
   if(!InpUseTrailATR) return true;
   double atr;
   if(!GetATR(c, atr, 1)) return false;
   double point = SymbolInfoDouble(c.sym, SYMBOL_POINT);
   if(point<=0) return false;

   for(int i=0;i<PositionsTotal();++i){
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL)!=c.sym) continue;

      long   type     = PositionGetInteger(POSITION_TYPE);
      double price    = (type==POSITION_TYPE_BUY) ? SymbolInfoDouble(c.sym, SYMBOL_BID)
                                                  : SymbolInfoDouble(c.sym, SYMBOL_ASK);
      double sl       = PositionGetDouble(POSITION_SL);

      double trail_dist = InpATRmultTrail * atr;
      double new_sl     = sl;

      if(type==POSITION_TYPE_BUY){
         double candidate = price - trail_dist;
         if(sl==0 || candidate>sl) new_sl = candidate;
      }else{
         double candidate = price + trail_dist;
         if(sl==0 || candidate<sl) new_sl = candidate;
      }

      // nepřekládat nad vstup u BUY / pod vstup u SELL dříve než BE?
      // (základní verze to neřeší)
      if(new_sl != sl){
         trade.PositionModify(c.sym, new_sl, PositionGetDouble(POSITION_TP));
         if(InpVerbose) Print("Trail SL ", c.sym, " -> ", DoubleToString(new_sl, (int)SymbolInfoInteger(c.sym, SYMBOL_DIGITS)));
      }
   }
   return true;
}

bool EnterIfSignal(SymbolCtx &c){
   if(FridayCutoff()) return false;
   if(CountOpenByMagic()>=InpMaxGlobalPositions) return false;
   if(CountOpenForSymbol(c.sym)>=InpMaxPerSymbol) return false;
   if(!SpreadOK(c.sym)) return false;

   double fast, slow, close1, atr;
   if(!GetEMA(c, fast, slow, 1)) return false;
   if(!GetClose(c.sym, close1, 1)) return false;
   if(!GetATR(c, atr, 1)) return false;

   // momentum pravidla
   bool longSig  = (close1>fast && fast>slow);
   bool shortSig = (close1<fast && fast<slow);

   // price, point
   double point = SymbolInfoDouble(c.sym, SYMBOL_POINT);
   double ask   = SymbolInfoDouble(c.sym, SYMBOL_ASK);
   double bid   = SymbolInfoDouble(c.sym, SYMBOL_BID);
   if(point<=0 || ask==0 || bid==0) return false;

   // SL/TP v ceně (ATR je v cenových jednotkách)
   double sl_dist = InpATRmultSL * atr;
   double tp_dist = (InpATRmultTP>0 ? InpATRmultTP * atr : 0.0);

   // LONG
   if(longSig && !HasPositionDirection(c.sym, +1) && CarryAllowed(c.sym, +1)){
      double sl = ask - sl_dist;
      double tp = (tp_dist>0 ? ask + tp_dist : 0.0);
      double lots = CalcLotsByRisk(c.sym, sl_dist);
      if(lots>0 && InpEnableTrading){
         trade.SetExpertMagicNumber(InpMagic);
         trade.SetDeviationInPoints(InpSlippagePoints);
         bool ok = trade.Buy(lots, c.sym, ask, sl, tp, "EMAcarry L");
         if(InpVerbose) Print("BUY ", c.sym, " lots=",lots," sl=",sl," tp=",tp," ok=",ok);
      }
   }

   // SHORT
   if(shortSig && !HasPositionDirection(c.sym, -1) && CarryAllowed(c.sym, -1)){
      double sl = bid + sl_dist;
      double tp = (tp_dist>0 ? bid - tp_dist : 0.0);
      double lots = CalcLotsByRisk(c.sym, sl_dist);
      if(lots>0 && InpEnableTrading){
         trade.SetExpertMagicNumber(InpMagic);
         trade.SetDeviationInPoints(InpSlippagePoints);
         bool ok = trade.Sell(lots, c.sym, bid, sl, tp, "EMAcarry S");
         if(InpVerbose) Print("SELL ", c.sym, " lots=",lots," sl=",sl," tp=",tp," ok=",ok);
      }
   }
   return true;
}

//============================= MT5 HOOKS ============================

int OnInit()
{
   if(InpVerbose) Print("Init FX_CarryMomentum v1.00");
   trade.SetExpertMagicNumber(InpMagic);

   string univ[];
   if(!BuildUniverse(univ)) {
      Print("❌ Universe je prázdné. Zkontroluj InpSymbolsCSV / MarketWatch.");
      return(INIT_FAILED);
   }

   ArrayResize(g_ctx, ArraySize(univ));
   for(int i=0;i<ArraySize(univ);++i){
      g_ctx[i].sym = univ[i];
      if(!MakeHandles(g_ctx[i])){
         Print("❌ Indikátorové handle selhaly pro ", g_ctx[i].sym);
         return(INIT_FAILED);
      }
      if(InpVerbose) Print("✔ Symbol připraven: ", g_ctx[i].sym);
   }

   EventSetTimer(InpTimerSeconds);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   for(int i=0;i<ArraySize(g_ctx);++i) ReleaseHandles(g_ctx[i]);
   EventKillTimer();
}

void OnTimer()
{
   // 1) trailing + případné zavírání na flip
   for(int i=0;i<ArraySize(g_ctx);++i){
      TrailPositionsATR(g_ctx[i]);
      if(InpCloseOnTrendFlip) CloseOnTrendFlip(g_ctx[i]);
   }

   // 2) sken vstupů **na nové zavřené svíčce**
   for(int i=0;i<ArraySize(g_ctx);++i){
      if(NewClosedBar(g_ctx[i])) {
         EnterIfSignal(g_ctx[i]);
      }
   }
}

void OnTick()
{
   // nic kritického – vše běží na OnTimer (robustní pro multi-symbol)
   // případně sem lze dát rychlé trailingy, pokud chceš častěji
}
