"""
Company headlines for the nightly fetch (scripts/nightly_fetch.py) and for new-ticker
analysis (agents/yf_fetcher.py, agents/news_agent.py).

yfinance's Ticker.news started returning [] for every ticker on 2026-10-02 (1.5.2 and 1.7.0
alike), and the pipeline ran for three weeks with no news before anyone noticed — agents
wrote "no ticker-specific news was captured tonight" and moved on.

Both sources are always fetched and merged. Google News RSS is the most on-topic (75% of
headlines name the company vs 53% for the old yfinance feed) and also covers NSE/BSE
listings, which Yahoo has no news for. Yahoo search still adds ~3.6 company stories per
ticker that Google's list misses (earnings-call write-ups, analyst notes), and either
source keeps news flowing if the other goes down.

Items are flat dicts — {title, publisher, link, published} — the shape news_agent already
reads from market_data_cache.news_json.
"""
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

MAX_ITEMS = 8
_GOOGLE_RSS = "https://news.google.com/rss/search"
_NAME_SUFFIXES = {
    "inc", "corp", "corporation", "co", "ltd", "limited", "plc", "the", "class", "holdings",
    "group", "company", "sa", "nv", "ag", "a/s", "se", "llc", "lp",
}
# Quote/landing pages and price-prediction spam — headlines with no news in them.
_NOT_NEWS = re.compile(r"stock price, news, quote|share price prediction|stock price prediction|stock quote", re.I)


def company_query_name(name: str) -> str:
    words = [w.strip(".,") for w in (name or "").replace(",", " ").split()]
    kept = [w for w in words if w and w.lower() not in _NAME_SUFFIXES]
    return " ".join(kept) or (name or "").strip()


def search_query(ticker: str, name: str | None, quote_type: str | None) -> str:
    if quote_type == "ETF":
        return f"{ticker} ETF when:3d"
    if name:
        return f'"{company_query_name(name)}" stock when:3d'
    return f"{ticker} stock when:3d"


def _google(query: str) -> list[dict]:
    r = requests.get(_GOOGLE_RSS, params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}, timeout=10)
    r.raise_for_status()
    items = []
    for it in ET.fromstring(r.content).findall(".//item"):
        publisher = (it.findtext("source") or "").strip()
        title = (it.findtext("title") or "").strip()
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(publisher) - 3].rstrip()
        try:
            published = parsedate_to_datetime(it.findtext("pubDate")).date().isoformat()
        except (TypeError, ValueError):
            published = None
        items.append({"title": title, "publisher": publisher, "link": it.findtext("link") or "", "published": published})
    return items


def names_company(title: str, ticker: str, name: str | None) -> bool:
    """The ticker as an uppercase word, or the first word of the company name."""
    first = company_query_name(name or "").split()[:1]
    return bool(re.search(rf"\b{re.escape(ticker)}\b", title)
                or (first and len(first[0]) >= 3 and re.search(rf"\b{re.escape(first[0])}", title, re.I)))


def _yahoo(ticker: str, name: str | None) -> list[dict]:
    """About half of Yahoo's search news is market-wide, and its relatedTickers tag alone is
    loose ("Qualcomm is cutting jobs" comes back tagged AAPL) — an item must be tagged with
    the ticker AND name the company in its headline."""
    import yfinance as yf
    items = []
    for n in yf.Search(ticker, news_count=MAX_ITEMS, max_results=0).news or []:
        if ticker not in (n.get("relatedTickers") or []) or not names_company(n.get("title", ""), ticker, name):
            continue
        ts = n.get("providerPublishTime")
        items.append({
            "title": n.get("title", ""), "publisher": n.get("publisher", ""), "link": n.get("link", ""),
            "published": datetime.fromtimestamp(ts, timezone.utc).date().isoformat() if ts else None,
        })
    return items


def clean(items: list[dict]) -> list[dict]:
    """Drops non-news pages and the same story syndicated to several sites (first copy wins)."""
    seen, out = set(), []
    for it in items:
        key = re.sub(r"[^a-z0-9]", "", it["title"].lower())
        if not key or key in seen or _NOT_NEWS.search(it["title"]):
            continue
        seen.add(key)
        out.append(it)
    return out


def _safe(fetch) -> list[dict]:
    try:
        return fetch()
    except Exception:
        return []


def fetch_headlines(ticker: str, name: str | None = None, quote_type: str | None = None) -> list[dict]:
    """Google's top stories plus the Yahoo ones it missed, newest first (undated last).
    Never raises — a news outage must not take down the fetch it's part of."""
    google = clean(_safe(lambda: _google(search_query(ticker, name, quote_type))))[:MAX_ITEMS]
    merged = clean(google + _safe(lambda: _yahoo(ticker, name)))
    merged.sort(key=lambda it: it["published"] or "", reverse=True)  # stable: Google first within a day
    return merged[:MAX_ITEMS]


def headline_text(item: dict) -> str:
    """'Apple gets a downgrade from Loop Capital (CNBC, 2026-10-20)' — source and date let
    the model weigh credibility and freshness."""
    meta = ", ".join(x for x in (item.get("publisher"), item.get("published")) if x)
    return f"{item['title']} ({meta})" if meta else item["title"]
