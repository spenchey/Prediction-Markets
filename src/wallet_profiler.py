"""
Wallet Profiler - On-Chain Wallet Analysis for Whale Detection

This module fetches on-chain data about wallets to enhance whale detection:
1. Transaction count (nonce) - Low nonce = fresh wallet (more suspicious)
2. Balance - Whale indicator
3. Funder inference - Who funded this wallet? (clustering signal)

Based on ChatGPT's pm_whale_tracker_v5 wallet_profiler.py

Works with Polygon network (Polymarket's chain).
"""

from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from loguru import logger

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


# =========================================
# WALLET PROFILE
# =========================================

@dataclass
class WalletOnChainProfile:
    """On-chain profile data for a wallet."""
    wallet: str
    chain_nonce: Optional[int] = None  # Transaction count
    balance_matic: Optional[float] = None  # MATIC balance
    balance_usd: Optional[float] = None  # Estimated USD value
    funder_wallet: Optional[str] = None  # First incoming tx from
    funder_confidence: Optional[float] = None  # How confident we are in funder
    profiled_at: Optional[datetime] = None
    error: Optional[str] = None

    @property
    def is_fresh_wallet(self) -> bool:
        """Wallet has low transaction count (potentially new/purpose-built)."""
        if self.chain_nonce is None:
            return False
        return self.chain_nonce < 10

    @property
    def freshness_score(self) -> float:
        """
        Score based on wallet freshness (0-1).
        Lower nonce = higher score.

        Uses exponential decay: score = exp(-nonce/40)
        - nonce 0: score ~1.0
        - nonce 10: score ~0.78
        - nonce 40: score ~0.37
        - nonce 100: score ~0.08
        """
        if self.chain_nonce is None:
            return 0.0
        import math
        return math.exp(-self.chain_nonce / 40.0)


# =========================================
# WALLET PROFILER
# =========================================

