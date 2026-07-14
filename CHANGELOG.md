# Changelog

All notable changes to FinanceCompanion are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning is
[SemVer](https://semver.org/): pre-1.0, so MINOR bumps may include breaking changes, PATCH is fixes.

## [0.2.0] — 2026-07-14

### Added
- Stock detail panel in chat — jump to any tracked ticker's full card without leaving the conversation (#73)
- `get_stock_analysis` tool for Ask AI — full vetted dossier for any ticker on demand instead of a web search (#74)
- Bounds-sanity check on nightly entry/exit/stop targets, flagged into `data_conflicts` (#75)
- Judge step flags conviction-score divergence (30+ points) between Claude and Gemini even when the verdict agrees (#75)

### Changed
- Ask AI chat always uses Sonnet — removed the Haiku fast-path router after finding it leaked real financial advice on short/ambiguous follow-ups (#74)
- Ask AI context is now tiered: full dossier for the focus ticker, compact numeric summary for other tracked tickers, full detail unchanged for general chat (#74)
- Prompt caching fixed — the cacheable block was permanently under Anthropic's ~1024-token minimum, so caching silently never fired in production (#74)
- Grounding instructions ("never invent a number") added across all LLM surfaces: chat, both nightly verdict agents, the AI report, and stock memory updates (#75)
- `data_conflicts` (cross-source + target-sanity warnings) now reaches Ask AI via the ticker dossier — previously it was recorded but never surfaced to chat (#75)

## [0.1.0] — 2026-06-22 to 2026-07-06

Initial build and early iteration. Selected highlights, grouped by theme (56 PRs total):

### Core product
- Dashboard, My Stocks tab, watchlist, portfolio import/P&L, admin portal
- Nightly agent pipeline: price/news/event/analyst agents + dual-agent verdict (Claude + Gemini) with judge reconciliation
- Per-ticker Stock Memory — persistent prose narrative updated after significant nights
- AskAI persistent per-ticker chat, on-demand AI reports, verdict trust layer (entry quality, scenarios, hold-and-forget, don't-panic notes)
- Standing audit agents — weekly Verdict Scorecard, daily Data Quality Sentinel

### Notable fixes
- Railway healthcheck crash from `DATETIME` vs `TIMESTAMP` in raw SQL migrations
- Simple-language field generation was dead in the production ingest path
- Nightly workflow exceeded GitHub Actions' 21,000-char expression limit
- Dashboard fundamentals card showed 100x-inflated percentages
- Various chat stability fixes (crash on missing analysis data, lost ticker focus at scale, stuck on non-2xx responses)

### Performance
- ~65% nightly analysis cost reduction (smart skip + Haiku ripple agent + prompt caching)
