"""
Nightly pipeline — Step 1: fetch market data for one ticker.
Usage: python3 scripts/nightly_fetch.py TICKER
Prints the analysis summary JSON and writes /tmp/summary_{ticker}.json + /tmp/raw_{ticker}.json.
"""
import sys, json
import yfinance as yf

ticker = sys.argv[1]
t = yf.Ticker(ticker)
info = t.info or {}
hist = t.history(period="5y")  # covers 1y and 5y trend context from one fetch
fi = t.fast_info
raw_news = t.news or []
try:
    calendar = t.calendar or {}
except Exception:
    calendar = {}

price = fi.last_price or info.get("currentPrice", 0) or 0
prev  = fi.previous_close or info.get("previousClose", price) or price
chg   = ((price - prev) / prev * 100) if prev else 0
hi52  = fi.year_high or info.get("fiftyTwoWeekHigh", 0) or 0
lo52  = fi.year_low  or info.get("fiftyTwoWeekLow",  0) or 0
rng   = ((price - lo52) / (hi52 - lo52) * 100) if (hi52 - lo52) > 0 else 50
ma50  = float(hist["Close"].rolling(50).mean().iloc[-1])  if len(hist) >= 50  else None
ma200 = float(hist["Close"].rolling(200).mean().iloc[-1]) if len(hist) >= 200 else None

delta = hist["Close"].diff()
gain  = delta.clip(lower=0).rolling(14).mean()
loss  = (-delta.clip(upper=0)).rolling(14).mean()
rsi   = float(100 - 100 / (1 + gain.iloc[-1] / loss.iloc[-1])) if loss.iloc[-1] != 0 else 50

news_titles = [n.get("content", {}).get("title") or n.get("title", "") for n in raw_news[:5]]
rec = (info.get("recommendationKey") or "hold").upper()
rec_count = info.get("numberOfAnalystOpinions")
tgt, tgt_hi, tgt_lo = info.get("targetMeanPrice"), info.get("targetHighPrice"), info.get("targetLowPrice")
ups = ((tgt - price) / price * 100) if tgt and price else None

# Fundamentals — same info dict already fetched above, no extra API call
pe_trailing, pe_forward = info.get("trailingPE"), info.get("forwardPE")
revenue_growth, earnings_growth = info.get("revenueGrowth"), info.get("earningsGrowth")
profit_margin, return_on_equity = info.get("profitMargins"), info.get("returnOnEquity")
debt_to_equity, free_cashflow = info.get("debtToEquity"), info.get("freeCashflow")
beta = info.get("beta")
short_float_pct, short_ratio = info.get("shortPercentOfFloat"), info.get("shortRatio")
inst_ownership_pct = info.get("heldPercentInstitutions")
insider_ownership_pct = info.get("heldPercentInsiders")
dividend_yield, market_cap = info.get("dividendYield"), info.get("marketCap")

try:
    edates = calendar.get("Earnings Date") or []
    edate = str(edates[0]) if edates else None
except Exception:
    edate = None

# 20-day support/resistance + classic pivot points
try:
    recent20 = hist["Close"].tail(20)
    support_20d    = round(float(recent20.min()), 2)
    resistance_20d = round(float(recent20.max()), 2)
    prev_h, prev_l, prev_c = float(hist["High"].iloc[-2]), float(hist["Low"].iloc[-2]), float(hist["Close"].iloc[-2])
    pivot  = round((prev_h + prev_l + prev_c) / 3, 2)
    piv_r1 = round(2 * pivot - prev_l, 2)
    piv_s1 = round(2 * pivot - prev_h, 2)
except Exception:
    support_20d = resistance_20d = pivot = piv_r1 = piv_s1 = None

# Sector & S&P 500 context — relative performance. ETFs have no GICS sector, so fall
# back to yfinance's fund "category" (e.g. "Precious Metals", "Large Blend") — without
# this, ~40% of a typical watchlist (anything that's an ETF, not a single stock) shows
# up with a blank sector tag everywhere it's surfaced.
sector, industry = info.get("sector", "") or "", info.get("industry", "") or ""
if not sector:
    sector = info.get("category", "") or ""
SECTOR_ETF_MAP = {
    "Technology": "XLK", "Healthcare": "XLV",
    "Financial Services": "XLF", "Financials": "XLF",
    "Consumer Cyclical": "XLY", "Consumer Defensive": "XLP",
    "Energy": "XLE", "Basic Materials": "XLB", "Industrials": "XLI",
    "Utilities": "XLU", "Real Estate": "XLRE",
    "Communication Services": "XLC",
}
# Semiconductor override — SOXX is more precise than XLK
sector_etf_ticker = "SOXX" if "semiconductor" in industry.lower() else SECTOR_ETF_MAP.get(sector, "SPY")

try:
    sp5 = yf.Ticker("^GSPC").history(period="5y")  # covers daily + 5y change below
    sp500_day_chg = round(((float(sp5["Close"].iloc[-1]) - float(sp5["Close"].iloc[-2])) / float(sp5["Close"].iloc[-2])) * 100, 2)
    sp500_5y_change = round(((float(sp5["Close"].iloc[-1]) - float(sp5["Close"].iloc[0])) / float(sp5["Close"].iloc[0])) * 100, 1)
except Exception:
    sp500_day_chg = sp500_5y_change = None

try:
    sect = yf.Ticker(sector_etf_ticker).history(period="25d")
    sector_day_chg = round(((float(sect["Close"].iloc[-1]) - float(sect["Close"].iloc[-2])) / float(sect["Close"].iloc[-2])) * 100, 2)
    relative_strength_1d = round(chg - sector_day_chg, 2)
