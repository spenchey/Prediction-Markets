"""
Test Suite for Whale Detector Module

Following TDD principles from Superpowers:
- Each test verifies one specific behavior
- Tests are named to describe expected behavior
- Real objects used (mocks only when unavoidable)

Alert Types Tested:
1. WHALE_TRADE - Large trades above threshold
2. UNUSUAL_SIZE - Statistically abnormal trades
3. MARKET_ANOMALY - Unusual for specific market
4. NEW_WALLET - First-time traders with large bets
5. FOCUSED_WALLET - Wallets concentrated in few markets
6. SMART_MONEY - High win rate wallets
"""
import pytest
from datetime import datetime, timedelta
from typing import List

# Import the modules we're testing
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.whale_detector import (
    WhaleDetector,
    WhaleAlert,
    WalletProfile,
    TradeMonitor,
    is_sports_market,
    severity_to_score,
    score_to_severity,
    SPORTS_KEYWORDS,
)
from src.polymarket_client import Trade


# =========================================
# TEST FIXTURES
# =========================================

def create_trade(
    trade_id: str = "test_trade_1",
    market_id: str = "market_1",
    trader_address: str = "0x1234567890abcdef",
    outcome: str = "Yes",
    side: str = "buy",
    amount_usd: float = 1000.0,
    timestamp: datetime = None
) -> Trade:
    """Factory function to create test trades."""
    return Trade(
        id=trade_id,
        market_id=market_id,
        trader_address=trader_address,
        outcome=outcome,
        side=side,
        size=amount_usd,  # Simplified: size = amount
        price=1.0,
        amount_usd=amount_usd,
        timestamp=timestamp or datetime.now(),
        transaction_hash=f"0x{trade_id}"
    )


def create_detector(
    whale_threshold: float = 10000,
    new_wallet_threshold: float = 1000,
    focused_wallet_threshold: float = 5000,
    std_multiplier: float = 3.0,
    exclude_sports: bool = True
) -> WhaleDetector:
    """Factory function to create detector with custom settings."""
    return WhaleDetector(
        whale_threshold_usd=whale_threshold,
        new_wallet_threshold_usd=new_wallet_threshold,
        focused_wallet_threshold_usd=focused_wallet_threshold,
        std_multiplier=std_multiplier,
        exclude_sports=exclude_sports
    )


# =========================================
# SPORTS FILTERING TESTS
# =========================================

class TestSportsFiltering:
    """Tests for sports market detection and filtering."""

    def test_detects_nfl_market_as_sports(self):
        """NFL-related markets should be identified as sports."""
        assert is_sports_market("Will the NFL season start on time?") == True
        assert is_sports_market("Super Bowl winner 2025") == True

    def test_detects_nba_market_as_sports(self):
        """NBA-related markets should be identified as sports."""
        assert is_sports_market("NBA MVP 2025") == True
        assert is_sports_market("Will the Lakers win the championship?") == True

    def test_detects_soccer_market_as_sports(self):
        """Soccer/football markets should be identified as sports."""
        assert is_sports_market("Premier League winner") == True
        assert is_sports_market("Champions League final") == True

    def test_non_sports_market_not_flagged(self):
        """Political and crypto markets should NOT be flagged as sports."""
        assert is_sports_market("Will Biden win 2024 election?") == False
        assert is_sports_market("Bitcoin above $100k by December?") == False
        assert is_sports_market("Will the Fed raise rates?") == False

    def test_empty_question_returns_false(self):
        """Empty or None questions should return False."""
        assert is_sports_market("") == False
        assert is_sports_market(None) == False

    def test_case_insensitive_detection(self):
        """Sports detection should be case insensitive."""
        assert is_sports_market("NFL playoffs") == True
        assert is_sports_market("nfl playoffs") == True
        assert is_sports_market("Nfl Playoffs") == True

    @pytest.mark.asyncio
    async def test_detector_skips_sports_markets(self):
        """Detector should skip sports markets when exclude_sports=True."""
        detector = create_detector(whale_threshold=100, exclude_sports=True)
        trade = create_trade(amount_usd=50000)  # Whale-sized trade

        # Sports market should produce no alerts
        alerts = await detector.analyze_trade(trade, "NFL Super Bowl winner")
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_detector_includes_sports_when_disabled(self):
        """Detector should include sports markets when exclude_sports=False."""
        detector = create_detector(whale_threshold=100, exclude_sports=False)
        trade = create_trade(amount_usd=50000)

        # Sports market should produce alerts when filtering disabled
        alerts = await detector.analyze_trade(trade, "NFL Super Bowl winner")
        assert len(alerts) > 0


