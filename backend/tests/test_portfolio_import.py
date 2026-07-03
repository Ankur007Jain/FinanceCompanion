"""
Tests for the portfolio import feature:
  - _parse_pdf / _parse_csv (unit tests — pure parsing logic, no DB)
  - POST /portfolio/import/preview (end-to-end via TestClient)
  - POST /portfolio/import/apply  (end-to-end via TestClient)
"""
import io
import uuid
from unittest.mock import patch

import pytest

from routers.portfolio import _parse_csv
from schemas import ImportPreviewItem


# ── helpers ──────────────────────────────────────────────────────────────────

def _mock_user(email: str = "import@example.com"):
    return patch(
        "routers.auth.id_token.verify_oauth2_token",
        return_value={"email": email, "name": "Test"},
    )


def _uid():
    return f"imp-{uuid.uuid4().hex[:8]}@example.com"


def _csv_bytes(header: str, *rows: str) -> bytes:
    lines = [header] + list(rows)
    return "\n".join(lines).encode()


def _add_watchlist(client, email: str, ticker: str):
    with _mock_user(email), patch("routers.watchlist._detect_leveraged", return_value=False):
        client.post(
            "/watchlist",
            params={"id_token": "tok"},
            json={"ticker": ticker, "company_name": "Test Co"},
        )


# ══════════════════════════════════════════════════════════════════════════════
# Unit — _parse_csv
# ══════════════════════════════════════════════════════════════════════════════

class TestParseCsv:
    def test_robinhood_style_with_cost(self):
        content = _csv_bytes(
            "Symbol,Quantity,Average Cost",
            "AAPL,13.291901,185.50",
            "VOO,5.0,430.00",
        )
        result = _parse_csv(content)
        assert len(result) == 2
        tickers = {r.ticker for r in result}
        assert tickers == {"AAPL", "VOO"}
        aapl = next(r for r in result if r.ticker == "AAPL")
        assert aapl.shares == pytest.approx(13.291901)
        assert aapl.avg_cost == pytest.approx(185.50)

    def test_unrecognised_cost_column_gives_none(self):
        # "Acquisition Price" is not in _COST_CANDIDATES — avg_cost should be None
        content = _csv_bytes(
            "Symbol,Quantity,Acquisition Price",
            "TSLA,2.0,250.0",
        )
        result = _parse_csv(content)
        assert len(result) == 1
        assert result[0].ticker == "TSLA"
        assert result[0].avg_cost is None

    def test_average_cost_basis_column_recognised(self):
        # "Average Cost Basis" is in _COST_CANDIDATES — should be parsed
        content = _csv_bytes(
            "Symbol,Quantity,Average Cost Basis",
            "TSLA,2.0,250.0",
        )
        result = _parse_csv(content)
        assert result[0].avg_cost == pytest.approx(250.0)

    def test_shares_column_alias(self):
        content = _csv_bytes(
            "Ticker,Shares,Cost Per Share",
            "MSFT,10.0,380.0",
        )
        result = _parse_csv(content)
        assert result[0].ticker == "MSFT"
        assert result[0].shares == pytest.approx(10.0)
        assert result[0].avg_cost == pytest.approx(380.0)

    def test_fractional_shares_preserved(self):
        content = _csv_bytes(
            "Symbol,Quantity",
            "NFLX,0.123456",
        )
        result = _parse_csv(content)
        assert result[0].shares == pytest.approx(0.123456)

    def test_skips_zero_share_rows(self):
        content = _csv_bytes(
            "Symbol,Quantity",
            "AAPL,0",
            "MSFT,5.0",
        )
        result = _parse_csv(content)
        assert len(result) == 1
        assert result[0].ticker == "MSFT"

    def test_skips_negative_share_rows(self):
        content = _csv_bytes(
            "Symbol,Quantity",
            "AAPL,-3.0",
            "MSFT,5.0",
        )
        result = _parse_csv(content)
        assert len(result) == 1
        assert result[0].ticker == "MSFT"

    def test_skips_options_rows(self):
        content = _csv_bytes(
            "Symbol,Quantity",
            "AAPL 200C 01/17,1.0",
            "MSFT,5.0",
        )
        result = _parse_csv(content)
        assert len(result) == 1
        assert result[0].ticker == "MSFT"

    def test_skips_too_long_tickers(self):
        content = _csv_bytes(
            "Symbol,Quantity",
            "TOOLONGX,10.0",
            "AAPL,5.0",
        )
        result = _parse_csv(content)
        assert len(result) == 1
        assert result[0].ticker == "AAPL"

    def test_deduplicates_tickers(self):
        content = _csv_bytes(
            "Symbol,Quantity",
            "AAPL,5.0",
            "AAPL,3.0",
        )
        result = _parse_csv(content)
        assert len(result) == 1

    def test_empty_csv_returns_empty_list(self):
        result = _parse_csv(b"Symbol,Quantity\n")
        assert result == []

    def test_raises_on_missing_ticker_column(self):
        content = _csv_bytes(
            "Price,Quantity",
            "100.0,5",
        )
        with pytest.raises(ValueError, match="Could not find ticker"):
            _parse_csv(content)

    def test_raises_on_missing_shares_column(self):
        content = _csv_bytes(
            "Symbol,Price",
            "AAPL,150.0",
        )
        with pytest.raises(ValueError, match="Could not find ticker"):
            _parse_csv(content)

    def test_header_is_case_insensitive(self):
        content = _csv_bytes(
            "SYMBOL,QUANTITY,AVERAGE COST",
            "AAPL,5.0,180.0",
        )
        result = _parse_csv(content)
        assert len(result) == 1
        assert result[0].ticker == "AAPL"

    def test_comma_in_shares_number_stripped(self):
        content = _csv_bytes(
            "Symbol,Quantity",
            "BRK.B,\"1,000\"",
        )
        result = _parse_csv(content)
        assert result[0].shares == pytest.approx(1000.0)

    def test_bom_prefix_stripped(self):
        # UTF-8 BOM sometimes present in Excel exports
        content = b"\xef\xbb\xbfSymbol,Quantity\nAAPL,5.0\n"
        result = _parse_csv(content)
        assert result[0].ticker == "AAPL"

    def test_ticker_normalised_to_uppercase(self):
        content = _csv_bytes(
            "Symbol,Quantity",
            "aapl,5.0",
        )
        result = _parse_csv(content)
        assert result[0].ticker == "AAPL"

    def test_dollar_sign_stripped_from_cost(self):
        content = _csv_bytes(
            "Symbol,Quantity,Average Cost",
            "AAPL,5.0,$185.50",
        )
        result = _parse_csv(content)
        assert result[0].avg_cost == pytest.approx(185.50)


