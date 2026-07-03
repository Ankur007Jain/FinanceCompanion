## QA Report — main..HEAD — 2026-07-02

### Summary
**300 backend passing, 0 failing · 53 frontend passing, 0 failing · 0 bugs found · 70 new tests written**

### Bugs Found
_None_ — all new endpoints and parsing logic are correct.

### New Tests Written

| File | Tests added | Coverage area |
|------|-------------|---------------|
| `backend/tests/test_portfolio_import.py` | 41 | CSV parser (unit), PDF regex (unit), `POST /portfolio/import/preview`, `POST /portfolio/import/apply` |
| `backend/tests/test_watchlist_portfolio.py` | 29 | `PATCH /watchlist/{ticker}/portfolio`, `PATCH /watchlist/{ticker}/sell`, digest `shares`/`avg_cost` propagation |

#### test_portfolio_import.py breakdown
| Class | Tests |
|-------|-------|
| `TestParseCsv` | 17 unit tests — column aliases, zero/negative rows, options skipped, >5-char tickers, dedup, empty CSV, missing columns, BOM prefix, uppercase normalisation, comma-in-number, dollar-sign stripping |
| `TestParsePdfRegex` | 7 unit tests — Margin/Cash positions, multi-position, dedup, zero shares, dot-ticker, case sensitivity |
| `TestImportPreview` | 8 integration tests — happy path, response shape, preview does not write DB, 401, 422 on bad file, 422 on empty, zero-share filter, no-extension fallback |
| `TestImportApply` | 9 integration tests — creates new item, updates existing, sets shares, sets avg_cost, bulk, 401, ticker normalisation, empty list, null avg_cost |

#### test_watchlist_portfolio.py breakdown
| Class | Tests |
|-------|-------|
| `TestSetPortfolioPosition` | 12 tests — 200 response, shares/avg_cost returned, avg_cost optional, fractional shares, 404 for missing ticker, 401 unauth, case-insensitive ticker, update existing, user isolation, 422 missing shares, DB persistence |
| `TestClearPortfolioPosition` | 10 tests — 200 response, shares cleared, avg_cost cleared, item stays in watchlist, 404 for missing, 401 unauth, case-insensitive, user isolation, no-op on watchlist-only item, re-add after sell |
| `TestDigestPortfolioFields` | 4 tests — `shares` field present, null for watchlist-only, set after portfolio position, cleared after sell |

### Test Fixes Required (not source bugs)
| Test | Fix applied |
|------|-------------|
| `TestParseCsv::test_fidelity_style_columns` | "Average Cost Basis" IS in `_COST_CANDIDATES` — corrected to use "Acquisition Price" as non-matching header; added separate positive test |
| 18 tests with digit-in-ticker (e.g. `SPOS1`, `SELL1`, `DGTS3`) | Ticker regex `^[A-Z]{1,5}...` disallows digits — renamed to letter-only tickers ≤5 chars |
| 4 tests with 6-char tickers (`SPPERS`, `SELLCI`, `SELISO`, `SELLNV`) | Same regex rule — shortened to ≤5 chars |

### Coverage Gaps (not auto-covered — future work)
- E2E: import modal UI flow (drag-drop file → preview table → apply button)
- E2E: "Add Position" modal in Watchlist tab
- E2E: My Stocks tab rendering with portfolio strip (P&L, weight %, AI suggestion)
- Frontend unit tests for `PortfolioSummary` and `PortfolioStrip` components
- PDF parser integration test with a real Robinhood PDF (binary fixture required)

### All Test Results

```
Backend (pytest):
====================== 300 passed, 334 warnings in 20.73s ======================

Frontend (jest):
Tests:  53 passed, 53 total
Time:   0.574 s
```