class WalletProfiler:
    """
    Fetches on-chain wallet data from Polygon.

    Two data sources:
    1. Polygon JSON-RPC (free, no API key) - nonce, balance
    2. Polygonscan API (requires key) - funder inference

    Usage:
        profiler = WalletProfiler()

        # Get profile (async)
        profile = await profiler.get_profile("0x...")

        # Batch profile
        profiles = await profiler.batch_profile(["0x...", "0x..."])
    """

    def __init__(
        self,
        polygon_rpc_url: str = "https://polygon-rpc.com",
        polygonscan_api_key: Optional[str] = None,
        cache_ttl_seconds: int = 1800,  # 30 minutes
        timeout_seconds: float = 10.0,
    ):
        self.polygon_rpc_url = polygon_rpc_url
        self.polygonscan_api_key = polygonscan_api_key
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.timeout = timeout_seconds

        # Cache
        self._cache: Dict[str, WalletOnChainProfile] = {}

        # HTTP client (created on first use)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": "PredictionMarketTracker/1.0"}
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _should_refresh(self, profile: Optional[WalletOnChainProfile]) -> bool:
        """Check if cached profile needs refresh."""
        if not profile or not profile.profiled_at:
            return True
        return datetime.now() - profile.profiled_at > self.cache_ttl

    async def get_profile(
        self,
        wallet: str,
        force_refresh: bool = False
    ) -> WalletOnChainProfile:
        """
        Get on-chain profile for a wallet.

        Uses cache unless force_refresh=True or cache expired.
        """
        wallet = wallet.lower()

        # Check cache
        if not force_refresh:
            cached = self._cache.get(wallet)
            if cached and not self._should_refresh(cached):
                return cached

        # Fetch fresh data
        profile = await self._fetch_profile(wallet)
        self._cache[wallet] = profile
        return profile

    async def _fetch_profile(self, wallet: str) -> WalletOnChainProfile:
        """Fetch profile data from chain."""
        profile = WalletOnChainProfile(wallet=wallet)

        try:
            # Fetch nonce and balance from RPC
            nonce, balance = await self._fetch_nonce_balance(wallet)
            profile.chain_nonce = nonce
            profile.balance_matic = balance

            # Estimate USD (rough: 1 MATIC ~= $0.50)
            if balance is not None:
                profile.balance_usd = balance * 0.50

            # Try to infer funder if we have API key
            if self.polygonscan_api_key:
                funder, conf = await self._infer_funder(wallet)
                profile.funder_wallet = funder
                profile.funder_confidence = conf

            profile.profiled_at = datetime.now()

        except Exception as e:
            logger.warning(f"Failed to profile wallet {wallet[:10]}...: {e}")
            profile.error = str(e)
            profile.profiled_at = datetime.now()

        return profile

    async def _fetch_nonce_balance(
        self,
        wallet: str
    ) -> Tuple[Optional[int], Optional[float]]:
        """Fetch nonce and balance via JSON-RPC."""
        client = await self._get_client()

        try:
            # Get transaction count (nonce)
            nonce_resp = await client.post(
                self.polygon_rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_getTransactionCount",
                    "params": [wallet, "latest"]
                }
            )
            nonce_resp.raise_for_status()
            nonce_hex = nonce_resp.json().get("result")
            nonce = int(nonce_hex, 16) if nonce_hex else None

            # Get balance
            balance_resp = await client.post(
                self.polygon_rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_getBalance",
                    "params": [wallet, "latest"]
                }
            )
            balance_resp.raise_for_status()
            balance_hex = balance_resp.json().get("result")
            balance_wei = int(balance_hex, 16) if balance_hex else None
            balance_matic = balance_wei / 1e18 if balance_wei is not None else None

            return nonce, balance_matic

        except Exception as e:
            logger.warning(f"RPC error for {wallet[:10]}...: {e}")
            return None, None

    async def _infer_funder(
        self,
        wallet: str
    ) -> Tuple[Optional[str], Optional[float]]:
        """
        Infer the wallet that funded this address.

        Uses Polygonscan API to find the first incoming transaction.
        This is a strong signal for entity clustering.
        """
        if not self.polygonscan_api_key:
            return None, None

        client = await self._get_client()

        try:
            resp = await client.get(
                "https://api.polygonscan.com/api",
                params={
                    "module": "account",
                    "action": "txlist",
                    "address": wallet,
                    "startblock": 0,
                    "endblock": 99999999,
                    "page": 1,
                    "offset": 20,  # First 20 transactions
                    "sort": "asc",
                    "apikey": self.polygonscan_api_key,
                }
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "1":
                return None, None

            txs = data.get("result") or []

            # Find first incoming transaction with non-zero value
            for tx in txs:
                to_addr = (tx.get("to") or "").lower()
                if to_addr == wallet.lower():
                    from_addr = (tx.get("from") or "").lower()
                    value = int(tx.get("value") or 0)
                    if from_addr and value > 0:
                        # Higher confidence if it's a significant amount
                        conf = 0.6 if value > 1e16 else 0.4  # >0.01 ETH
                        return from_addr, conf

            return None, None

        except Exception as e:
            logger.warning(f"Polygonscan error for {wallet[:10]}...: {e}")
            return None, None

    async def batch_profile(
        self,
        wallets: List[str],
        max_concurrent: int = 5
    ) -> Dict[str, WalletOnChainProfile]:
        """
        Profile multiple wallets concurrently.

        Returns dict mapping wallet -> profile.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def profile_with_limit(wallet: str) -> Tuple[str, WalletOnChainProfile]:
            async with semaphore:
                profile = await self.get_profile(wallet)
                return wallet, profile

        tasks = [profile_with_limit(w) for w in wallets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        profiles: Dict[str, WalletOnChainProfile] = {}
        for result in results:
            if isinstance(result, tuple):
                wallet, profile = result
                profiles[wallet.lower()] = profile
            # Skip exceptions

        return profiles

    def get_cached_profile(self, wallet: str) -> Optional[WalletOnChainProfile]:
        """Get cached profile without fetching (returns None if not cached)."""
        return self._cache.get(wallet.lower())

    def get_stats(self) -> Dict[str, Any]:
        """Get profiler statistics."""
        cached = list(self._cache.values())
        fresh_wallets = [p for p in cached if p.is_fresh_wallet]
        with_funder = [p for p in cached if p.funder_wallet]

        return {
            "cached_profiles": len(self._cache),
            "fresh_wallets": len(fresh_wallets),
            "profiles_with_funder": len(with_funder),
            "polygonscan_enabled": self.polygonscan_api_key is not None,
        }


# =========================================
# TEST
# =========================================

async def main():
    """Test the wallet profiler."""
    print("Testing Wallet Profiler...")

    profiler = WalletProfiler()

    # Test with a known Polymarket wallet
    test_wallet = "0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d"

    print(f"\nProfiling {test_wallet[:15]}...")
    profile = await profiler.get_profile(test_wallet)

    print(f"  Nonce: {profile.chain_nonce}")
    print(f"  Balance: {profile.balance_matic:.4f} MATIC" if profile.balance_matic else "  Balance: Unknown")
    print(f"  Fresh wallet: {profile.is_fresh_wallet}")
    print(f"  Freshness score: {profile.freshness_score:.3f}")
    print(f"  Funder: {profile.funder_wallet or 'Unknown'}")

    print(f"\nStats: {profiler.get_stats()}")

    await profiler.close()


if __name__ == "__main__":
    asyncio.run(main())
