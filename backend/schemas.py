from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class TokenVerifyRequest(BaseModel):
    id_token: str


class UserOut(BaseModel):
    email: str
    name: Optional[str]
    tier: str
    is_admin: bool
    tokens_used: int

    class Config:
        from_attributes = True


class WatchlistAddRequest(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    is_leveraged: bool = False


class WatchlistItemOut(BaseModel):
    id: str
    ticker: str
    company_name: Optional[str]
    sector: Optional[str]
    is_leveraged: bool
    added_at: datetime

    class Config:
        from_attributes = True


class StockAnalysisOut(BaseModel):
    id: str
    ticker: str
    analysis_date: date
    current_price: Optional[float]
    prev_close: Optional[float]
    day_change_pct: Optional[float]
    week_52_high: Optional[float]
    week_52_low: Optional[float]
    range_position_pct: Optional[float]
    volume: Optional[int]
    avg_volume: Optional[int]
    ma_50: Optional[float]
    ma_200: Optional[float]
    rsi: Optional[float]
    analyst_consensus: Optional[str]
    analyst_count: Optional[int]
    target_price_mean: Optional[float]
    verdict: Optional[str]
    entry_target: Optional[float]
    exit_target: Optional[float]
    reasoning: Optional[str]
    news_summary: Optional[str]
    events_json: Optional[str]
    ripple_analysis: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DigestItem(BaseModel):
    ticker: str
    company_name: Optional[str]
    is_leveraged: bool
    analysis: Optional[StockAnalysisOut]


class CopilotDecisionRequest(BaseModel):
    analysis_id: str
    ticker: str
    decision: str          # "approve" | "skip" | "override"
    override_action: Optional[str] = None
    override_price: Optional[float] = None


class SimulationTradeOut(BaseModel):
    id: str
    ticker: str
    action: str
    price: float
    shares: float
    trade_date: datetime
    reasoning: Optional[str]

    class Config:
        from_attributes = True


class SimulationPortfolioOut(BaseModel):
    id: str
    ticker: str
    shares: float
    entry_price: Optional[float]
    entry_date: Optional[datetime]
    status: str
    virtual_cash: float

    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    ticker: Optional[str] = None
    title: Optional[str] = None


class ConversationOut(BaseModel):
    id: str
    ticker: Optional[str]
    title: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    content: str
    user_email: str
    id_token: str


class NightlyJobRequest(BaseModel):
    secret: str
    tickers: Optional[list[str]] = None  # None = run all watchlisted tickers


class IngestAnalysisRequest(BaseModel):
    ticker: str
    analysis_date: date
    current_price: Optional[float] = None
    price_change_pct: Optional[float] = None
    week52_high: Optional[float] = None
    week52_low: Optional[float] = None
    week52_position_pct: Optional[float] = None
    ma50: Optional[float] = None
    ma200: Optional[float] = None
    rsi: Optional[float] = None
    analyst_consensus: Optional[str] = None
    analyst_upside_pct: Optional[float] = None
    verdict: str
    entry_target: Optional[float] = None
    exit_target: Optional[float] = None
    reasoning: Optional[str] = None
    news_summary: Optional[str] = None
    ripple_analysis: Optional[str] = None
    is_important_day: bool = False
    importance_reason: Optional[str] = None
