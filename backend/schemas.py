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
    pe_trailing: Optional[float]
    pe_forward: Optional[float]
    revenue_growth: Optional[float]
    earnings_growth: Optional[float]
    profit_margin: Optional[float]
    debt_to_equity: Optional[float]
    free_cashflow: Optional[float]
    return_on_equity: Optional[float]
    beta: Optional[float]
    short_float_pct: Optional[float]
    short_ratio: Optional[float]
    inst_ownership_pct: Optional[float]
    insider_ownership_pct: Optional[float]
    sp500_52w_change: Optional[float]
    stock_52w_change: Optional[float]
    dividend_yield: Optional[float]
    market_cap: Optional[float]
    sector: Optional[str]
    industry: Optional[str]
    verdict: Optional[str]
    entry_target: Optional[float]
    exit_target: Optional[float]
    stop_loss: Optional[float]
    hold_period: Optional[str]
    reasoning: Optional[str]
    conviction_score: Optional[int]
    risk_level: Optional[str]
    confidence: Optional[str]
    bull_case: Optional[str]
    bear_case: Optional[str]
    thesis_invalidation: Optional[str]
    news_summary: Optional[str]
    events_json: Optional[str]
    ripple_analysis: Optional[str]
    is_important_day: Optional[bool]
    importance_reason: Optional[str]
    entry_quality: Optional[str]
    hold_and_forget_rating: Optional[str]
    position_size_pct: Optional[str]
    scenario_bull: Optional[str]
    scenario_base: Optional[str]
    scenario_bear: Optional[str]
    scenario_bull_pct: Optional[float]
    scenario_base_pct: Optional[float]
    scenario_bear_pct: Optional[float]
    scenario_bull_prob: Optional[int]
    scenario_base_prob: Optional[int]
    scenario_bear_prob: Optional[int]
    dont_panic_note: Optional[str]
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


class ImportantFlag(BaseModel):
    ticker: str
    verdict: str
    importance_reason: Optional[str] = None


class ReportDayOut(BaseModel):
    report_date: str
    analyzed_count: int
    total_watchlist: int
    by_verdict: dict[str, list[str]]
    important_flags: list[ImportantFlag]


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
    pe_trailing: Optional[float] = None
    pe_forward: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    profit_margin: Optional[float] = None
    debt_to_equity: Optional[float] = None
    free_cashflow: Optional[float] = None
    return_on_equity: Optional[float] = None
    beta: Optional[float] = None
    short_float_pct: Optional[float] = None
    short_ratio: Optional[float] = None
    inst_ownership_pct: Optional[float] = None
    insider_ownership_pct: Optional[float] = None
    sp500_52w_change: Optional[float] = None
    stock_52w_change: Optional[float] = None
    dividend_yield: Optional[float] = None
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    verdict: str
    entry_target: Optional[float] = None
    exit_target: Optional[float] = None
    stop_loss: Optional[float] = None
    hold_period: Optional[str] = None
    reasoning: Optional[str] = None
    conviction_score: Optional[int] = None
    risk_level: Optional[str] = None
    confidence: Optional[str] = None
    bull_case: Optional[str] = None
    bear_case: Optional[str] = None
    thesis_invalidation: Optional[str] = None
    news_summary: Optional[str] = None
    ripple_analysis: Optional[str] = None
    is_important_day: bool = False
    importance_reason: Optional[str] = None
