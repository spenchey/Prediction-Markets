"""
Claude Skills API Integration for Prediction Markets Whale Tracker

This service integrates Claude's Skills API to provide AI-powered analysis
of whale trades and market movements.
"""

import os
from typing import Optional
from dataclasses import dataclass
from anthropic import Anthropic
from loguru import logger


@dataclass
class WhaleTradeData:
    """Data structure for whale trade information."""
    market_question: str
    position: str  # "YES" or "NO"
    amount_usd: float
    entry_price: float
    price_before: float
    price_after: float
    wallet_address: str
    timestamp: str
    market_volume_24h: Optional[float] = None
    wallet_historical_accuracy: Optional[float] = None


@dataclass
class WhaleAnalysis:
    """AI-generated whale trade analysis."""
    summary: str
    smart_money_signal: str  # "Bullish", "Bearish", "Neutral"
    confidence: str  # "High", "Medium", "Low"
    key_insight: str
    full_analysis: str


class ClaudeSkillsService:
    """
    Service for analyzing whale trades using Claude's Skills API.

    Uses a custom prediction-markets-analyst skill to generate
    intelligent insights about large trades.
    """

    SKILLS_BETA = "skills-2025-10-02"

    def __init__(self, api_key: Optional[str] = None, custom_skill_id: Optional[str] = None):
        """
        Initialize the Claude Skills service.

        Args:
            api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
            custom_skill_id: Optional custom skill ID if you've uploaded your own skill.
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = None
        self.custom_skill_id = custom_skill_id
        self.model = "claude-sonnet-4-5-20250929"

        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
            logger.info("Claude Skills service initialized")
        else:
            logger.warning("ANTHROPIC_API_KEY not set - Claude Skills service disabled")

    def is_available(self) -> bool:
        """Check if the service is available."""
        return self.client is not None

    def analyze_whale_trade(self, trade: WhaleTradeData) -> Optional[WhaleAnalysis]:
        """
        Analyze a whale trade using Claude with the prediction markets skill.

        Args:
            trade: WhaleTradeData object containing trade details.

        Returns:
            WhaleAnalysis object with AI-generated insights, or None if service unavailable.
        """
        if not self.is_available():
            logger.warning("Claude Skills service not available")
            return None

        try:
            prompt = self._build_analysis_prompt(trade)
            skills_config = self._get_skills_config()

            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=2048,
                betas=[self.SKILLS_BETA],
                system=self._get_system_prompt(),
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                **skills_config
            )

            return self._parse_response(response)
        except Exception as e:
            logger.error(f"Claude analysis failed: {e}")
            return None

    def analyze_multiple_trades(self, trades: list[WhaleTradeData]) -> Optional[str]:
        """
        Analyze multiple whale trades for patterns and correlations.

        Args:
            trades: List of WhaleTradeData objects.

        Returns:
            String containing pattern analysis, or None if service unavailable.
        """
        if not self.is_available():
            return None

        try:
            prompt = self._build_multi_trade_prompt(trades)

            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=4096,
                betas=[self.SKILLS_BETA],
                system=self._get_system_prompt(),
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                **self._get_skills_config()
            )

            return self._extract_text(response)
        except Exception as e:
            logger.error(f"Claude batch analysis failed: {e}")
            return None

    def generate_alert_message(
        self,
        trade: WhaleTradeData,
        channel: str = "telegram"
    ) -> Optional[str]:
        """
        Generate a formatted alert message for a specific notification channel.

        Args:
            trade: WhaleTradeData object.
            channel: Notification channel ("telegram", "discord", "slack", "email").

        Returns:
            Formatted alert message string, or None if service unavailable.
        """
        if not self.is_available():
            return None

        try:
            prompt = f"""Generate a {channel} alert message for this whale trade:

Market: {trade.market_question}
Position: {trade.position}
Size: ${trade.amount_usd:,.2f}
Entry Price: ${trade.entry_price:.2f}
Price Impact: {trade.price_before:.2f}c → {trade.price_after:.2f}c

Format the message appropriately for {channel}:
- Telegram: Use markdown, emojis, keep concise
- Discord: Use embeds-friendly formatting with clear sections
- Slack: Use mrkdwn formatting
- Email: Use plain text with clear structure

Include a brief 1-2 sentence analysis of why this trade is significant."""

            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=1024,
                betas=[self.SKILLS_BETA],
                system=self._get_system_prompt(),
                messages=[{"role": "user", "content": prompt}],
                **self._get_skills_config()
            )

            return self._extract_text(response)
        except Exception as e:
            logger.error(f"Claude alert generation failed: {e}")
            return None

    def _get_skills_config(self) -> dict:
        """Get the skills configuration for API calls."""
        if self.custom_skill_id:
            return {
                "container": {
                    "skills": [{
                        "type": "custom",
                        "skill_id": self.custom_skill_id,
                        "version": "latest"
                    }]
                }
            }
        return {}

    def _get_system_prompt(self) -> str:
        """Get the system prompt with skill instructions embedded."""
        return """You are an expert prediction markets analyst specializing in whale trade detection and market analysis. You help users understand significant trading activity on prediction markets like Polymarket.

