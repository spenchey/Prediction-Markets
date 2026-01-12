'use client'

import { useState } from 'react'
import { AlertCircle, TrendingUp, User, Clock, ExternalLink, Filter } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

interface Alert {
  id: string
  alert_type: string
  severity: string
  message: string
  trade_amount_usd: number
  trader_address: string
  market_id: string
  outcome: string
  timestamp: string
}

interface AlertFeedProps {
  alerts: Alert[]
}

const severityConfig = {
  HIGH: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    text: 'text-red-400',
    badge: 'bg-red-500',
    glow: 'shadow-red-500/20',
  },
  MEDIUM: {
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/30',
    text: 'text-yellow-400',
    badge: 'bg-yellow-500',
    glow: 'shadow-yellow-500/20',
  },
  LOW: {
    bg: 'bg-green-500/10',
    border: 'border-green-500/30',
    text: 'text-green-400',
    badge: 'bg-green-500',
    glow: 'shadow-green-500/20',
  },
}

const alertTypeIcons = {
  WHALE_TRADE: '🐋',
  UNUSUAL_SIZE: '📊',
  NEW_WALLET: '🆕',
  SMART_MONEY: '🧠',
}

export default function AlertFeed({ alerts }: AlertFeedProps) {
  const [filter, setFilter] = useState<string>('ALL')

  const filteredAlerts = filter === 'ALL' 
    ? alerts 
    : alerts.filter(a => a.alert_type === filter || a.severity === filter)

  const alertTypes = ['ALL', 'HIGH', 'MEDIUM', 'LOW']

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-400" />
          <h2 className="font-semibold">Live Alerts</h2>
          <span className="text-sm text-slate-400">({alerts.length})</span>
        </div>
        
        {/* Filter Buttons */}
        <div className="flex gap-1">
          {alertTypes.map(type => (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={`px-3 py-1 text-xs rounded-full transition-colors ${
                filter === type 
                  ? 'bg-whale-600 text-white' 
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {/* Alert List */}
      <div className="max-h-[600px] overflow-y-auto">
        {filteredAlerts.length === 0 ? (
          <div className="p-8 text-center text-slate-400">
            <AlertCircle className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No alerts yet</p>
            <p className="text-sm mt-1">Whale trades will appear here in real-time</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-700/50">
            {filteredAlerts.map((alert, index) => {
              const config = severityConfig[alert.severity as keyof typeof severityConfig] || severityConfig.LOW
              const icon = alertTypeIcons[alert.alert_type as keyof typeof alertTypeIcons] || '🔔'
              
              return (
                <div
                  key={alert.id || index}
                  className={`p-4 ${config.bg} ${index === 0 ? 'animate-slide-in' : ''} hover:bg-slate-700/50 transition-colors`}
                >
                  <div className="flex items-start gap-3">
                    {/* Icon & Severity */}
                    <div className="flex-shrink-0">
                      <span className="text-2xl">{icon}</span>
                    </div>

                    {/* Content */}
                    <div className="flex-grow min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${config.badge} text-white font-medium`}>
                          {alert.severity}
                        </span>
                        <span className="text-xs text-slate-400">
                          {alert.alert_type.replace('_', ' ')}
                        </span>
                      </div>

                      <p className="text-sm text-slate-200 mb-2">
                        {alert.message}
                      </p>

                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
                        <span className={`font-mono ${config.text} font-semibold`}>
                          ${alert.trade_amount_usd?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </span>
                        
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3" />
                          {alert.trader_address?.slice(0, 10)}...
                        </span>
                        
                        <span className="flex items-center gap-1">
                          <TrendingUp className="w-3 h-3" />
                          {alert.outcome}
                        </span>
                        
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {alert.timestamp && formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true })}
                        </span>
                      </div>
                    </div>

                    {/* Actions */}
                    <button 
                      className="flex-shrink-0 p-1.5 rounded hover:bg-slate-600 text-slate-400 hover:text-white transition-colors"
                      title="View on Polymarket"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
