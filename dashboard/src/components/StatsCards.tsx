'use client'

import { TrendingUp, Users, Activity, AlertCircle } from 'lucide-react'

interface StatsCardsProps {
  stats: {
    total_trades_tracked: number
    total_alerts_generated: number
    whale_trades_24h: number
    unique_wallets: number
  } | null
}

export default function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      title: 'Whale Trades (24h)',
      value: stats?.whale_trades_24h ?? 0,
      icon: AlertCircle,
      color: 'text-red-400',
      bgColor: 'bg-red-500/10',
      borderColor: 'border-red-500/30',
    },
    {
      title: 'Total Alerts',
      value: stats?.total_alerts_generated ?? 0,
      icon: Activity,
      color: 'text-yellow-400',
      bgColor: 'bg-yellow-500/10',
      borderColor: 'border-yellow-500/30',
    },
    {
      title: 'Trades Tracked',
      value: stats?.total_trades_tracked ?? 0,
      icon: TrendingUp,
      color: 'text-green-400',
      bgColor: 'bg-green-500/10',
      borderColor: 'border-green-500/30',
    },
    {
      title: 'Unique Wallets',
      value: stats?.unique_wallets ?? 0,
      icon: Users,
      color: 'text-blue-400',
      bgColor: 'bg-blue-500/10',
      borderColor: 'border-blue-500/30',
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div
          key={card.title}
          className={`${card.bgColor} ${card.borderColor} border rounded-xl p-4 transition-transform hover:scale-105`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-400">{card.title}</p>
              <p className={`text-2xl font-bold ${card.color} mt-1`}>
                {card.value.toLocaleString()}
              </p>
            </div>
            <card.icon className={`w-8 h-8 ${card.color} opacity-50`} />
          </div>
        </div>
      ))}
    </div>
  )
}
