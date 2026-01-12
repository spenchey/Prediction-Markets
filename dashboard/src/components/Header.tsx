'use client'

import { RefreshCw, Wifi, WifiOff, Github, Settings } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

interface HeaderProps {
  isConnected: boolean
  lastUpdate: Date | null
  onRefresh: () => void
}

export default function Header({ isConnected, lastUpdate, onRefresh }: HeaderProps) {
  return (
    <header className="bg-slate-800 border-b border-slate-700 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <span className="text-3xl">🐋</span>
            <div>
              <h1 className="text-xl font-bold text-white">Whale Tracker</h1>
              <p className="text-xs text-slate-400">Prediction Market Alerts</p>
            </div>
          </div>

          {/* Status & Actions */}
          <div className="flex items-center gap-4">
            {/* Connection Status */}
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
              isConnected 
                ? 'bg-green-500/20 text-green-400' 
                : 'bg-red-500/20 text-red-400'
            }`}>
              {isConnected ? (
                <>
                  <Wifi className="w-4 h-4" />
                  <span>Live</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-4 h-4" />
                  <span>Disconnected</span>
                </>
              )}
            </div>

            {/* Last Update */}
            {lastUpdate && (
              <span className="text-sm text-slate-400 hidden sm:block">
                Updated {formatDistanceToNow(lastUpdate, { addSuffix: true })}
              </span>
            )}

            {/* Refresh Button */}
            <button
              onClick={onRefresh}
              className="p-2 rounded-lg bg-slate-700 hover:bg-slate-600 transition-colors"
              title="Refresh data"
            >
              <RefreshCw className="w-5 h-5" />
            </button>

            {/* Settings (placeholder) */}
            <button
              className="p-2 rounded-lg bg-slate-700 hover:bg-slate-600 transition-colors"
              title="Settings"
            >
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