# =========================================
# WHALE TRADE ALERT TESTS
# =========================================

class TestWhaleTrade:
    """Tests for WHALE_TRADE alert detection."""

    @pytest.mark.asyncio
    async def test_detects_trade_above_threshold(self):
        """Trade above threshold should trigger WHALE_TRADE alert."""
        detector = create_detector(whale_threshold=10000)
        trade = create_trade(amount_usd=15000)

        alerts = await detector.analyze_trade(trade, "Bitcoin price prediction")

        whale_alerts = [a for a in alerts if a.alert_type == "WHALE_TRADE"]
        assert len(whale_alerts) == 1
        assert whale_alerts[0].trade.amount_usd == 15000

    @pytest.mark.asyncio
    async def test_no_alert_below_threshold(self):
        """Trade below threshold should NOT trigger WHALE_TRADE alert."""
        detector = create_detector(whale_threshold=10000)
        trade = create_trade(amount_usd=5000)

        alerts = await detector.analyze_trade(trade, "Bitcoin price prediction")

        whale_alerts = [a for a in alerts if a.alert_type == "WHALE_TRADE"]
        assert len(whale_alerts) == 0

    @pytest.mark.asyncio
    async def test_exact_threshold_triggers_alert(self):
        """Trade exactly at threshold should trigger alert."""
        detector = create_detector(whale_threshold=10000)
        trade = create_trade(amount_usd=10000)

        alerts = await detector.analyze_trade(trade, "Bitcoin price prediction")

        whale_alerts = [a for a in alerts if a.alert_type == "WHALE_TRADE"]
        assert len(whale_alerts) == 1

    @pytest.mark.asyncio
    async def test_high_severity_for_large_whale(self):
        """Very large trades should get HIGH severity."""
        detector = create_detector(whale_threshold=10000)
        trade = create_trade(amount_usd=100000)

        alerts = await detector.analyze_trade(trade, "Bitcoin price prediction")

        whale_alerts = [a for a in alerts if a.alert_type == "WHALE_TRADE"]
        assert whale_alerts[0].severity == "HIGH"
        assert whale_alerts[0].severity_score >= 8


# =========================================
# NEW WALLET ALERT TESTS
# =========================================

class TestNewWallet:
    """Tests for NEW_WALLET alert detection."""

    @pytest.mark.asyncio
    async def test_detects_new_wallet_large_trade(self):
        """New wallet making significant trade should trigger alert."""
        detector = create_detector(new_wallet_threshold=1000)
        trade = create_trade(
            trader_address="0xnewwallet123",
            amount_usd=5000
        )

        alerts = await detector.analyze_trade(trade, "Political market")

        new_wallet_alerts = [a for a in alerts if a.alert_type == "NEW_WALLET"]
        assert len(new_wallet_alerts) == 1

    @pytest.mark.asyncio
    async def test_no_alert_for_small_new_wallet_trade(self):
        """New wallet making small trade should NOT trigger alert."""
        detector = create_detector(new_wallet_threshold=1000)
        trade = create_trade(
            trader_address="0xnewwallet456",
            amount_usd=500
        )

        alerts = await detector.analyze_trade(trade, "Political market")

        new_wallet_alerts = [a for a in alerts if a.alert_type == "NEW_WALLET"]
        assert len(new_wallet_alerts) == 0

    @pytest.mark.asyncio
    async def test_established_wallet_not_flagged_as_new(self):
        """Wallet with 5+ trades should NOT be flagged as new."""
        detector = create_detector(new_wallet_threshold=1000)
        address = "0xestablishedwallet"

        # Make 5 trades to establish the wallet
        for i in range(5):
            trade = create_trade(
                trade_id=f"trade_{i}",
                trader_address=address,
                amount_usd=100
            )
            await detector.analyze_trade(trade, "Market")

        # Now make a large trade - should NOT trigger NEW_WALLET
        large_trade = create_trade(
            trade_id="trade_large",
            trader_address=address,
            amount_usd=5000
        )
        alerts = await detector.analyze_trade(large_trade, "Market")

        new_wallet_alerts = [a for a in alerts if a.alert_type == "NEW_WALLET"]
        assert len(new_wallet_alerts) == 0


