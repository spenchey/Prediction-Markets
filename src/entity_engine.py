"""
Entity Engine - Advanced Wallet Clustering for Whale Detection

This module implements graph-based entity detection to identify:
- Multiple wallets controlled by the same entity
- Coordinated trading activity
- Sophisticated whale behavior patterns

Based on research from:
- ChatGPT's pm_whale_tracker_v5 (Union-Find clustering)
- ChatGPT's pm_whale_tracker_v6 (Market liquidity scaling, stable IDs)
- PolyTrack (cluster detection concept)
- Polymaster (coordination detection)

Key features:
1. Union-Find algorithm for efficient cluster merging
2. Multi-signal edge weighting (funder, time-coupled, market overlap)
3. Edge decay (old connections fade over time)
4. Saturation + caps (diminishing returns per signal)
5. Entity-level scoring (aggregate wallet behavior)
6. Market liquidity scaling (v6) - edges weighted by market activity
7. Stable entity IDs (v6) - IDs persist across rebuilds
"""

from __future__ import annotations
import hashlib
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Deque, Any
from loguru import logger


# =========================================
# UNION-FIND DATA STRUCTURE
# =========================================

class UnionFind:
    """
    Efficient Union-Find (Disjoint Set Union) data structure.

    Used to merge wallets into clusters/entities based on
    detected relationships.
    """

    def __init__(self):
        self.parent: Dict[str, str] = {}
        self.rank: Dict[str, int] = {}

    def find(self, x: str) -> str:
        """Find the root/representative of x's set with path compression."""
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
            return x

        # Path compression
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        """Merge the sets containing a and b (union by rank)."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return

        # Union by rank
        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1

    def connected(self, a: str, b: str) -> bool:
        """Check if a and b are in the same set."""
        return self.find(a) == self.find(b)


# =========================================
# WALLET EDGE (CONNECTION BETWEEN WALLETS)
# =========================================

@dataclass
class WalletEdge:
    """
    Represents a connection between two wallets.

    Multiple signals can contribute to the edge weight:
    - shared_funder: Same wallet funded both
    - time_coupled: Traded same market within short window
    - market_overlap: Similar trading patterns (Jaccard similarity)
    """
    wallet_a: str
    wallet_b: str
    weight: float = 0.0
    evidence: Dict[str, float] = field(default_factory=dict)  # signal -> weight
    evidence_counts: Dict[str, int] = field(default_factory=dict)  # signal -> count
    last_updated: datetime = field(default_factory=datetime.now)

    @staticmethod
    def order_pair(a: str, b: str) -> Tuple[str, str]:
        """Ensure consistent ordering of wallet pairs."""
        return (a, b) if a < b else (b, a)


# =========================================
# ENTITY (CLUSTER OF WALLETS)
# =========================================

@dataclass
class Entity:
    """
    Represents a detected entity (group of related wallets).

    An entity might be:
    - A single trader with multiple wallets
    - A coordinated trading group
    - Related accounts (same funder, similar behavior)
    """
    entity_id: str
    wallets: Set[str] = field(default_factory=set)
    confidence: float = 0.5
    reason: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Aggregate stats
    total_volume_usd: float = 0.0
    total_trades: int = 0
    markets_traded: Set[str] = field(default_factory=set)

    @staticmethod
    def generate_id(wallets: List[str]) -> str:
        """Generate deterministic entity ID from wallet set."""
        sorted_wallets = sorted(set(wallets))
        h = hashlib.sha1("|".join(sorted_wallets).encode()).hexdigest()[:14]
        return f"entity:{h}"

    @property
    def wallet_count(self) -> int:
        return len(self.wallets)


# =========================================
# ENTITY SCORE
# =========================================

@dataclass
class EntityScore:
    """Score result for an entity."""
    score: float  # 0-100
    reasons: Dict[str, Any] = field(default_factory=dict)


def calculate_entity_score(
    *,
    wallet_count: int,
    cash_window: float,
    cash_recent: float,
    cash_prior: float,
    distinct_markets: int,
) -> EntityScore:
    """
    Calculate entity-level whale score (0-100).

    Features:
    - size: total cash in window (saturating log scale)
    - growth: recent vs prior cash flow
    - coordination: number of wallets in entity
    - breadth: distinct markets traded
    """
    reasons: Dict[str, Any] = {}

    def clamp(x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, x))

    # Size: saturating (log-like)
    # $10k -> ~10 pts, $50k -> ~25, $200k -> ~40
    size_pts = 40.0 * clamp(math.log10(max(cash_window, 1.0)) / 6.0, 0.0, 1.0)
    reasons["size"] = {"cash_window": cash_window, "points": size_pts}

    # Growth: if recent >> prior, that's meaningful
    growth_ratio = (cash_recent - cash_prior) / max(cash_prior, 1.0)
    growth_pts = 20.0 * clamp((growth_ratio + 0.5) / 2.5, 0.0, 1.0)
    reasons["growth"] = {
        "cash_recent": cash_recent,
        "cash_prior": cash_prior,
        "growth_ratio": growth_ratio,
        "points": growth_pts
    }

    # Wallet count: 1 wallet => 0, 3 wallets => ~8, 10 wallets => ~18
    wc = max(1, wallet_count)
    wallets_pts = 20.0 * clamp((math.log2(wc) - 0.0) / 3.5, 0.0, 1.0)
    reasons["wallets"] = {"wallet_count": wc, "points": wallets_pts}

    # Market breadth: slight boost if entity appears across multiple markets
    breadth_pts = 10.0 * clamp((distinct_markets - 1) / 6.0, 0.0, 1.0)
    reasons["breadth"] = {"distinct_markets": distinct_markets, "points": breadth_pts}

    total = size_pts + growth_pts + wallets_pts + breadth_pts
    score = clamp(total, 0.0, 100.0)
    reasons["total"] = score

    return EntityScore(score=score, reasons=reasons)


# =========================================
# ENTITY ENGINE
# =========================================

class EntityEngine:
    """
    Main engine for entity detection and clustering.

    Maintains a graph of wallet relationships and periodically
    rebuilds entity clusters using Union-Find.

    Usage:
        engine = EntityEngine()

        # On each trade
        engine.on_trade(wallet, market_id, timestamp, wallet_profile)

        # Get entity for a wallet
        entity = engine.get_entity_for_wallet(wallet)

        # Get all entities
        entities = engine.get_all_entities()
    """

    def __init__(
        self,
        # Timing windows
        coord_window_seconds: int = 300,  # 5 minutes for time-coupled detection
        overlap_lookback_seconds: int = 86400,  # 24h for market overlap
        entity_rebuild_seconds: int = 60,  # Rebuild entities every minute
        edge_halflife_seconds: int = 86400,  # Edge decay half-life (1 day)

        # Signal weights
        edge_funder_weight: float = 0.90,  # Shared funder (strong signal)
        edge_time_couple_inc: float = 0.18,  # Time-coupled trading
        edge_overlap_weight: float = 0.40,  # Market overlap

        # Overlap detection params
        overlap_min_common_markets: int = 3,
        overlap_jaccard_threshold: float = 0.35,

        # Saturation and caps
        edge_saturation_k: float = 0.55,  # Diminishing returns factor
        cap_shared_funder: float = 1.50,
        cap_time_coupled: float = 1.20,
        cap_market_overlap: float = 1.00,

        # Entity threshold
        entity_edge_threshold: float = 0.75,  # Min weight to consider connected

        # Market liquidity scaling (v6)
        market_liquidity_window_seconds: int = 3600,  # 1 hour
        market_liquidity_baseline: float = 50000.0,  # $50k baseline
        market_importance_min_scale: float = 0.35,  # Min scale factor
        market_importance_max_scale: float = 1.25,  # Max scale factor
    ):
        # Config
        self.coord_window = timedelta(seconds=coord_window_seconds)
        self.overlap_lookback = timedelta(seconds=overlap_lookback_seconds)
        self.entity_rebuild_interval = timedelta(seconds=entity_rebuild_seconds)
        self.edge_halflife_seconds = edge_halflife_seconds

        self.edge_funder_weight = edge_funder_weight
        self.edge_time_couple_inc = edge_time_couple_inc
        self.edge_overlap_weight = edge_overlap_weight

        self.overlap_min_common_markets = overlap_min_common_markets
        self.overlap_jaccard_threshold = overlap_jaccard_threshold

        self.edge_saturation_k = edge_saturation_k
        self.cap_shared_funder = cap_shared_funder
        self.cap_time_coupled = cap_time_coupled
        self.cap_market_overlap = cap_market_overlap

        self.entity_edge_threshold = entity_edge_threshold

        # Market liquidity scaling (v6)
        self.market_liquidity_window = timedelta(seconds=market_liquidity_window_seconds)
        self.market_liquidity_baseline = market_liquidity_baseline
        self.market_importance_min_scale = market_importance_min_scale
        self.market_importance_max_scale = market_importance_max_scale

        # State
        self.edges: Dict[Tuple[str, str], WalletEdge] = {}
        self.entities: Dict[str, Entity] = {}
        self.wallet_to_entity: Dict[str, str] = {}
        self._entity_seq: int = 0  # Sequential entity ID counter (v6)

        # Tracking for time-coupled detection
        self._recent_by_market: Dict[str, Deque[Tuple[datetime, str]]] = defaultdict(deque)

        # Tracking for market overlap detection
        self._wallet_markets: Dict[str, Dict[str, datetime]] = defaultdict(dict)
        self._market_wallets: Dict[str, Deque[Tuple[datetime, str]]] = defaultdict(deque)

        # Funder tracking
        self._wallet_funders: Dict[str, str] = {}
        self._funder_wallets: Dict[str, Set[str]] = defaultdict(set)

        # Market volume tracking (v6)
        self._market_trades: Dict[str, Deque[Tuple[datetime, float]]] = defaultdict(deque)

        self._last_rebuild = datetime.now()

    def _decay_factor(self, dt_seconds: float) -> float:
        """Calculate exponential decay factor."""
        if self.edge_halflife_seconds <= 0 or dt_seconds <= 0:
            return 1.0
        return 0.5 ** (dt_seconds / self.edge_halflife_seconds)

    def _clamp(self, x: float, lo: float, hi: float) -> float:
        """Clamp value between lo and hi."""
        return max(lo, min(hi, x))

    def _market_scale(self, market_id: str, timestamp: datetime) -> float:
        """
        Scale edge weights based on market liquidity (v6).

        High liquidity markets => scale down (need more evidence to link wallets)
        Low liquidity markets => scale up (less evidence needed)

        Returns scale factor between market_importance_min_scale and market_importance_max_scale.
        """
        cutoff = timestamp - self.market_liquidity_window
        dq = self._market_trades.get(market_id, deque())

        # Prune old entries
        while dq and dq[0][0] < cutoff:
            dq.popleft()

        # Sum recent volume
        volume = sum(cash for ts, cash in dq)

        # Log-like scaling around baseline
        # baseline => ~1.0; 10x baseline => ~0.5; 0.1x baseline => ~1.2 (capped)
        baseline = max(self.market_liquidity_baseline, 1.0)
        ratio = volume / baseline if baseline > 0 else 0.0
        scale = 1.0 / (1.0 + math.log10(1.0 + max(ratio, 0.0)))

        # Normalize: at ratio=1 => 1/(1+log10(2)) ≈ 0.77; adjust upward
        scale = scale / 0.77

        return self._clamp(scale, self.market_importance_min_scale, self.market_importance_max_scale)

    def _next_entity_id(self) -> str:
        """Generate next sequential entity ID (v6 stable IDs)."""
        self._entity_seq += 1
        return f"ent_{self._entity_seq:06d}"

    def _record_market_trade(self, market_id: str, timestamp: datetime, cash: float) -> None:
        """Record a trade for market volume tracking."""
        self._market_trades[market_id].append((timestamp, cash))

    def _get_or_create_edge(self, wallet_a: str, wallet_b: str) -> WalletEdge:
        """Get or create an edge between two wallets."""
        key = WalletEdge.order_pair(wallet_a, wallet_b)
        if key not in self.edges:
            self.edges[key] = WalletEdge(wallet_a=key[0], wallet_b=key[1])
        return self.edges[key]

    def _add_edge_signal(
        self,
        wallet_a: str,
        wallet_b: str,
        *,
        signal: str,
        base_weight: float,
        cap: float,
        timestamp: datetime,
    ) -> None:
        """
        Add a signal to an edge with saturation and caps.
        """
        if wallet_a == wallet_b:
            return

        edge = self._get_or_create_edge(wallet_a, wallet_b)

        # Apply decay to existing weights
        dt = (timestamp - edge.last_updated).total_seconds()
        decay = self._decay_factor(dt)

        for sig in edge.evidence:
            edge.evidence[sig] *= decay

        # Saturation: diminishing returns
        prev_count = edge.evidence_counts.get(signal, 0)
        saturation = 1.0 / (1.0 + self.edge_saturation_k * prev_count)

        # Cap check
        prev_weight = edge.evidence.get(signal, 0.0)
        remaining = max(0.0, cap - prev_weight)
        add_weight = min(base_weight * saturation, remaining)

        # Update
        edge.evidence[signal] = prev_weight + add_weight
        edge.evidence_counts[signal] = prev_count + 1
        edge.weight = sum(edge.evidence.values())
        edge.last_updated = timestamp

    def set_wallet_funder(self, wallet: str, funder: str) -> None:
        """Register a wallet's funder for shared-funder detection."""
        wallet = wallet.lower()
        funder = funder.lower()
        self._wallet_funders[wallet] = funder
        self._funder_wallets[funder].add(wallet)

    def on_trade(
        self,
        *,
        wallet: str,
        market_id: str,
        timestamp: datetime,
        funder: Optional[str] = None,
        cash: float = 0.0,  # v6: trade amount for volume tracking
    ) -> None:
        """
        Process a trade for entity detection.

        Updates edges based on:
        1. Shared funder (if known)
        2. Time-coupled trading (same market, close timing) - scaled by liquidity
        3. Market overlap (similar trading patterns) - scaled by liquidity
        """
        wallet = wallet.lower()

        # Record trade for market volume tracking (v6)
        if cash > 0:
            self._record_market_trade(market_id, timestamp, cash)

        # Calculate market-based scale factor (v6)
        scale = self._market_scale(market_id, timestamp)

        # 1. Shared funder detection (not market-dependent, no scale)
        if funder:
            self.set_wallet_funder(wallet, funder)

        funder = self._wallet_funders.get(wallet)
        if funder:
            peers = self._funder_wallets.get(funder, set())
            for peer in peers:
                if peer != wallet:
                    self._add_edge_signal(
                        wallet, peer,
                        signal="shared_funder",
                        base_weight=self.edge_funder_weight,
                        cap=self.cap_shared_funder,
                        timestamp=timestamp,
                    )

        # 2. Time-coupled detection
        cutoff = timestamp - self.coord_window
        dq = self._recent_by_market[market_id]

        # Prune old entries
        while dq and dq[0][0] < cutoff:
            dq.popleft()

        # Add edges to recent traders in same market (scaled by liquidity v6)
        for other_ts, other_wallet in dq:
            if other_wallet != wallet:
                self._add_edge_signal(
                    wallet, other_wallet,
                    signal="time_coupled",
                    base_weight=self.edge_time_couple_inc * scale,
                    cap=self.cap_time_coupled,
                    timestamp=timestamp,
                )

        dq.append((timestamp, wallet))

        # 3. Market overlap detection
        overlap_cutoff = timestamp - self.overlap_lookback

        # Update wallet's market set
        self._wallet_markets[wallet][market_id] = timestamp

        # Prune old markets for this wallet
        old_markets = [
            m for m, ts in self._wallet_markets[wallet].items()
            if ts < overlap_cutoff
        ]
        for m in old_markets:
            del self._wallet_markets[wallet][m]

        # Track which wallets traded this market
        market_dq = self._market_wallets[market_id]
        while market_dq and market_dq[0][0] < overlap_cutoff:
            market_dq.popleft()
        market_dq.append((timestamp, wallet))

        # Check for overlapping wallets
        my_markets = self._wallet_markets.get(wallet, {})
        if len(my_markets) >= self.overlap_min_common_markets:
            candidate_common: Dict[str, int] = defaultdict(int)

            for mkt in my_markets:
                mkt_dq = self._market_wallets.get(mkt, deque())
                seen = set()
                for other_ts, other_wallet in mkt_dq:
                    if other_wallet == wallet or other_wallet in seen:
                        continue
                    seen.add(other_wallet)
                    candidate_common[other_wallet] += 1

            my_count = len(my_markets)
            for other_wallet, common in candidate_common.items():
                if common < self.overlap_min_common_markets:
                    continue

                other_markets = self._wallet_markets.get(other_wallet, {})
                other_count = len(other_markets) if other_markets else common
                union = max(1, my_count + other_count - common)
                jaccard = common / union

                if jaccard >= self.overlap_jaccard_threshold:
                    # Scale by market liquidity (v6)
                    add_weight = self.edge_overlap_weight * min(1.0, jaccard / 0.6) * scale
                    self._add_edge_signal(
                        wallet, other_wallet,
                        signal="market_overlap",
                        base_weight=add_weight,
                        cap=self.cap_market_overlap,
                        timestamp=timestamp,
                    )

        # Maybe rebuild entities
        self.maybe_rebuild_entities()

    def maybe_rebuild_entities(self) -> None:
        """Rebuild entities if enough time has passed."""
        now = datetime.now()
        if now - self._last_rebuild < self.entity_rebuild_interval:
            return
        self._last_rebuild = now
        self.rebuild_entities()

    def rebuild_entities(self) -> None:
        """
        Rebuild entity clusters from current edges using Union-Find.

        v6: Uses stable entity IDs - preserves IDs when wallets overlap with
        existing entities. Only generates new IDs for truly new entities.
        """
        now = datetime.now()

        # Collect edges above threshold (with decay applied)
        valid_edges: List[Tuple[str, str, float]] = []

        for (wa, wb), edge in self.edges.items():
            dt = (now - edge.last_updated).total_seconds()
            decay = self._decay_factor(dt)
            decayed_weight = edge.weight * decay

            if decayed_weight >= self.entity_edge_threshold:
                valid_edges.append((wa, wb, decayed_weight))

        # Build clusters with Union-Find
        uf = UnionFind()
        wallets_in_graph: Set[str] = set()

        for wa, wb, w in valid_edges:
            uf.union(wa, wb)
            wallets_in_graph.add(wa)
            wallets_in_graph.add(wb)

        # Group by root
        components: Dict[str, List[str]] = defaultdict(list)
        for w in wallets_in_graph:
            components[uf.find(w)].append(w)

        # v6: Snapshot old wallet->entity mapping BEFORE clearing
        old_wallet_to_entity = dict(self.wallet_to_entity)
        old_entities = dict(self.entities)

        # Clear wallet mappings but keep entity metadata
        self.wallet_to_entity.clear()

        # Determine entity IDs for each component (v6 stable IDs)
        comp_to_entity_id: Dict[str, str] = {}

        for root, wallets in components.items():
            if len(wallets) < 2:
                continue

            # Count how many wallets in this component belong to existing entities
            entity_counts: Dict[str, int] = {}
            for w in wallets:
                old_eid = old_wallet_to_entity.get(w)
                if old_eid:
                    entity_counts[old_eid] = entity_counts.get(old_eid, 0) + 1

            if entity_counts:
                # Pick entity with most overlap (stable ID reuse)
                best_eid = sorted(
                    entity_counts.items(),
                    key=lambda kv: (-kv[1], kv[0])  # Most overlap, then alphabetical
                )[0][0]
                comp_to_entity_id[root] = best_eid
            else:
                # New entity - generate sequential ID
                comp_to_entity_id[root] = self._next_entity_id()

        # Create/update entities
        new_entities: Dict[str, Entity] = {}

        for root, wallets in components.items():
            if len(wallets) < 2:
                continue

            entity_id = comp_to_entity_id[root]
            confidence = min(0.50 + 0.10 * (len(wallets) - 2), 0.95)

            # Preserve created_at if entity existed
            created_at = now
            if entity_id in old_entities:
                created_at = old_entities[entity_id].created_at

            entity = Entity(
                entity_id=entity_id,
                wallets=set(wallets),
                confidence=confidence,
                reason=f"graph_cc_stable: {len(wallets)} wallets, threshold={self.entity_edge_threshold}",
                created_at=created_at,
                updated_at=now,
            )

            new_entities[entity_id] = entity
            for w in wallets:
                self.wallet_to_entity[w] = entity_id

        self.entities = new_entities

        logger.debug(f"Rebuilt {len(self.entities)} entities from {len(valid_edges)} edges (stable IDs)")

    def get_entity_for_wallet(self, wallet: str) -> Optional[Entity]:
        """Get the entity containing this wallet, if any."""
        wallet = wallet.lower()
        entity_id = self.wallet_to_entity.get(wallet)
        return self.entities.get(entity_id) if entity_id else None

    def get_all_entities(self) -> List[Entity]:
        """Get all detected entities."""
        return list(self.entities.values())

    def get_entity_stats(self) -> Dict[str, Any]:
        """Get statistics about entity detection."""
        return {
            "total_entities": len(self.entities),
            "total_edges": len(self.edges),
            "wallets_in_entities": len(self.wallet_to_entity),
            "largest_entity_size": max(
                (e.wallet_count for e in self.entities.values()),
                default=0
            ),
            "entities_by_size": {
                "2_wallets": len([e for e in self.entities.values() if e.wallet_count == 2]),
                "3_5_wallets": len([e for e in self.entities.values() if 3 <= e.wallet_count <= 5]),
                "6_plus_wallets": len([e for e in self.entities.values() if e.wallet_count >= 6]),
            }
        }

    def get_edge_details(self, wallet_a: str, wallet_b: str) -> Optional[Dict[str, Any]]:
        """Get detailed edge information between two wallets."""
        key = WalletEdge.order_pair(wallet_a.lower(), wallet_b.lower())
        edge = self.edges.get(key)
        if not edge:
            return None

        return {
            "wallet_a": edge.wallet_a,
            "wallet_b": edge.wallet_b,
            "weight": edge.weight,
            "evidence": edge.evidence,
            "counts": edge.evidence_counts,
            "last_updated": edge.last_updated.isoformat(),
        }


