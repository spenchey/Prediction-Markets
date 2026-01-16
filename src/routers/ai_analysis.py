"""
FastAPI Router for AI-powered whale trade analysis.

This router provides endpoints that use Claude's Skills API
to analyze prediction market whale trades.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from ..services.claude_skills_service import (
    ClaudeSkillsService,
    WhaleTradeData,
    WhaleAnalysis
)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Analysis"])


# Request/Response Models

class WhaleTradeRequest(BaseModel):
    """Request model for whale trade analysis."""
    market_question: str = Field(..., description="The prediction market question")
    position: str = Field(..., pattern="^(YES|NO)$", description="Trade position (YES or NO)")
    amount_usd: float = Field(..., gt=0, description="Trade amount in USD")
    entry_price: float = Field(..., ge=0, le=1, description="Entry price (0-1)")
    price_before: float = Field(..., ge=0, le=1, description="Market price before trade")
    price_after: float = Field(..., ge=0, le=1, description="Market price after trade")
    wallet_address: str = Field(..., description="Wallet address")
    timestamp: Optional[str] = Field(None, description="Trade timestamp (ISO format)")
    market_volume_24h: Optional[float] = Field(None, description="24h market volume in USD")
    wallet_historical_accuracy: Optional[float] = Field(None, description="Wallet historical accuracy %")

    model_config = {
        "json_schema_extra": {
            "example": {
                "market_question": "Will Bitcoin reach $100k by March 2025?",
                "position": "YES",
                "amount_usd": 50000,
                "entry_price": 0.45,
                "price_before": 0.42,
                "price_after": 0.45,
                "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
                "timestamp": "2025-01-15T14:30:00Z",
                "market_volume_24h": 500000,
                "wallet_historical_accuracy": 72.5
            }
        }
    }


class WhaleAnalysisResponse(BaseModel):
    """Response model for whale trade analysis."""
    summary: str
    smart_money_signal: str
    confidence: str
    key_insight: str
    full_analysis: str


class AlertMessageRequest(BaseModel):
    """Request model for generating alert messages."""
    trade: WhaleTradeRequest
    channel: str = Field(
        default="telegram",
        pattern="^(telegram|discord|slack|email)$",
        description="Notification channel"
    )


class AlertMessageResponse(BaseModel):
    """Response model for alert message generation."""
    channel: str
    message: str


class MultiTradeRequest(BaseModel):
    """Request model for analyzing multiple trades."""
    trades: list[WhaleTradeRequest] = Field(..., min_length=1, max_length=20)


class MultiTradeResponse(BaseModel):
    """Response model for multi-trade pattern analysis."""
    trade_count: int
    analysis: str


# Singleton service instance
_skills_service: Optional[ClaudeSkillsService] = None


def get_skills_service() -> ClaudeSkillsService:
    """Dependency to get Claude Skills service instance."""
    global _skills_service
    if _skills_service is None:
        _skills_service = ClaudeSkillsService()
    return _skills_service


# Endpoints

@router.get("/health")
async def ai_health_check():
    """Check if the AI analysis service is available."""
    service = get_skills_service()
    return {
        "status": "healthy" if service.is_available() else "degraded",
        "service": "claude-skills-integration",
        "api_configured": service.is_available()
    }


@router.post("/analyze", response_model=WhaleAnalysisResponse)
async def analyze_whale_trade(
    request: WhaleTradeRequest,
    service: ClaudeSkillsService = Depends(get_skills_service)
) -> WhaleAnalysisResponse:
    """
    Analyze a single whale trade using AI.

    This endpoint uses Claude's prediction markets analyst skill to provide
    intelligent analysis of significant trades, including:
    - Smart money signal assessment
    - Confidence level
    - Key actionable insights
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="AI analysis service unavailable. Set ANTHROPIC_API_KEY to enable."
        )

    try:
        trade = WhaleTradeData(
            market_question=request.market_question,
            position=request.position,
            amount_usd=request.amount_usd,
            entry_price=request.entry_price,
            price_before=request.price_before,
            price_after=request.price_after,
            wallet_address=request.wallet_address,
            timestamp=request.timestamp or datetime.utcnow().isoformat(),
            market_volume_24h=request.market_volume_24h,
            wallet_historical_accuracy=request.wallet_historical_accuracy
        )

        analysis = service.analyze_whale_trade(trade)

        if analysis is None:
            raise HTTPException(status_code=500, detail="Analysis failed")

        return WhaleAnalysisResponse(
            summary=analysis.summary,
            smart_money_signal=analysis.smart_money_signal,
            confidence=analysis.confidence,
            key_insight=analysis.key_insight,
            full_analysis=analysis.full_analysis
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze/batch", response_model=MultiTradeResponse)
async def analyze_multiple_trades(
    request: MultiTradeRequest,
    service: ClaudeSkillsService = Depends(get_skills_service)
) -> MultiTradeResponse:
    """
    Analyze multiple whale trades for patterns and correlations.

    This endpoint examines a batch of trades to identify:
    - Common themes across markets
    - Coordinated trading patterns
    - Overall smart money sentiment
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="AI analysis service unavailable. Set ANTHROPIC_API_KEY to enable."
        )

    try:
        trades = [
            WhaleTradeData(
                market_question=t.market_question,
                position=t.position,
                amount_usd=t.amount_usd,
                entry_price=t.entry_price,
                price_before=t.price_before,
                price_after=t.price_after,
                wallet_address=t.wallet_address,
                timestamp=t.timestamp or datetime.utcnow().isoformat(),
                market_volume_24h=t.market_volume_24h,
                wallet_historical_accuracy=t.wallet_historical_accuracy
            )
            for t in request.trades
        ]

        analysis = service.analyze_multiple_trades(trades)

        if analysis is None:
            raise HTTPException(status_code=500, detail="Batch analysis failed")

        return MultiTradeResponse(
            trade_count=len(trades),
            analysis=analysis
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")


@router.post("/alert/generate", response_model=AlertMessageResponse)
async def generate_alert_message(
    request: AlertMessageRequest,
    service: ClaudeSkillsService = Depends(get_skills_service)
) -> AlertMessageResponse:
    """
    Generate a formatted alert message for a specific notification channel.

    Supports:
    - telegram: Markdown with emojis
    - discord: Embed-friendly formatting
    - slack: mrkdwn formatting
    - email: Plain text structure
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="AI analysis service unavailable. Set ANTHROPIC_API_KEY to enable."
        )

    try:
        trade = WhaleTradeData(
            market_question=request.trade.market_question,
            position=request.trade.position,
            amount_usd=request.trade.amount_usd,
            entry_price=request.trade.entry_price,
            price_before=request.trade.price_before,
            price_after=request.trade.price_after,
            wallet_address=request.trade.wallet_address,
            timestamp=request.trade.timestamp or datetime.utcnow().isoformat()
        )

        message = service.generate_alert_message(trade, request.channel)

        if message is None:
            raise HTTPException(status_code=500, detail="Alert generation failed")

        return AlertMessageResponse(
            channel=request.channel,
            message=message
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Alert generation failed: {str(e)}")