# =========================================
# FOCUSED WALLET ALERT TESTS
# =========================================

class TestFocusedWallet:
    """Tests for FOCUSED_WALLET alert detection."""

    @pytest.mark.asyncio
    async def test_detects_focused_wallet(self):
        """Wallet with 5+ trades in <=3 markets should be focused."""
        detector = create_detector(focused_wallet_threshold=5000)
        address = "0xfocusedwallet"

        # Make 5 trades in same market
        for i in range(5):
            trade = create_trade(
                trade_id=f"focus_trade_{i}",
                trader_address=address,
                market_id="single_market",
                amount_usd=100
            )
            await detector.analyze_trade(trade, "Single Market Question")

        # Now make a large trade - should trigger FOCUSED_WALLET
        large_trade = create_trade(
            trade_id="focus_trade_large",
            trader_address=address,
            market_id="single_market",
            amount_usd=10000
        )
        alerts = await detector.analyze_trade(large_trade, "Single Market Question")

        focused_alerts = [a for a in alerts if a.alert_type == "FOCUSED_WALLET"]
        assert len(focused_alerts) == 1

    @pytest.mark.asyncio
    async def test_diversified_wallet_not_focused(self):
        """Wallet trading in many markets should NOT be flagged as focused."""
        detector = create_detector(focused_wallet_threshold=5000)
        address = "0xdiversifiedwallet"

        # Make trades in 10 different markets
        for i in range(10):
            trade = create_trade(
                trade_id=f"diverse_trade_{i}",
                trader_address=address,
                market_id=f"market_{i}",
                amount_usd=100
            )
            await detector.analyze_trade(trade, f"Market {i}")

        # Large trade should NOT trigger FOCUSED_WALLET
        large_trade = create_trade(
            trade_id="diverse_trade_large",
            trader_address=address,
            market_id="market_0",
            amount_usd=10000
        )
        alerts = await detector.analyze_trade(large_trade, "Market 0")

        focused_alerts = [a for a in alerts if a.alert_type == "FOCUSED_WALLET"]
        assert len(focused_alerts) == 0


# =========================================
# STATISTICAL ANOMALY TESTS
# =========================================

class TestStatisticalAnomaly:
    """Tests for UNUSUAL_SIZE and MARKET_ANOMALY detection."""

    @pytest.mark.asyncio
    async def test_unusual_size_after_baseline(self):
        """Trade >3 std devs above mean should trigger UNUSUAL_SIZE."""
        detector = create_detector(
            whale_threshold=100000,  # High threshold so WHALE doesn't trigger
            std_multiplier=3.0,
            min_trades_for_stats=10
        )

        # Build baseline with small trades
        for i in range(100):
            trade = create_trade(
                trade_id=f"baseline_{i}",
                trader_address=f"0xtrader_{i}",
                amount_usd=100  # Small trades
            )
            await detector.analyze_trade(trade, "Market")

        # Now a trade that's way above average
        unusual_trade = create_trade(
            trade_id="unusual_trade",
            trader_address="0xunusualtrader",
            amount_usd=5000  # 50x the baseline
        )
        alerts = await detector.analyze_trade(unusual_trade, "Market")

        unusual_alerts = [a for a in alerts if a.alert_type == "UNUSUAL_SIZE"]
        assert len(unusual_alerts) == 1

    @pytest.mark.asyncio
    async def test_market_anomaly_detection(self):
        """Trade unusual for specific market should trigger MARKET_ANOMALY."""
        detector = create_detector(
            whale_threshold=100000,
            std_multiplier=3.0,
            min_trades_for_stats=10
        )

        # Build baseline for specific market
        for i in range(25):
            trade = create_trade(
                trade_id=f"market_baseline_{i}",
                trader_address=f"0xtrader_{i}",
                market_id="specific_market",
                amount_usd=100
            )
            await detector.analyze_trade(trade, "Specific Market")

        # Unusual trade for THIS market
        anomaly_trade = create_trade(
            trade_id="anomaly_trade",
            trader_address="0xanomalytrader",
            market_id="specific_market",
            amount_usd=5000
        )
        alerts = await detector.analyze_trade(anomaly_trade, "Specific Market")

        anomaly_alerts = [a for a in alerts if a.alert_type == "MARKET_ANOMALY"]
        assert len(anomaly_alerts) == 1


# =========================================
# SMART MONEY TESTS
# =========================================

