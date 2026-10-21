"""
services/news_feed.py replaced yfinance's Ticker.news, which returned [] for every ticker
from 2026-10-02 — three weeks of nightly verdicts and new-ticker analyses ran with no news.
"""
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services import news_feed as nf

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item><title>Apple gets a downgrade from Loop Capital on fears of slow iPhone sales - CNBC</title>
  <link>https://news.google.com/rss/articles/a1</link><pubDate>Tue, 20 Oct 2026 14:05:00 GMT</pubDate>
  <source url="https://www.cnbc.com">CNBC</source></item>
<item><title>Bigbearai Holdings stock hits 52-week low at 2.11 USD By Investing.com - Investing.com UK</title>
  <link>https://news.google.com/rss/articles/a2</link><pubDate>Mon, 19 Oct 2026 09:00:00 GMT</pubDate>
  <source url="https://uk.investing.com">Investing.com UK</source></item>
<item><title>Bigbearai Holdings stock hits 52-week low at 2.11 USD By Investing.com - Investing.com South Africa</title>
  <link>https://news.google.com/rss/articles/a3</link><pubDate>Mon, 19 Oct 2026 09:01:00 GMT</pubDate>
  <source url="https://za.investing.com">Investing.com South Africa</source></item>
<item><title>Redwire Corporation (RDW) stock price, news, quote and history - Yahoo Finance UK</title>
  <link>https://news.google.com/rss/articles/a4</link><pubDate>Mon, 19 Oct 2026 08:00:00 GMT</pubDate>
  <source url="https://uk.finance.yahoo.com">Yahoo Finance UK</source></item>
<item><title>TCS Share Price Prediction for Wednesday: 21 Oct 2026 - Univest</title>
  <link>https://news.google.com/rss/articles/a5</link><pubDate>Mon, 19 Oct 2026 07:00:00 GMT</pubDate>
  <source url="https://univest.in">Univest</source></item>
<item><title>Prediction: Apple's Stock Is Due for a Reality Check on Nov. 2 - The Motley Fool</title>
  <link>https://news.google.com/rss/articles/a6</link><pubDate>not a date</pubDate>
  <source url="https://www.fool.com">The Motley Fool</source></item>
