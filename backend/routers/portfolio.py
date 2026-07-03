"""
Portfolio import — parse Robinhood (and other broker) PDF/CSV statements
and bulk-create/update watchlist items with real share positions.

Format detection order:
  1. Robinhood transaction history (Trans Code + Instrument columns)
  2. Standard holdings CSV  (Symbol/Ticker + Quantity column names)
  3. AI fallback            (send sample to Haiku, parse JSON response)
"""
import asyncio
import csv
import io
import json
import logging
import os
import re
from collections import defaultdict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from models import WatchlistItem
from routers.auth import get_current_user
from schemas import ImportApplyRequest, ImportPreviewItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

_TICKER_RE = re.compile(r'^[A-Z]{1,5}(?:\.[A-Z]{1,2})?$')

# ── PDF parser (Robinhood monthly statement) ─────────────────────────────────

def _parse_pdf(content: bytes) -> list[ImportPreviewItem]:
    from pypdf import PdfReader  # lazy import — not in all envs
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # Robinhood Portfolio Summary table:
    # "AAPL Margin 13.291901 $312.06000 $4,147.87 ..."
    # Pattern: TICKER (Margin|Cash) QUANTITY $PRICE
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


# ── CSV parsers ───────────────────────────────────────────────────────────────

_TICKER_CANDIDATES = ["symbol", "ticker", "stock symbol", "security"]
_SHARES_CANDIDATES = ["quantity", "shares", "qty", "units", "# shares"]
_COST_CANDIDATES   = ["average cost", "avg cost", "avg. cost", "cost per share",
                      "average buy price", "average cost basis"]


def _parse_robinhood_transactions(rows: list[dict], norm: dict[str, str]) -> list[ImportPreviewItem]:
    """
    Aggregate Robinhood activity CSV into net positions.
    Columns: Activity Date, Instrument, Trans Code, Quantity, Price, Amount, ...
    """
    instrument_col  = norm["instrument"]
    trans_code_col  = norm["trans code"]
    quantity_col    = norm.get("quantity", "")
    price_col       = norm.get("price", "")

    net_shares: dict[str, float]   = defaultdict(float)
    total_cost:  dict[str, float]  = defaultdict(float)   # sum(qty * price) for buys
    total_bought: dict[str, float] = defaultdict(float)   # sum(qty) for buys

    for row in rows:
        ticker = (row.get(instrument_col) or "").strip().upper()
        if not ticker or not _TICKER_RE.match(ticker):
            continue

        trans = (row.get(trans_code_col) or "").strip().upper()
        qty_raw   = (row.get(quantity_col) or "").strip().replace(",", "")
        price_raw = (row.get(price_col)   or "").strip().replace(",", "").replace("$", "").replace("(", "").replace(")", "")

        try:
            qty = float(qty_raw) if qty_raw else 0.0
        except ValueError:
            continue

        if qty <= 0:
            continue

        if trans == "BUY":
            net_shares[ticker] += qty
            total_bought[ticker] += qty
            if price_raw:
                try:
                    total_cost[ticker] += qty * float(price_raw)
                except ValueError:
                    pass
        elif trans == "SELL":
            net_shares[ticker] -= qty

    results: list[ImportPreviewItem] = []
    for ticker in sorted(net_shares):
        shares = round(net_shares[ticker], 6)
        if shares < 0.000001:
            continue
        avg_cost: float | None = None
        if total_bought[ticker] > 0 and total_cost[ticker] > 0:
            avg_cost = round(total_cost[ticker] / total_bought[ticker], 4)
        results.append(ImportPreviewItem(ticker=ticker, shares=shares, avg_cost=avg_cost))

    return results


def _parse_holdings_csv(rows: list[dict], norm: dict[str, str]) -> list[ImportPreviewItem]:
    """Standard holdings CSV — one row per position."""
    ticker_col = next((norm[c] for c in _TICKER_CANDIDATES if c in norm), None)
    shares_col = next((norm[c] for c in _SHARES_CANDIDATES if c in norm), None)
    cost_col   = next((norm[c] for c in _COST_CANDIDATES   if c in norm), None)

    if not ticker_col or not shares_col:
        raise ValueError("Could not find ticker/symbol or quantity/shares columns in CSV.")

    results: list[ImportPreviewItem] = []
    seen: set[str] = set()

    for row in rows:
        ticker = (row.get(ticker_col) or "").strip().upper()
        shares_raw = (row.get(shares_col) or "").strip().replace(",", "").replace("$", "")

        if not ticker or ticker in seen:
            continue
        if " " in ticker or not _TICKER_RE.match(ticker):
            continue
        try:
            shares = float(shares_raw)
            if shares <= 0:
                continue
        except ValueError:
            continue

        avg_cost = None
        if cost_col:
            cost_raw = (row.get(cost_col) or "").strip().replace(",", "").replace("$", "")
            try:
                avg_cost = float(cost_raw) if cost_raw else None
            except ValueError:
                pass

        seen.add(ticker)
        results.append(ImportPreviewItem(ticker=ticker, shares=shares, avg_cost=avg_cost))

    return results