class TestSmartMoney:
    """Tests for SMART_MONEY alert detection."""

    @pytest.mark.asyncio
    async def test_smart_money_detection(self):
        """Wallet with high win rate should trigger SMART_MONEY alert."""
        detector = create_detector()
        address = "0xsmartmoney"

        # First establish the wallet
        for i in range(5):
            trade = create_trade(
                trade_id=f"smart_setup_{i}",
                trader_address=address,
                amount_usd=10000
            )
            await detector.analyze_trade(trade, "Market")

        # Manually set win rate (simulating resolved markets)
        profile = detector.wallet_profiles[address]
        profile.winning_trades = 15
        profile.losing_trades = 5  # 75% win rate
        profile.total_volume_usd = 100000

        # New trade from smart money wallet
        smart_trade = create_trade(
            trade_id="smart_trade",
            trader_address=address,
            amount_usd=1000
        )
        alerts = await detector.analyze_trade(smart_trade, "New Market")

        smart_alerts = [a for a in alerts if a.alert_type == "SMART_MONEY"]
        assert len(smart_alerts) == 1
        assert smart_alerts[0].severity == "HIGH"


# =========================================
# WALLET PROFILE TESTS
# =========================================

class TestWalletProfile:
    """Tests for WalletProfile properties."""

    def test_new_wallet_with_few_trades(self):
        """Wallet with <5 trades should be marked as new."""
        profile = WalletProfile(address="0xtest", total_trades=3)
        assert profile.is_new_wallet == True

    def test_established_wallet(self):
        """Wallet with >=5 trades should NOT be marked as new."""
        profile = WalletProfile(address="0xtest", total_trades=5)
        assert profile.is_new_wallet == False

    def test_whale_wallet_by_volume(self):
        """Wallet with >$100k volume should be marked as whale."""
        profile = WalletProfile(address="0xtest", total_volume_usd=150000)
        assert profile.is_whale == True

    def test_non_whale_wallet(self):
        """Wallet with <$100k volume should NOT be marked as whale."""
        profile = WalletProfile(address="0xtest", total_volume_usd=50000)
        assert profile.is_whale == False

    def test_focused_wallet_detection(self):
        """Wallet in <=3 markets with 5+ trades should be focused."""
        profile = WalletProfile(
            address="0xtest",
            total_trades=10,
            markets_traded={"market1", "market2"}
        )
        assert profile.is_focused == True

    def test_diversified_wallet_not_focused(self):
        """Wallet in >3 markets should NOT be focused."""
        profile = WalletProfile(
            address="0xtest",
            total_trades=10,
            markets_traded={"m1", "m2", "m3", "m4", "m5"}
        )
        assert profile.is_focused == False

    def test_win_rate_calculation(self):
        """Win rate should be calculated correctly."""
        profile = WalletProfile(
            address="0xtest",
            winning_trades=7,
            losing_trades=3
        )
        assert profile.win_rate == 0.7

    def test_win_rate_none_with_few_trades(self):
        """Win rate should be None with <10 resolved trades."""
        profile = WalletProfile(
            address="0xtest",
            winning_trades=3,
            losing_trades=2
        )
        assert profile.win_rate is None

    def test_smart_money_classification(self):
        """Wallet meeting smart money criteria should be flagged."""
        profile = WalletProfile(
            address="0xtest",
            total_volume_usd=100000,
            winning_trades=15,
            losing_trades=5  # 75% win rate
        )
        assert profile.is_smart_money == True


# =========================================
# SEVERITY SCORING TESTS
# =========================================

class TestSeverityScoring:
    """Tests for severity scoring system."""

    def test_severity_to_score_conversion(self):
        """Categorical severity should convert to numeric score."""
        assert severity_to_score("LOW") == 3
        assert severity_to_score("MEDIUM") == 6
        assert severity_to_score("HIGH") == 9

    def test_score_to_severity_conversion(self):
        """Numeric score should convert to categorical severity."""
        assert score_to_severity(1) == "LOW"
        assert score_to_severity(3) == "LOW"
        assert score_to_severity(4) == "MEDIUM"
        assert score_to_severity(6) == "MEDIUM"
        assert score_to_severity(7) == "HIGH"
        assert score_to_severity(10) == "HIGH"

    @pytest.mark.asyncio
    async def test_alert_has_both_severity_types(self):
        """Alerts should have both categorical and numeric severity."""
        detector = create_detector(whale_threshold=1000)
        trade = create_trade(amount_usd=5000)

        alerts = await detector.analyze_trade(trade, "Market")

        assert len(alerts) > 0
        alert = alerts[0]
        assert hasattr(alert, 'severity')  # Categorical
        assert hasattr(alert, 'severity_score')  # Numeric
        assert alert.severity in ["LOW", "MEDIUM", "HIGH"]
        assert 1 <= alert.severity_score <= 10