# ══════════════════════════════════════════════════════════════════════════════
# Unit — _parse_pdf (regex logic on synthetic text)
# ══════════════════════════════════════════════════════════════════════════════

class TestParsePdfRegex:
    """Test the PDF regex by injecting a synthetic text into the pattern directly."""

    def _run(self, text: str) -> list[ImportPreviewItem]:
        import re
        pattern = re.compile(
            r'\b([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\s+(?:Margin|Cash)\s+([\d,]+(?:\.\d+)?)\s+\$'
        )
        seen: dict[str, float] = {}
        for m in pattern.finditer(text):
            ticker = m.group(1)
            shares = float(m.group(2).replace(",", ""))
            if ticker not in seen and shares > 0:
                seen[ticker] = shares
        return [ImportPreviewItem(ticker=t, shares=s) for t, s in seen.items()]

    def test_margin_position_parsed(self):
        text = "AAPL Margin 13.291901 $312.06"
        result = self._run(text)
        assert len(result) == 1
        assert result[0].ticker == "AAPL"
        assert result[0].shares == pytest.approx(13.291901)

    def test_cash_position_parsed(self):
        text = "VOO Cash 15.430716 $430.00"
        result = self._run(text)
        assert len(result) == 1
        assert result[0].ticker == "VOO"

    def test_multiple_positions_parsed(self):
        text = (
            "AAPL Margin 13.291901 $312.06\n"
            "VOO Cash 15.430716 $430.00\n"
            "MSFT Margin 5.0 $380.00\n"
        )
        result = self._run(text)
        assert len(result) == 3

    def test_duplicate_ticker_only_first_kept(self):
        text = (
            "AAPL Margin 10.0 $150.0\n"
            "AAPL Margin 5.0 $160.0\n"
        )
        result = self._run(text)
        assert len(result) == 1
        assert result[0].shares == pytest.approx(10.0)

    def test_zero_shares_skipped(self):
        text = "AAPL Margin 0 $150.0"
        result = self._run(text)
        assert result == []

    def test_dot_ticker_parsed(self):
        text = "BRK.B Margin 20.0 $350.00"
        result = self._run(text)
        assert result[0].ticker == "BRK.B"

    def test_lowercase_margin_not_matched(self):
        text = "AAPL margin 10.0 $150.0"
        result = self._run(text)
        assert result == []


