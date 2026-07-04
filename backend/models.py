from datetime import datetime, date
from uuid import uuid4
from sqlalchemy import (
    Column, String, Boolean, Integer, BigInteger, Float, Text,
    DateTime, Date, ForeignKey,
)
from database import Base


def _uid():
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    email = Column(String, primary_key=True)
    name = Column(String)
    tier = Column(String, nullable=False, default="free")
    is_admin = Column(Boolean, nullable=False, default=False)
    tokens_used = Column(Integer, nullable=False, default=0)
    token_limit = Column(Integer, nullable=True)
    portfolio_size = Column(Float, nullable=True)   # user-provided approximate portfolio value
    created_at = Column(DateTime, default=datetime.utcnow)


class WatchlistItem(Base):
    """Per-user list of tickers to track. Analysis is global per ticker."""
    __tablename__ = "watchlist_items"
    id = Column(String, primary_key=True, default=_uid)
    user_email = Column(String, ForeignKey("users.email"), nullable=False)
    ticker = Column(String, nullable=False)
    company_name = Column(String)
    sector = Column(String)
    is_leveraged = Column(Boolean, default=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    last_read_analysis_id = Column(String, ForeignKey("stock_analyses.id"), nullable=True)
    last_read_at = Column(DateTime, nullable=True)
    shares = Column(Float, nullable=True)    # null = watchlist only; set = portfolio position
    avg_cost = Column(Float, nullable=True)  # average cost per share


class MarketDataCache(Base):
    """Raw yfinance data per ticker per day — prevents redundant API calls."""
    __tablename__ = "market_data_cache"
    ticker = Column(String, primary_key=True)
    cache_date = Column(Date, primary_key=True)
    info_json = Column(Text)        # yf.Ticker.info dict
    history_json = Column(Text)     # 1-year daily OHLCV as JSON
    news_json = Column(Text)        # raw news list
    calendar_json = Column(Text)    # earnings calendar
    created_at = Column(DateTime, default=datetime.utcnow)


class StockAnalysis(Base):
    """Nightly analysis result — global per ticker, not per user."""
    __tablename__ = "stock_analyses"
    id = Column(String, primary_key=True, default=_uid)
    ticker = Column(String, nullable=False, index=True)
    analysis_date = Column(Date, nullable=False, index=True)

    # Price snapshot
    current_price = Column(Float)
    prev_close = Column(Float)
    day_change_pct = Column(Float)
    day_high = Column(Float)
    day_low = Column(Float)
    week_52_high = Column(Float)
    week_52_low = Column(Float)
    range_position_pct = Column(Float)  # 0=at 52w low, 100=at 52w high
    volume = Column(BigInteger)
    avg_volume = Column(BigInteger)
    ma_50 = Column(Float)
    ma_200 = Column(Float)
    rsi = Column(Float)

    # Support / Resistance levels (computed nightly from price history)
    support_20d = Column(Float)      # 20-day swing low — short-term support floor
    resistance_20d = Column(Float)   # 20-day swing high — short-term resistance ceiling
    pivot_point = Column(Float)      # classic pivot: (prev_H + prev_L + prev_C) / 3
    pivot_r1 = Column(Float)         # resistance 1: 2*pivot - prev_low
    pivot_s1 = Column(Float)         # support 1:    2*pivot - prev_high

    # Market / Sector context (relative performance)
    sp500_day_chg = Column(Float)       # S&P 500 % change today — market tailwind/headwind
    sector_etf = Column(String)         # e.g. "XLK", "SOXX" — sector proxy ETF
    sector_day_chg = Column(Float)      # sector ETF % change today
    relative_strength_1d = Column(Float)  # stock % today − sector % today (+ = outperforming)

    # Finnhub cross-validation (secondary source)
    fh_price = Column(Float)            # Finnhub last price — for conflict detection
    fh_analyst_consensus = Column(String)  # Finnhub analyst rating — for conflict detection

    # Analyst data
    analyst_consensus = Column(String)
    analyst_count = Column(Integer)
    target_price_mean = Column(Float)
    target_price_high = Column(Float)
    target_price_low = Column(Float)

    # Fundamentals (extracted from yfinance .info — same fetch, no extra API call)
    pe_trailing = Column(Float)
    pe_forward = Column(Float)
    revenue_growth = Column(Float)       # e.g. 0.12 = 12% YoY
    earnings_growth = Column(Float)
    profit_margin = Column(Float)
    debt_to_equity = Column(Float)
    free_cashflow = Column(Float)
    return_on_equity = Column(Float)
    beta = Column(Float)
    short_float_pct = Column(Float)      # % of float sold short
    short_ratio = Column(Float)          # days to cover
    inst_ownership_pct = Column(Float)
    insider_ownership_pct = Column(Float)
    sp500_52w_change = Column(Float)     # S&P 500 return over same period (relative strength context)
    stock_52w_change = Column(Float)
    sp500_5y_change = Column(Float)      # 5-year trailing return, same idea over a longer horizon
    stock_5y_change = Column(Float)
    dividend_yield = Column(Float)
    market_cap = Column(Float)
    sector = Column(String)
    industry = Column(String)
    fundamentals_json = Column(Text)     # full dump for future use

    # Verdict (output of Verdict Agent)
    verdict = Column(String)  # BUY / HOLD / SELL / WATCH
    entry_target = Column(Float)
    exit_target = Column(Float)
    stop_loss = Column(Float)
    hold_period = Column(String)  # e.g. "3-5 days", "2-4 weeks", "1-3 months"
    reasoning = Column(Text)
    conviction_score = Column(Integer)   # 0-100, strength of the setup
    risk_level = Column(String)          # LOW / MED / HIGH
    confidence = Column(String)          # High / Medium / Low
    bull_case = Column(Text)
    bear_case = Column(Text)
    thesis_invalidation = Column(Text)   # the single event that flips the verdict

    # Simple-language versions (pre-generated by Haiku during nightly run)
    reasoning_simple = Column(Text)
    bull_case_simple = Column(Text)
    bear_case_simple = Column(Text)
    thesis_invalidation_simple = Column(Text)
    news_summary_simple = Column(Text)

    # Agent outputs
    news_summary = Column(Text)
    events_json = Column(Text)       # JSON list of upcoming events
    ripple_analysis = Column(Text)

    # Data quality
    data_conflicts = Column(Text)    # cross-validation issues flagged

    # Historical significance
    is_important_day = Column(Boolean, default=False)
    importance_reason = Column(Text)  # why this day is flagged as significant

    # Trust layer — busy professional signals
    entry_quality = Column(String)       # GREAT | FAIR | WAIT
    hold_and_forget_rating = Column(String)  # HOLD_AND_FORGET | CHECK_MONTHLY | WATCH_CLOSELY
    position_size_pct = Column(String)   # e.g. "5–8%"
    scenario_bull = Column(Text)
    scenario_base = Column(Text)
    scenario_bear = Column(Text)
    scenario_bull_pct = Column(Float)    # expected % return
    scenario_base_pct = Column(Float)
    scenario_bear_pct = Column(Float)
    scenario_bull_prob = Column(Integer) # probability 0-100 (three sum to 100)
    scenario_base_prob = Column(Integer)
    scenario_bear_prob = Column(Integer)
    dont_panic_note = Column(Text)       # populated when price dropped >15% since last BUY

    # Signal convergence — deterministic pre-verdict score
    signal_convergence_score = Column(Integer)  # 0-10, how many independent signals align
    convergence_details = Column(Text)          # JSON dict of which signals fired

    # Dual-agent verdicts — Claude (A) vs Gemini (B), reconciled by judge
    verdict_a = Column(String)       # Claude Sonnet 4.6 raw verdict
    verdict_b = Column(String)       # Gemini 2.5 Flash raw verdict
    verdict_agreement = Column(Boolean)  # True = both agree, False = split
    split_reason = Column(Text)      # populated when verdict_a != verdict_b

    # Token usage + cost tracking (Python agents only — excludes GHA claude-code-action).
    # In production this is Gemini Verdict B's usage — Claude's Verdict A + judge steps run
    # as the orchestrating claude-code-action agent's own reasoning, not a scripted API call,
    # so there's no usage object to read for those.
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    tokens_cache_read = Column(Integer, default=0)
    tokens_cache_write = Column(Integer, default=0)
    cost_usd = Column(Float)         # total USD cost for verdict + ripple + news agents

    # Simple-language (Haiku) rewrite job — fully backend-controlled, tracked separately.
    simple_fields_tokens_input = Column(Integer)
    simple_fields_tokens_output = Column(Integer)
    simple_fields_cost_usd = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)