# =========================================
# MULTIPLE ALERTS PER TRADE TESTS
# =========================================

class TestMultipleAlerts:
    """Tests for scenarios that trigger multiple alert types."""

    @pytest.mark.asyncio
    async def test_new_wallet_whale_triggers_both(self):
        """New wallet making whale trade should trigger both alerts."""
        detector = create_detector(
            whale_threshold=5000,
            new_wallet_threshold=1000
        )

        trade = create_trade(
            trader_address="0xbrandnewwhale",
            amount_usd=50000
        )

        alerts = await detector.analyze_trade(trade, "Market")

        alert_types = {a.alert_type for a in alerts}
        assert "WHALE_TRADE" in alert_types
        assert "NEW_WALLET" in alert_types


# =========================================
# ALERT CONTENT TESTS
# =========================================

class TestAlertContent:
    """Tests for alert message content and metadata."""

    @pytest.mark.asyncio
    async def test_alert_contains_trade_info(self):
        """Alert should contain trade information."""
        detector = create_detector(whale_threshold=1000)
        trade = create_trade(
            amount_usd=5000,
            trader_address="0xtesttrader",
            outcome="Yes"
        )

        alerts = await detector.analyze_trade(trade, "Test Market")

        assert len(alerts) > 0
        alert = alerts[0]
        assert alert.trade.amount_usd == 5000
        assert alert.trade.trader_address == "0xtesttrader"

    @pytest.mark.asyncio
    async def test_alert_contains_market_question(self):
        """Alert should contain market question when provided."""
        detector = create_detector(whale_threshold=1000)
        trade = create_trade(amount_usd=5000)

        alerts = await detector.analyze_trade(trade, "Will Bitcoin reach $100k?")

        assert len(alerts) > 0
        assert alerts[0].market_question == "Will Bitcoin reach $100k?"

    @pytest.mark.asyncio
    async def test_alert_to_dict_serialization(self):
        """Alert should serialize to dictionary correctly."""
        detector = create_detector(whale_threshold=1000)
        trade = create_trade(amount_usd=5000)

        alerts = await detector.analyze_trade(trade, "Market")

        assert len(alerts) > 0
        alert_dict = alerts[0].to_dict()

        assert "id" in alert_dict
        assert "alert_type" in alert_dict
        assert "severity" in alert_dict
        assert "severity_score" in alert_dict
        assert "trade_amount_usd" in alert_dict
        assert "trader_address" in alert_dict


# =========================================
# DETECTOR STATE TESTS
# =========================================

class TestDetectorState:
    """Tests for detector state management."""

    @pytest.mark.asyncio
    async def test_wallet_profiles_accumulate(self):
        """Detector should accumulate wallet profiles over time."""
        detector = create_detector()

        for i in range(5):
            trade = create_trade(
                trade_id=f"state_trade_{i}",
                trader_address="0xsametrader",
                amount_usd=100
            )
            await detector.analyze_trade(trade, "Market")

        profile = detector.wallet_profiles.get("0xsametrader")
        assert profile is not None
        assert profile.total_trades == 5
        assert profile.total_volume_usd == 500

    @pytest.mark.asyncio
    async def test_get_top_wallets(self):
        """Should return top wallets sorted by volume."""
        detector = create_detector()

        # Create wallets with different volumes
        for i, volume in enumerate([1000, 5000, 3000]):
            for j in range(3):
                trade = create_trade(
                    trade_id=f"vol_trade_{i}_{j}",
                    trader_address=f"0xwallet_{i}",
                    amount_usd=volume / 3
                )
                await detector.analyze_trade(trade, "Market")

        top_wallets = detector.get_top_wallets(limit=3)

        assert len(top_wallets) == 3
        # Should be sorted by volume descending
        assert top_wallets[0].total_volume_usd >= top_wallets[1].total_volume_usd
        assert top_wallets[1].total_volume_usd >= top_wallets[2].total_volume_usd


# =========================================
# RUN TESTS
# =========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
