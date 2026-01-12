'use client'

import { TrendingUp, BarChart3, ExternalLink } from 'lucide-react'

interface Market {
  id: string
  question: string
  yes_price: number
  no_price: number
  volume: number
}

interface MarketsListProps {
  markets: Market[]
}

export default function MarketsList({ markets }: MarketsListProps) {
  const formatVolume = (volume: number) => {
    if (volume >= 1000000) return `$${(volume / 1000000).toFixed(1)}M`
    if (volume >= 1000) return `$${(volume / 1000).toFixed(0)}K`
    return `$${volume.toFixed(0)}`
  }

  const getPriceColor = (price: number) => {
    if (price >= 0.7) return 'text-green-400'
    if (price <= 0.3) return 'text-red-400'
    return 'text-yellow-400'
  }

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700 flex items-center gap-2">
        <BarChart3 className="w-5 h-5 text-whale-400" />
        <h2 className="font-semibold">Top Markets</h2>
      </div>

      {/* Markets List */}
      <div className="divide-y divide-slate-700/50">
        {markets.length === 0 ? (
          <div className="p-6 text-center text-slate-400">
            <BarChart3 className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p className="text-sm">Loading markets...</p>
          </div>
        ) : (
          markets.slice(0, 8).map((market) => (
            <div
              key={market.id}
              className="px-4 py-3 hover:bg-slate-700/50 transition-colors"
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <p className="text-sm text-slate-200 line-clamp-2 flex-grow">
                  {market.question}
                </p>
                <a 
                  href={`https://polymarket.com`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-slate-400 hover:text-white flex-shrink-0"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
              
              <div className="flex items-center justify-between">
                {/* Price Bar */}
                <div className="flex-grow mr-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-sm font-semibold ${getPriceColor(market.yes_price)}`}>
                      Yes {(market.yes_price * 100).toFixed(0)}%
                    </span>
                    <span className="text-slate-500">•</span>
                    <span className={`text-sm font-semibold ${getPriceColor(market.no_price)}`}>
                      No {(market.no_price * 100).toFixed(0)}%
                    </span>
                  </div>
                  
                  {/* Visual Bar */}
                  <div className="h-1.5 bg-red-500/30 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-green-500 rounded-full transition-all"
                      style={{ width: `${market.yes_price * 100}%` }}
                    />
                  </div>
                </div>

                {/* Volume */}
                <div className="text-right flex-shrink-0">
                  <span className="text-xs text-slate-400">Vol</span>
                  <p className="text-sm font-semibold text-slate-200">
                    {formatVolume(market.volume)}
                  </p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      {markets.length > 0 && (
        <div className="px-4 py-2 bg-slate-900/50 text-center">
          <a 
            href="https://polymarket.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-whale-400 hover:text-whale-300 transition-colors"
          >
            View all markets →
          </a>
        </div>
      )}
    </div>
  )
}