# ══════════════════════════════════════════════════════════════════════════════
# Integration — POST /portfolio/import/preview
# ══════════════════════════════════════════════════════════════════════════════

class TestImportPreview:
    def _upload(self, client, email: str, content: bytes, filename: str):
        with _mock_user(email):
            return client.post(
                "/portfolio/import/preview",
                params={"id_token": "tok"},
                files={"file": (filename, io.BytesIO(content), "text/csv")},
            )

    def test_csv_preview_returns_positions(self, client):
        email = _uid()
        content = _csv_bytes(
            "Symbol,Quantity,Average Cost",
            "AAPL,13.291901,185.50",
            "VOO,15.430716,430.00",
        )
        r = self._upload(client, email, content, "holdings.csv")
        assert r.status_code == 200
        data = r.json()
        assert "positions" in data
        assert len(data["positions"]) == 2

    def test_csv_preview_position_shape(self, client):
        email = _uid()
        content = _csv_bytes(
            "Symbol,Quantity,Average Cost",
            "AAPL,5.0,185.0",
        )
        r = self._upload(client, email, content, "h.csv")
        pos = r.json()["positions"][0]
        assert pos["ticker"] == "AAPL"
        assert pos["shares"] == pytest.approx(5.0)
        assert pos["avg_cost"] == pytest.approx(185.0)

    def test_preview_does_not_save_to_db(self, client):
        email = _uid()
        content = _csv_bytes(
            "Symbol,Quantity",
            "PREVIEWONLY,10.0",
        )
        self._upload(client, email, content, "h.csv")
        # Digest should have no items (ticker was never added to watchlist or portfolio)
        with _mock_user(email):
            r = client.get("/analysis/digest", params={"id_token": "tok"})
        assert r.json() == []

    def test_preview_unauthenticated_returns_401(self, client):
        content = _csv_bytes("Symbol,Quantity", "AAPL,5")
        r = client.post(
            "/portfolio/import/preview",
            params={"id_token": "bad-token"},
            files={"file": ("h.csv", io.BytesIO(content), "text/csv")},
        )
        assert r.status_code == 401

    def test_preview_unparseable_file_returns_422(self, client):
        email = _uid()
        # Garbled content with no recognizable columns
        content = b"junk;no;headers\n1;2;3\n"
        with _mock_user(email):
            r = client.post(
                "/portfolio/import/preview",
                params={"id_token": "tok"},
                files={"file": ("bad.csv", io.BytesIO(content), "text/csv")},
            )
        assert r.status_code == 422

    def test_preview_empty_csv_returns_422(self, client):
        email = _uid()
        content = _csv_bytes("Symbol,Quantity")  # header only, no rows
        r = self._upload(client, email, content, "empty.csv")
        assert r.status_code == 422

    def test_preview_filters_zero_share_rows(self, client):
        email = _uid()
        content = _csv_bytes(
            "Symbol,Quantity",
            "AAPL,0",
            "MSFT,5.0",
        )
        r = self._upload(client, email, content, "h.csv")
        assert r.status_code == 200
        positions = r.json()["positions"]
        tickers = [p["ticker"] for p in positions]
        assert "AAPL" not in tickers
        assert "MSFT" in tickers

    def test_preview_csv_filename_without_extension_still_works(self, client):
        email = _uid()
        content = _csv_bytes(
            "Symbol,Quantity",
            "AAPL,5.0",
        )
        # No .pdf/.csv extension — server falls back to CSV parser
        with _mock_user(email):
            r = client.post(
                "/portfolio/import/preview",
                params={"id_token": "tok"},
                files={"file": ("export", io.BytesIO(content), "text/csv")},
            )
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# Integration — POST /portfolio/import/apply
# ══════════════════════════════════════════════════════════════════════════════