except Exception:
    sector_day_chg = relative_strength_1d = None

# 52-week and 5-year return vs S&P — stored as percentage (e.g. 18.4 not 0.184)
_sp500_52w_raw = info.get("SandP52WeekChange")
sp500_52w_change = round(_sp500_52w_raw * 100, 1) if _sp500_52w_raw else None
_stock_52w_raw = info.get("52WeekChange")
stock_52w_change = round(_stock_52w_raw * 100, 1) if _stock_52w_raw else None

try:  # yfinance has no built-in 5y-change field the way it does for 52-week
    stock_5y_change = round(((float(hist["Close"].iloc[-1]) - float(hist["Close"].iloc[0])) / float(hist["Close"].iloc[0])) * 100, 1)
except Exception:
    stock_5y_change = None

# Finnhub cross-validation — price & analyst (secondary source)
import os
import requests

fh_price = fh_analyst = data_conflicts_str = None
fh_key = os.environ.get("FINNHUB_API_KEY", "")
if fh_key and fh_key not in ("placeholder", "test-key", ""):
    try:
        _fhq = requests.get(f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={fh_key}", timeout=5).json()
        fh_price = round(float(_fhq.get("c") or 0), 2) or None
    except Exception:
        pass
    try:
        _recs = requests.get(f"https://finnhub.io/api/v1/recommendation?symbol={ticker}&token={fh_key}", timeout=5).json()
        if _recs:
            _r = _recs[0]
            _tot = (_r.get("buy", 0) + _r.get("strongBuy", 0) + _r.get("hold", 0) + _r.get("sell", 0) + _r.get("strongSell", 0))
            if _tot:
                _buy_pct = (_r.get("buy", 0) + _r.get("strongBuy", 0)) / _tot
                fh_analyst = "STRONG_BUY" if _buy_pct > 0.6 else "BUY" if _buy_pct > 0.45 else "HOLD" if _buy_pct > 0.3 else "SELL"
    except Exception:
        pass
    _conflicts = []
    if fh_price and price and abs(price - fh_price) / price > 0.02:
        _conflicts.append(f"Price: yfinance={price} vs Finnhub={fh_price} ({abs(price - fh_price) / price * 100:.1f}% diff)")
    if fh_analyst and rec and fh_analyst.replace("STRONG_", "") != rec.replace("STRONG_", ""):
        _conflicts.append(f"Analyst: yfinance={rec} vs Finnhub={fh_analyst}")
    data_conflicts_str = "; ".join(_conflicts) if _conflicts else None

_summary = {
    "ticker": ticker, "price": round(price, 2), "change_pct": round(chg, 2),
    "hi52": round(hi52, 2), "lo52": round(lo52, 2), "range_pct": round(rng, 1),
    "ma50": round(ma50, 2) if ma50 else None,
    "ma200": round(ma200, 2) if ma200 else None,
    "rsi": round(rsi, 1), "analyst": rec, "analyst_count": rec_count,
    "upside_pct": round(ups, 1) if ups else None,
    "target_mean": tgt, "target_high": tgt_hi, "target_low": tgt_lo,
    "news": news_titles, "earnings_date": edate,
    "support_20d": support_20d, "resistance_20d": resistance_20d,
    "pivot": pivot, "piv_r1": piv_r1, "piv_s1": piv_s1,
    "sector": sector, "industry": industry,
    "sector_etf": sector_etf_ticker,
    "sp500_day_chg": sp500_day_chg,
    "sector_day_chg": sector_day_chg,
    "relative_strength_1d": relative_strength_1d,
    "sp500_52w_change": sp500_52w_change,
    "stock_52w_change": stock_52w_change,
    "sp500_5y_change": sp500_5y_change,
    "stock_5y_change": stock_5y_change,
    "pe_trailing": pe_trailing, "pe_forward": pe_forward,
    "revenue_growth": revenue_growth, "earnings_growth": earnings_growth,
    "profit_margin": profit_margin, "debt_to_equity": debt_to_equity,
    "free_cashflow": free_cashflow, "return_on_equity": return_on_equity,
    "beta": beta, "short_float_pct": short_float_pct, "short_ratio": short_ratio,
    "inst_ownership_pct": inst_ownership_pct, "insider_ownership_pct": insider_ownership_pct,
    "dividend_yield": dividend_yield, "market_cap": market_cap,
    "fh_price": fh_price, "fh_analyst": fh_analyst,
    "data_conflicts": data_conflicts_str,
}
print(json.dumps(_summary))
with open(f"/tmp/summary_{ticker}.json", "w") as f:
    json.dump(_summary, f)

# Serialize full raw data for the snapshot endpoint
try:
    hist_r = hist.reset_index()
    hist_r["Date"] = hist_r["Date"].astype(str)
    history_json = hist_r.to_json(orient="records")
except Exception:
    history_json = "[]"

try:
    cal_s = {}
    for k, v in (calendar or {}).items():
        cal_s[k] = [str(x) for x in v] if isinstance(v, list) else str(v)
    calendar_json = json.dumps(cal_s)
except Exception:
    calendar_json = "{}"

try:
    news_json = json.dumps(raw_news)
except Exception:
    news_json = "[]"

try:
    info_json = json.dumps(info)
except Exception:
    info_json = "{}"

with open(f"/tmp/raw_{ticker}.json", "w") as f:
    json.dump({
        "info_json": info_json,
        "history_json": history_json,
        "news_json": news_json,
        "calendar_json": calendar_json,
    }, f)
