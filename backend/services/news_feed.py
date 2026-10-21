"""
Company headlines for the nightly fetch (scripts/nightly_fetch.py) and for new-ticker
analysis (agents/yf_fetcher.py, agents/news_agent.py).

yfinance's Ticker.news started returning [] for every ticker on 2026-10-02 (1.5.2 and 1.7.0
alike), and the pipeline ran for three weeks with no news before anyone noticed — agents
wrote "no ticker-specific news was captured tonight" and moved on. Google News RSS is the
primary source: in a side-by-side on the watchlist it was the most on-topic (75% of
headlines name the company vs 53% for the old yfinance feed) and it also covers NSE/BSE
listings, which Yahoo has no news for. Yahoo search is the fallback (mutual funds, or
Google refusing a runner's IP).

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


def _yahoo(ticker: str) -> list[dict]:
    import yfinance as yf
    items = []
    for n in yf.Search(ticker, news_count=MAX_ITEMS, max_results=0).news or []:
        ts = n.get("providerPublishTime")
        items.append({
            "title": n.get("title", ""), "publisher": n.get("publisher", ""), "link": n.get("link", ""),
            "published": datetime.fromtimestamp(ts, timezone.utc).date().isoformat() if ts else None,
        })
    return items


def clean(items: list[dict]) -> list[dict]:
    """Drops non-news pages and the same wire story syndicated to several sites."""
    seen, out = set(), []
    for it in items:
        key = re.sub(r"[^a-z0-9]", "", it["title"].lower())
        if not key or key in seen or _NOT_NEWS.search(it["title"]):
            continue
        seen.add(key)
        out.append(it)
    return out[:MAX_ITEMS]


def fetch_headlines(ticker: str, name: str | None = None, quote_type: str | None = None) -> list[dict]:
    """Never raises — a news outage must not take down the fetch it's part of."""
    for source in (lambda: _google(search_query(ticker, name, quote_type)), lambda: _yahoo(ticker)):
        try:
            items = clean(source())
        except Exception:
            items = []
        if items:
            return items
    return []


def headline_text(item: dict) -> str:
    """'Apple gets a downgrade from Loop Capital (CNBC, 2026-10-20)' — source and date let
    the model weigh credibility and freshness."""
    meta = ", ".join(x for x in (item.get("publisher"), item.get("published")) if x)
    return f"{item['title']} ({meta})" if meta else item["title"]