# =========================================
# TEST
# =========================================

if __name__ == "__main__":
    print("Testing Entity Engine...")

    engine = EntityEngine(
        coord_window_seconds=60,
        entity_rebuild_seconds=1,
        entity_edge_threshold=0.3,  # Lower for testing
    )

    # Simulate trades from related wallets
    now = datetime.now()

    # Set up shared funder
    engine.set_wallet_funder("0xwallet1", "0xfunder_a")
    engine.set_wallet_funder("0xwallet2", "0xfunder_a")
    engine.set_wallet_funder("0xwallet3", "0xfunder_a")

    # Wallets 1-3 trade same market close together (shared funder + time coupled)
    engine.on_trade(wallet="0xwallet1", market_id="market_btc", timestamp=now)
    engine.on_trade(wallet="0xwallet2", market_id="market_btc", timestamp=now + timedelta(seconds=10))
    engine.on_trade(wallet="0xwallet3", market_id="market_btc", timestamp=now + timedelta(seconds=20))

    # Wallet 4 trades independently
    engine.on_trade(wallet="0xwallet4", market_id="market_eth", timestamp=now)

    # Force rebuild
    engine.rebuild_entities()

    print(f"\nEntities detected: {len(engine.entities)}")
    for entity in engine.entities.values():
        print(f"  {entity.entity_id}: {entity.wallets} (confidence: {entity.confidence:.2f})")

    print(f"\nStats: {engine.get_entity_stats()}")

    # Check entity for wallet
    entity = engine.get_entity_for_wallet("0xwallet1")
    if entity:
        print(f"\nWallet1's entity: {entity.entity_id} with {entity.wallet_count} wallets")