def _parse_csv(content: bytes) -> list[ImportPreviewItem]:
    """Legacy entry point — kept for existing unit tests. Calls _parse_holdings_csv."""
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    norm = {k.lower().strip(): k for k in rows[0].keys()}
    return _parse_holdings_csv(rows, norm)


def _try_parse_csv(content: bytes) -> list[ImportPreviewItem] | None:
    """
    Detect CSV format and dispatch to the right parser.
    Returns None if format is unrecognised (caller should use AI fallback).
    """
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []

    norm = {k.lower().strip(): k for k in rows[0].keys()}

    # Fewer than 2 columns → malformed CSV, not an "unknown broker" format
    if len(norm) < 2:
        raise ValueError("CSV appears malformed — fewer than 2 columns detected.")

    # Robinhood transaction history
    if "trans code" in norm and "instrument" in norm:
        logger.info("Detected Robinhood transaction history CSV")
        return _parse_robinhood_transactions(rows, norm)

    # Standard holdings CSV
    has_ticker = any(c in norm for c in _TICKER_CANDIDATES)
    has_shares = any(c in norm for c in _SHARES_CANDIDATES)
    if has_ticker and has_shares:
        logger.info("Detected standard holdings CSV")
        return _parse_holdings_csv(rows, norm)

    # Format unknown — signal AI fallback
    return None


def _ai_parse_csv_sync(content: bytes) -> list[ImportPreviewItem]:
    """Send CSV sample to Haiku; parse its JSON response into positions."""
    import anthropic  # lazy — not needed unless AI fallback triggered

    text = content.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    # Send header + first 30 data rows to stay token-light
    sample = "\n".join(lines[:31])

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": (
                "Extract stock portfolio positions from this CSV.\n"
                "Return ONLY a JSON array — no explanation, no markdown.\n"
                "Each element: {\"ticker\": \"AAPL\", \"shares\": 5.0, \"avg_cost\": 150.0}\n"
                "avg_cost is null if not available.\n"
                "Skip: cash, options, fees, ADR fees, dividends, rows with no shares, rows where net position is 0 or negative.\n"
                "Ticker must be 1-5 uppercase letters (or LETTER.B format like BRK.B).\n\n"
                f"CSV:\n{sample}\n\nJSON array:"
            ),
        }],
    )

    raw = msg.content[0].text.strip()
    # Strip markdown code fences if present
    if "```" in raw:
        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        raw = m.group(0) if m else "[]"

    data = json.loads(raw)
    results: list[ImportPreviewItem] = []
    for item in data:
        ticker = str(item.get("ticker", "")).strip().upper()
        if not ticker or not _TICKER_RE.match(ticker):
            continue
        try:
            shares = float(item["shares"])
        except (KeyError, TypeError, ValueError):
            continue
        if shares <= 0:
            continue
        raw_cost = item.get("avg_cost")
        avg_cost = float(raw_cost) if raw_cost is not None else None
        results.append(ImportPreviewItem(ticker=ticker, shares=round(shares, 6), avg_cost=avg_cost))
    return results


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/import/preview")
async def import_preview(
    id_token: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Parse a PDF/CSV broker statement and return positions for user review. Does NOT save anything."""
    get_current_user(id_token, db)
    content = await file.read()
    fname = (file.filename or "").lower()

    try:
        if fname.endswith(".pdf"):
            positions = _parse_pdf(content)
        elif fname.endswith(".csv"):
            positions = _try_parse_csv(content)
            if positions is None:
                logger.info("Unknown CSV format — using Haiku AI parser")
                positions = await asyncio.to_thread(_ai_parse_csv_sync, content)
        else:
            # No extension — try CSV dispatch, fall back to PDF
            positions = _try_parse_csv(content)
            if positions is None:
                try:
                    positions = await asyncio.to_thread(_ai_parse_csv_sync, content)
                except Exception:
                    positions = _parse_pdf(content)
    except ImportError:
        raise HTTPException(status_code=500, detail="PDF parsing not available — pypdf not installed.")
    except Exception as e:
        logger.warning(f"Import parse error: {e}")
        raise HTTPException(status_code=422, detail=f"Could not parse file: {e}")

    if not positions:
        raise HTTPException(status_code=422, detail="No valid stock positions found in the file.")

    return {"positions": [p.model_dump() for p in positions]}


@router.post("/import/apply")
def import_apply(
    id_token: str,
    body: ImportApplyRequest,
    db: Session = Depends(get_db),
):
    """Save confirmed positions — creates watchlist items if missing, sets shares/avg_cost."""
    user = get_current_user(id_token, db)
    added: list[str] = []
    updated: list[str] = []

    for pos in body.positions:
        ticker = pos.ticker.upper()
        item = db.query(WatchlistItem).filter(
            WatchlistItem.user_email == user.email,
            WatchlistItem.ticker == ticker,
        ).first()

        if item:
            item.shares = pos.shares
            if pos.avg_cost is not None:
                item.avg_cost = pos.avg_cost
            updated.append(ticker)
        else:
            item = WatchlistItem(
                user_email=user.email,
                ticker=ticker,
                company_name=pos.company_name,
                shares=pos.shares,
                avg_cost=pos.avg_cost,
                is_leveraged=False,
            )
            db.add(item)
            added.append(ticker)

    db.commit()
    return {"added": added, "updated": updated, "total": len(added) + len(updated)}
