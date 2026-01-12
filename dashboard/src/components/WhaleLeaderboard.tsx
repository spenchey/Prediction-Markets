'use client'

import { Trophy, TrendingUp, ExternalLink } from 'lucide-react'

interface Wallet {
  address: string
  total_trades: number
  total_volume_usd: number
  is_whale: boolean
  is_new: boolean
  markets_traded: number
}

interface WhaleLeaderboardProps {
  wallets: Wallet[]
}

export default function WhaleLeaderboard({ wallets }: WhaleLeaderboardProps) {
  const formatVolume = (volume: number) => {
    if (volume >= 1000000) return `$${(volume / 1000000).toFixed(1)}M`
    if (volume >= 1000) return `$${(volume / 1000).toFixed(1)}K`
    return `$${volume.toFixed(0)}`
  }

  const getRankBadge = (index: number) => {
    if (index === 0) return { emoji: '🥇', color: 'text-yellow-400' }
    if (index === 1) return { emoji: '🥈', color: 'text-slate-300' }
    if (index === 2) return { emoji: '🥉', color: 'text-amber-600' }
    return { emoji: `#${index + 1}`, color: 'text-slate-500' }
  }

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700 flex items-center gap-2">
        <Trophy className="w-5 h-5 text-yellow-400" />
        <h2 className="font-semibold">Top Whales</h2>
      </div>

      {/* Leaderboard */}
      <div className="divide-y divide-slate-700/50">
        {wallets.length === 0 ? (
          <div className="p-6 text-center text-slate-400">
            <Trophy className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No wallets tracked yet</p>
          </div>
        ) : (
          wallets.slice(0, 10).map((wallet, index) => {
            const rank = getRankBadge(index)
            return (
              <div
                key={wallet.address}
                className="px-4 py-3 hover:bg-slate-700/50 transition-colors flex items-center gap-3"
              >
                {/* Rank */}
                <span className={`text-lg font-bold w-8 ${rank.color}`}>
                  {rank.emoji}
                </span>

                {/* Wallet Info */}
                <div className="flex-grow min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm text-slate-200 truncate">
                      {wallet.address.slice(0, 8)}...{wallet.address.slice(-6)}
                    </span>
                    {wallet.is_whale && (
                      <span className="text-xs">🐋</span>
                    )}
                    {wallet.is_new && (
                      <span className="text-xs px-1.5 py-0.5 bg-blue-500/20 text-blue-400 rounded">
                        NEW
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-400 mt-0.5">
                    <span>{wallet.total_trades} trades</span>
                    <span>{wallet.markets_traded} markets</span>
                  </div>
                </div>

                {/* Volume */}
                <div className="text-right">
                  <span className="text-green-400 font-semibold">
                    {formatVolume(wallet.total_volume_usd)}
                  </span>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Footer */}
      {wallets.length > 0 && (
        <div className="px-4 py-2 bg-slate-900/50 text-center">
          <button className="text-sm text-whale-400 hover:text-whale-300 transition-colors">
            View all wallets →
          </button>
        </div>
      )}
    </div>
  )
}