class TestImportApply:
    def _apply(self, client, email: str, positions: list[dict]):
        with _mock_user(email):
            return client.post(
                "/portfolio/import/apply",
                params={"id_token": "tok"},
                json={"positions": positions},
            )

    def test_apply_creates_new_watchlist_items(self, client):
        email = _uid()
        r = self._apply(client, email, [{"ticker": "APLX", "shares": 5.0}])
        assert r.status_code == 200
        data = r.json()
        assert "APLX" in data["added"]
        assert data["total"] == 1

    def test_apply_updates_existing_watchlist_item(self, client):
        email = _uid()
        _add_watchlist(client, email, "UPDT")
        r = self._apply(client, email, [{"ticker": "UPDT", "shares": 7.5, "avg_cost": 100.0}])
        assert r.status_code == 200
        data = r.json()
        assert "UPDT" in data["updated"]

    def test_apply_sets_shares_in_db(self, client):
        email = _uid()
        self._apply(client, email, [{"ticker": "SHRS1", "shares": 12.5}])
        # Confirm via watchlist list endpoint
        with _mock_user(email):
            r = client.get("/watchlist", params={"id_token": "tok"})
        items = {i["ticker"]: i for i in r.json()}
        assert "SHRS1" in items
        assert items["SHRS1"]["shares"] == pytest.approx(12.5)

    def test_apply_sets_avg_cost_in_db(self, client):
        email = _uid()
        self._apply(client, email, [{"ticker": "COST1", "shares": 5.0, "avg_cost": 200.0}])
        with _mock_user(email):
            r = client.get("/watchlist", params={"id_token": "tok"})
        items = {i["ticker"]: i for i in r.json()}
        assert items["COST1"]["avg_cost"] == pytest.approx(200.0)

    def test_apply_bulk_multiple_positions(self, client):
        email = _uid()
        positions = [
            {"ticker": "BLK1", "shares": 3.0},
            {"ticker": "BLK2", "shares": 7.0},
            {"ticker": "BLK3", "shares": 11.0},
        ]
        r = self._apply(client, email, positions)
        assert r.status_code == 200
        assert r.json()["total"] == 3

    def test_apply_unauthenticated_returns_401(self, client):
        r = client.post(
            "/portfolio/import/apply",
            params={"id_token": "bad-token"},
            json={"positions": [{"ticker": "AAPL", "shares": 1.0}]},
        )
        assert r.status_code == 401

    def test_apply_ticker_normalised_to_uppercase(self, client):
        email = _uid()
        r = self._apply(client, email, [{"ticker": "aapl", "shares": 5.0}])
        assert r.status_code == 200
        with _mock_user(email):
            r2 = client.get("/watchlist", params={"id_token": "tok"})
        tickers = [i["ticker"] for i in r2.json()]
        assert "AAPL" in tickers

    def test_apply_empty_positions_list(self, client):
        email = _uid()
        r = self._apply(client, email, [])
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_apply_null_avg_cost_keeps_shares_only(self, client):
        email = _uid()
        self._apply(client, email, [{"ticker": "NULLCOST", "shares": 4.0, "avg_cost": None}])
        with _mock_user(email):
            r = client.get("/watchlist", params={"id_token": "tok"})
        items = {i["ticker"]: i for i in r.json()}
        assert items["NULLCOST"]["shares"] == pytest.approx(4.0)
        assert items["NULLCOST"]["avg_cost"] is None

    def test_apply_overwrites_existing_shares(self, client):
        email = _uid()
        _add_watchlist(client, email, "OWRT")
        self._apply(client, email, [{"ticker": "OWRT", "shares": 5.0}])
        self._apply(client, email, [{"ticker": "OWRT", "shares": 10.0}])
        with _mock_user(email):
            r = client.get("/watchlist", params={"id_token": "tok"})
        items = {i["ticker"]: i for i in r.json()}
        assert items["OWRT"]["shares"] == pytest.approx(10.0)

    def test_apply_is_user_scoped(self, client):
        emailA, emailB = _uid(), _uid()
        self._apply(client, emailA, [{"ticker": "SCPA", "shares": 5.0}])
        # User B should NOT see User A's position
        with _mock_user(emailB):
            r = client.get("/watchlist", params={"id_token": "tok"})
        tickers = [i["ticker"] for i in r.json()]
        assert "SCPA" not in tickers
