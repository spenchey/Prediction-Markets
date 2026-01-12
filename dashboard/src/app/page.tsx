'use client'

import { useState, useEffect, useCallback } from 'react'
import { AlertCircle, TrendingUp, Users, Activity, RefreshCw, Bell, Wallet, Settings } from 'lucide-react'
import AlertFeed from '@/components/AlertFeed'
import StatsCards from '@/components/StatsCards'
import MarketsList from '@/components/MarketsList'
import WhaleLeaderboard from '@/components/WhaleLeaderboard'
import NotificationBanner from '@/components/NotificationBanner'
import Header from '@/components/Header'
import VolumeChart from '@/components/VolumeChart'
import NotificationSettings from '@/components/NotificationSettings'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function Dashboard() {
  const [alerts, setAlerts] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [markets, setMarkets] = useState<any[]>([])
  const [wallets, setWallets] = useState<any[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)
  const [newAlertCount, setNewAlertCount] = useState(0)
  const [showSettings, setShowSettings] = useState(false)

  // Fetch initial data
  const fetchData = useCallback(async () => {
    try {
      // Fetch alerts
      const alertsRes = await fetch(`${API_BASE}/alerts?limit=50`)
      if (alertsRes.ok) {
        const alertsData = await alertsRes.json()
        setAlerts(alertsData)
      }

      // Fetch stats
      const statsRes = await fetch(`${API_BASE}/stats`)
      if (statsRes.ok) {
        const statsData = await statsRes.json()
        setStats(statsData)
      }

      // Fetch markets
      const marketsRes = await fetch(`${API_BASE}/markets?limit=10`)
      if (marketsRes.ok) {
        const marketsData = await marketsRes.json()
        setMarkets(marketsData)
      }

      // Fetch wallet stats
      const walletsRes = await fetch(`${API_BASE}/stats/wallets?limit=10`)
      if (walletsRes.ok) {
        const walletsData = await walletsRes.json()
        setWallets(walletsData.wallets || [])
      }

      setLastUpdate(new Date())
      setIsConnected(true)
    } catch (error) {
      console.error('Failed to fetch data:', error)
      setIsConnected(false)
    }
  }, [])

  // Set up real-time alerts via SSE
  useEffect(() => {
    fetchData()
    
    // Connect to SSE for real-time alerts
    const eventSource = new EventSource(`${API_BASE}/alerts/stream`)
    
    eventSource.onmessage = (event) => {
      try {
        const newAlert = JSON.parse(event.data.replace(/'/g, '"'))
        setAlerts(prev => [newAlert, ...prev.slice(0, 49)])
        setNewAlertCount(prev => prev + 1)
        
        // Play sound for high severity alerts
        if (newAlert.severity === 'HIGH') {
          playAlertSound()
        }
      } catch (e) {
        console.error('Failed to parse alert:', e)
      }
    }

    eventSource.onerror = () => {
      setIsConnected(false)
    }

    eventSource.onopen = () => {
      setIsConnected(true)
    }

    // Refresh data periodically
    const interval = setInterval(fetchData, 30000)

    return () => {
      eventSource.close()
      clearInterval(interval)
    }
  }, [fetchData])

  const playAlertSound = () => {
    // Create a simple beep sound
    try {
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
      const oscillator = audioContext.createOscillator()
      const gainNode = audioContext.createGain()
      
      oscillator.connect(gainNode)
      gainNode.connect(audioContext.destination)
      
      oscillator.frequency.value = 800
      oscillator.type = 'sine'
      gainNode.gain.value = 0.1
      
      oscillator.start()
      oscillator.stop(audioContext.currentTime + 0.2)
    } catch (e) {
      // Audio not available
    }
  }

  const handleRefresh = () => {
    fetchData()
    setNewAlertCount(0)
  }

  return (
    <div className="min-h-screen bg-slate-900 text-white">
      <Header 
        isConnected={isConnected} 
        lastUpdate={lastUpdate}
        onRefresh={handleRefresh}
      />
      
      {newAlertCount > 0 && (
        <NotificationBanner 
          count={newAlertCount} 
          onDismiss={() => setNewAlertCount(0)} 
        />
      )}

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Stats Overview */}
        <StatsCards stats={stats} />

        {/* Volume Chart */}
        <div className="mt-6">
          <VolumeChart apiBase={API_BASE} />
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          {/* Alert Feed - Takes 2 columns */}
          <div className="lg:col-span-2">
            <AlertFeed alerts={alerts} />
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <WhaleLeaderboard wallets={wallets} />
            <MarketsList markets={markets} />
          </div>
        </div>
      </main>

      {/* Settings Modal */}
      <NotificationSettings 
        isOpen={showSettings} 
        onClose={() => setShowSettings(false)}
        apiBase={API_BASE}
      />

      {/* Floating Settings Button */}
      <button
        onClick={() => setShowSettings(true)}
        className="fixed bottom-6 right-6 p-4 bg-blue-600 hover:bg-blue-700 rounded-full shadow-lg transition-all hover:scale-110 z-40"
        title="Notification Settings"
      >
        <Settings className="w-6 h-6" />
      </button>
    </div>
  )
}