class StockMemory(Base):
    """Persistent prose narrative per ticker — updated by nightly runner when significant."""
    __tablename__ = "stock_memories"
    ticker = Column(String, primary_key=True)
    memory_narrative = Column(Text, default="")
    last_updated = Column(DateTime, default=datetime.utcnow)
    update_count = Column(Integer, default=0)


class StockReport(Base):
    """On-demand AI-generated report synthesizing past analyses for a ticker. One per ticker per day."""
    __tablename__ = "stock_reports"
    id = Column(String, primary_key=True, default=_uid)
    ticker = Column(String, nullable=False, index=True)
    report_date = Column(Date, nullable=False, index=True)
    content = Column(Text, nullable=False)   # markdown narrative
    analyses_count = Column(Integer)         # how many past analyses were fed in
    created_at = Column(DateTime, default=datetime.utcnow)


class SimulationPortfolio(Base):
    """Virtual $10k portfolio per user per mode (autopilot / copilot)."""
    __tablename__ = "simulation_portfolios"
    id = Column(String, primary_key=True, default=_uid)
    user_email = Column(String, ForeignKey("users.email"), nullable=False)
    mode = Column(String, nullable=False)  # "autopilot" | "copilot"
    ticker = Column(String, nullable=False)
    shares = Column(Float, default=0.0)
    entry_price = Column(Float)
    entry_date = Column(DateTime)
    status = Column(String, default="watch")  # "watch" | "open" | "closed"
    virtual_cash = Column(Float, default=10000.0)


