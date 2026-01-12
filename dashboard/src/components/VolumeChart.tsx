'use client'

import { useEffect, useState } from 'react'
import { BarChart3, TrendingUp, TrendingDown } from 'lucide-react'

interface VolumeData {
  time: string
  volume: number
  whaleCount: number
}

interface VolumeChartProps {
  apiBase?: string
}

export default function VolumeChart({ apiBase = 'http://localhost:8000' }: VolumeChartProps) {
  const [data, setData] = useState<VolumeData[]>([])
  const [timeRange, setTimeRange] = useState<'1h' | '24h' | '7d'>('24h')
  
  // Generate mock historical data (in production, this would come from the API)
  useEffect(() => {
    const generateMockData = () => {
      const now = new Date()
      const points = timeRange === '1h' ? 12 : timeRange === '24h' ? 24 : 7
      const interval = timeRange === '1h' ? 5 : timeRange === '24h' ? 60 : 1440
      
      return Array.from({ length: points }, (_, i) => {
        const time = new Date(now.getTime() - (points - 1 - i) * interval * 60 * 1000)
        const baseVolume = Math.random() * 50000 + 10000
        const whaleCount = Math.floor(Math.random() * 5) + 1
        
        return {
          time: timeRange === '7d' 
            ? time.toLocaleDateString('en-US', { weekday: 'short' })
            : time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
          volume: Math.round(baseVolume),
          whaleCount
        }
      })
    }
    
    setData(generateMockData())
    
    // Update every minute
    const interval = setInterval(() => setData(generateMockData()), 60000)
    return () => clearInterval(interval)
  }, [timeRange])
  
  const maxVolume = Math.max(...data.map(d => d.volume), 1)
  const totalVolume = data.reduce((sum, d) => sum + d.volume, 0)
  const totalWhales = data.reduce((sum, d) => sum + d.whaleCount, 0)
  const avgVolume = totalVolume / data.length
  
  // Calculate trend (comparing last half to first half)
  const firstHalf = data.slice(0, Math.floor(data.length / 2))
  const secondHalf = data.slice(Math.floor(data.length / 2))
  const firstHalfAvg = firstHalf.reduce((s, d) => s + d.volume, 0) / firstHalf.length
  const secondHalfAvg = secondHalf.reduce((s, d) => s + d.volume, 0) / secondHalf.length
  const trend = ((secondHalfAvg - firstHalfAvg) / firstHalfAvg) * 100
  
  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-400" />
          <h3 className="font-semibold text-lg">Trading Volume</h3>
        </div>
        
        {/* Time Range Selector */}
        <div className="flex bg-slate-700 rounded-lg p-1">
          {(['1h', '24h', '7d'] as const).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                timeRange === range 
                  ? 'bg-blue-600 text-white' 
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>
      
      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="bg-slate-700/50 rounded-lg p-3">
          <p className="text-slate-400 text-xs">Total Volume</p>
          <p className="text-xl font-bold text-green-400">
            ${(totalVolume / 1000).toFixed(1)}K
          </p>
        </div>
        <div className="bg-slate-700/50 rounded-lg p-3">
          <p className="text-slate-400 text-xs">Whale Trades</p>
          <p className="text-xl font-bold text-purple-400">{totalWhales}</p>
        </div>
        <div className="bg-slate-700/50 rounded-lg p-3">
          <p className="text-slate-400 text-xs">Trend</p>
          <div className="flex items-center gap-1">
            {trend >= 0 ? (
              <TrendingUp className="w-4 h-4 text-green-400" />
            ) : (
              <TrendingDown className="w-4 h-4 text-red-400" />
            )}
            <p className={`text-xl font-bold ${trend >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {trend >= 0 ? '+' : ''}{trend.toFixed(1)}%
            </p>
          </div>
        </div>
      </div>
      
      {/* Chart */}
      <div className="h-48 flex items-end gap-1">
        {data.map((d, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-1">
            {/* Bar */}
            <div className="w-full flex flex-col justify-end h-36">
              <div
                className="w-full bg-gradient-to-t from-blue-600 to-blue-400 rounded-t-sm transition-all duration-300 relative group"
                style={{ height: `${(d.volume / maxVolume) * 100}%` }}
              >
                {/* Whale indicator */}
                {d.whaleCount > 2 && (
                  <div className="absolute -top-2 left-1/2 -translate-x-1/2 text-xs">
                    🐋
                  </div>
                )}
                
                {/* Tooltip */}
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                  <div className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-xs whitespace-nowrap shadow-xl">
                    <p className="text-slate-400">{d.time}</p>
                    <p className="font-bold text-green-400">${d.volume.toLocaleString()}</p>
                    <p className="text-purple-400">{d.whaleCount} whale trades</p>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Label */}
            <span className="text-[10px] text-slate-500 truncate w-full text-center">
              {timeRange === '7d' ? d.time : d.time.split(' ')[0]}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