When analyzing whale trades, consider:
1. Trade size relative to market volume
2. Timing and market conditions
3. Price impact and direction
4. Historical wallet performance if available

Always provide actionable insights and clear signal assessments (Bullish/Bearish/Neutral) with confidence levels (High/Medium/Low)."""

    def _build_analysis_prompt(self, trade: WhaleTradeData) -> str:
        """Build the analysis prompt for a single trade."""
        price_change = trade.price_after - trade.price_before
        price_change_pct = (price_change / trade.price_before) * 100 if trade.price_before > 0 else 0

        prompt = f"""Analyze this whale trade:

**Trade Details:**
- Market: {trade.market_question}
- Position: {trade.position}
- Size: ${trade.amount_usd:,.2f}
- Entry Price: ${trade.entry_price:.2f}
- Price Impact: {trade.price_before:.2f}c → {trade.price_after:.2f}c ({price_change_pct:+.1f}%)
- Timestamp: {trade.timestamp}
- Wallet: {trade.wallet_address[:10]}...{trade.wallet_address[-6:]}"""

        if trade.market_volume_24h:
            pct_of_volume = (trade.amount_usd / trade.market_volume_24h) * 100
            prompt += f"\n- 24h Market Volume: ${trade.market_volume_24h:,.2f} (this trade = {pct_of_volume:.1f}%)"

        if trade.wallet_historical_accuracy:
            prompt += f"\n- Wallet Historical Accuracy: {trade.wallet_historical_accuracy:.1f}%"

        prompt += """

Provide your analysis in this format:
1. A 2-3 sentence summary
2. Smart Money Signal (Bullish/Bearish/Neutral)
3. Confidence Level (High/Medium/Low)
4. One key actionable insight"""

        return prompt

    def _build_multi_trade_prompt(self, trades: list[WhaleTradeData]) -> str:
        """Build prompt for analyzing multiple trades."""
        trades_text = "\n\n".join([
            f"Trade {i+1}:\n- Market: {t.market_question}\n- Position: {t.position}\n- Size: ${t.amount_usd:,.2f}\n- Time: {t.timestamp}"
            for i, t in enumerate(trades)
        ])

        return f"""Analyze these {len(trades)} whale trades for patterns and correlations:

{trades_text}

Look for:
1. Common themes or related markets
2. Coordinated trading patterns
3. Smart money directional bias
4. Any concerning or noteworthy patterns

Provide a summary of overall market sentiment based on this whale activity."""

    def _parse_response(self, response) -> WhaleAnalysis:
        """Parse the API response into a WhaleAnalysis object."""
        text = self._extract_text(response)

        summary = text[:200] if len(text) > 200 else text
        signal = "Neutral"
        confidence = "Medium"
        insight = ""

        lines = text.split('\n')
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if 'smart money signal' in line_lower:
                if 'bullish' in line_lower:
                    signal = "Bullish"
                elif 'bearish' in line_lower:
                    signal = "Bearish"
            elif 'confidence' in line_lower:
                if 'high' in line_lower:
                    confidence = "High"
                elif 'low' in line_lower:
                    confidence = "Low"
            elif 'key insight' in line_lower or 'actionable' in line_lower:
                if ':' in line:
                    insight = line.split(':', 1)[1].strip()
                elif i + 1 < len(lines):
                    insight = lines[i + 1].strip()

        return WhaleAnalysis(
            summary=summary,
            smart_money_signal=signal,
            confidence=confidence,
            key_insight=insight or summary[:100],
            full_analysis=text
        )

    def _extract_text(self, response) -> str:
        """Extract text content from API response."""
        for block in response.content:
            if hasattr(block, 'text'):
                return block.text
        return ""


def analyze_whale_trade(
    market: str,
    position: str,
    amount: float,
    price: float,
    price_before: float,
    price_after: float,
    wallet: str,
    timestamp: str,
    api_key: Optional[str] = None
) -> Optional[WhaleAnalysis]:
    """
    Quick function to analyze a single whale trade.

    Example:
        analysis = analyze_whale_trade(
            market="Will Trump win 2024 election?",
            position="YES",
            amount=100000,
            price=0.52,
            price_before=0.50,
            price_after=0.54,
            wallet="0x1234...abcd",
            timestamp="2024-11-01T14:30:00Z"
        )
        if analysis:
            print(analysis.smart_money_signal)  # "Bullish"
    """
    service = ClaudeSkillsService(api_key=api_key)
    trade = WhaleTradeData(
        market_question=market,
        position=position,
        amount_usd=amount,
        entry_price=price,
        price_before=price_before,
        price_after=price_after,
        wallet_address=wallet,
        timestamp=timestamp
    )
    return service.analyze_whale_trade(trade)