class SimulationTrade(Base):
    """Individual buy/sell event inside a simulation."""
    __tablename__ = "simulation_trades"
    id = Column(String, primary_key=True, default=_uid)
    user_email = Column(String, ForeignKey("users.email"), nullable=False)
    mode = Column(String, nullable=False)
    ticker = Column(String, nullable=False)
    action = Column(String, nullable=False)  # "buy" | "sell"
    price = Column(Float, nullable=False)
    shares = Column(Float, nullable=False)
    trade_date = Column(DateTime, default=datetime.utcnow)
    reasoning = Column(Text)
    analysis_id = Column(String, ForeignKey("stock_analyses.id"))


class CopilotDecision(Base):
    """Records what the user did with each Co-pilot recommendation."""
    __tablename__ = "copilot_decisions"
    id = Column(String, primary_key=True, default=_uid)
    user_email = Column(String, ForeignKey("users.email"), nullable=False)
    analysis_id = Column(String, ForeignKey("stock_analyses.id"), nullable=False)
    ticker = Column(String, nullable=False)
    decision = Column(String, nullable=False)  # "approve" | "skip" | "override"
    override_action = Column(String)            # "buy" | "sell" | "hold" if override
    override_price = Column(Float)
    decided_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    """Chatbot conversation — optionally scoped to a ticker."""
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=_uid)
    user_email = Column(String, ForeignKey("users.email"), nullable=False)
    ticker = Column(String)   # None = general finance chat
    title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, default=_uid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    model_used = Column(String)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cache_read_tokens = Column(Integer, default=0)
    cache_write_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class AppConfig(Base):
    __tablename__ = "app_config"
    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)


class TickerControl(Base):
    """Admin on/off switch for the nightly analysis job — global per ticker, since
    StockAnalysis is shared across every user tracking that ticker."""
    __tablename__ = "ticker_control"
    ticker = Column(String, primary_key=True)
    analysis_enabled = Column(Boolean, nullable=False, default=True)
    disabled_by = Column(String, ForeignKey("users.email"), nullable=True)
    disabled_at = Column(DateTime, nullable=True)


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(String, primary_key=True, default=_uid)
    user_email = Column(String, ForeignKey("users.email"), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