</channel></rss>"""


def _resp(content=RSS):
    return MagicMock(content=content, raise_for_status=lambda: None)


class TestQuery:
    @pytest.mark.parametrize("name,expected", [
        ("Apple Inc.", "Apple"), ("BigBear.ai Holdings, Inc.", "BigBear.ai"),
        ("The Home Depot, Inc.", "Home Depot"), ("Novo Nordisk A/S", "Novo Nordisk"),
        ("Taiwan Semiconductor Manufacturing Company Limited", "Taiwan Semiconductor Manufacturing"),
    ])
    def test_company_name_is_stripped_to_what_headlines_use(self, name, expected):
        assert nf.company_query_name(name) == expected

    def test_stocks_by_name_etfs_by_ticker(self):
        assert nf.search_query("AAPL", "Apple Inc.", "EQUITY") == '"Apple" stock when:3d'
        assert nf.search_query("SOXX", "iShares Semiconductor ETF", "ETF") == "SOXX ETF when:3d"
        assert nf.search_query("XYZ", None, None) == "XYZ stock when:3d"


class TestGoogle:
    def test_parses_and_cleans_the_feed(self):
        with patch.object(nf.requests, "get", return_value=_resp()):
            items = nf.fetch_headlines("AAPL", "Apple Inc.", "EQUITY")
        assert [i["title"] for i in items] == [
            "Apple gets a downgrade from Loop Capital on fears of slow iPhone sales",
            "Bigbearai Holdings stock hits 52-week low at 2.11 USD By Investing.com",  # syndicated copy dropped
            "Prediction: Apple's Stock Is Due for a Reality Check on Nov. 2",  # "Prediction:" is an article, kept
        ]
        assert items[0] == {"title": items[0]["title"], "publisher": "CNBC",
                            "link": "https://news.google.com/rss/articles/a1", "published": "2026-10-20"}
        assert items[2]["published"] is None

    def test_caps_the_number_of_items(self):
        many = b"<rss><channel>" + b"".join(
            f"<item><title>Story {i} - Pub</title><source>Pub</source></item>".encode() for i in range(20)
        ) + b"</channel></rss>"
        with patch.object(nf.requests, "get", return_value=_resp(many)):
            assert len(nf.fetch_headlines("AAPL", "Apple Inc.")) == nf.MAX_ITEMS


class TestFallback:
    YAHOO = [{"title": "Fund flows rise", "publisher": "Reuters", "link": "https://y/1", "providerPublishTime": 1792543020}]

    def test_yahoo_used_when_google_has_nothing(self):
        empty = _resp(b"<rss><channel></channel></rss>")
        with patch.object(nf.requests, "get", return_value=empty), \
             patch("yfinance.Search", return_value=SimpleNamespace(news=self.YAHOO)):
            items = nf.fetch_headlines("VITSX", "Vanguard Total Stock Market", "MUTUALFUND")
        assert items == [{"title": "Fund flows rise", "publisher": "Reuters", "link": "https://y/1", "published": "2026-10-21"}]

    def test_yahoo_used_when_google_errors(self):
        with patch.object(nf.requests, "get", side_effect=nf.requests.ConnectionError("blocked")), \
             patch("yfinance.Search", return_value=SimpleNamespace(news=self.YAHOO)):
            assert nf.fetch_headlines("AAPL", "Apple Inc.")[0]["publisher"] == "Reuters"

    def test_never_raises_when_every_source_fails(self):
        with patch.object(nf.requests, "get", side_effect=RuntimeError("down")), \
             patch("yfinance.Search", side_effect=RuntimeError("down")):
            assert nf.fetch_headlines("AAPL", "Apple Inc.") == []


def test_headline_text_carries_source_and_date():
    assert nf.headline_text({"title": "Downgrade", "publisher": "CNBC", "published": "2026-10-20"}) == "Downgrade (CNBC, 2026-10-20)"
    assert nf.headline_text({"title": "Downgrade", "publisher": "", "published": None}) == "Downgrade"


class TestCallSites:
    def test_nightly_fetch_uses_the_feed_not_ticker_news(self):
        src = (Path(__file__).resolve().parents[2] / "scripts" / "nightly_fetch.py").read_text()
        assert "fetch_headlines(" in src and "headline_text(" in src
        assert "t.news" not in src

    def test_new_ticker_fetch_stores_feed_items(self):
        from agents import yf_fetcher
        fake = MagicMock(info={"regularMarketPrice": 10.0, "longName": "Apple Inc.", "quoteType": "EQUITY"})
        with patch.object(yf_fetcher.yf, "Ticker", return_value=fake), \
             patch.object(yf_fetcher, "fetch_headlines", return_value=[{"title": "T", "publisher": "P", "link": "L", "published": None}]) as fh:
            data = yf_fetcher._fetch_from_api("AAPL", retries=1)
        fh.assert_called_once_with("AAPL", "Apple Inc.", "EQUITY")
        assert data.news[0]["title"] == "T"

    def test_news_agent_fetches_live_when_the_cache_row_is_empty(self):
        from agents import news_agent
        cached = SimpleNamespace(news=[], info={"longName": "Apple Inc.", "quoteType": "EQUITY"})
        with patch.object(news_agent, "fetch_headlines", return_value=[{"title": "Downgrade", "publisher": "CNBC", "link": "https://c/1"}]) as fh:
            lines = news_agent._yf_news("AAPL", cached)
        fh.assert_called_once_with("AAPL", "Apple Inc.", "EQUITY")
        assert lines == ["Downgrade [CNBC] — https://c/1"]

    def test_news_agent_drops_google_redirect_links_from_user_facing_summary_input(self):
        from agents import news_agent
        cached = SimpleNamespace(news=[{"title": "Downgrade", "publisher": "CNBC", "link": "https://news.google.com/rss/articles/CBMi" + "x" * 200}], info={})
        assert news_agent._yf_news("AAPL", cached) == ["Downgrade [CNBC]"]

    def test_news_agent_reads_feed_items_from_the_cache(self):
        from agents import news_agent
        cached = SimpleNamespace(news=[{"title": "Downgrade", "publisher": "CNBC", "link": "https://c/1", "published": "2026-10-20"}], info={})
        with patch.object(news_agent, "fetch_headlines") as fh:
            assert news_agent._yf_news("AAPL", cached) == ["Downgrade [CNBC] — https://c/1"]
        fh.assert_not_called()


def test_data_quality_reports_tickers_without_news(client: TestClient, db_session):
    """A news outage stores "[]", not NULL — the sentinel must see it anyway."""
    import os
    from models import MarketDataCache, StockAnalysis
    os.environ["ADMIN_SECRET"] = "dq-news-secret"
    today = date.today()
    for t, news in (("NFQA", [{"title": "x"}]), ("NFQB", []), ("NFQC", None), ("NFQD", [])):
        db_session.merge(MarketDataCache(ticker=t, cache_date=today, info_json="{}",
                                         news_json=json.dumps(news) if news is not None else None))
        db_session.add(StockAnalysis(ticker=t, analysis_date=today, verdict="WATCH"))
    db_session.commit()

    body = client.get("/jobs/admin/data-quality", params={"x_admin_secret": "dq-news-secret"}).json()
    rows = db_session.query(MarketDataCache.news_json).filter(MarketDataCache.cache_date == today).all()  # other tests add rows too
    expected = round(100 * sum(1 for (n,) in rows if n in (None, "", "[]", "null")) / len(rows), 1)
    assert body["null_rates_by_date"][today.isoformat()]["null_pct"]["news"] == expected > 0
