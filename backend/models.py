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

    # Analyst data
    analyst_consensus = Column(String)
    analyst_count = Column(Integer)
    target_price_mean = Column(Float)
    target_price_high = Column(Float)
    target_price_low = Column(Float)

    # Verdict (output of Verdict Agent)
    verdict = Column(String)  # BUY / HOLD / SELL / WATCH
    entry_target = Column(Float)
    exit_target = Column(Float)
    reasoning = Column(Text)

    # Agent outputs
    news_summary = Column(Text)
    events_json = Column(Text)       # JSON list of upcoming events
    ripple_analysis = Column(Text)

    # Data quality
    data_conflicts = Column(Text)    # cross-validation issues flagged

    # Historical significance
    is_important_day = Column(Boolean, default=False)
    importance_reason = Column(Text)  # why this day is flagged as significant

    created_at = Column(DateTime, default=datetime.utcnow)


class StockMemory(Base):
    """Persistent prose narrative per ticker — updated by nightly runner when significant."""
    __tablename__ = "stock_memories"
    ticker = Column(String, primary_key=True)
    memory_narrative = Column(Text, default="")
    last_updated = Column(DateTime, default=datetime.utcnow)
    update_count = Column(Integer, default=0)


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
