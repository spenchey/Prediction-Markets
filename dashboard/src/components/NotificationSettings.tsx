'use client'

import { useState } from 'react'
import { 
  Bell, Mail, MessageSquare, Send, Smartphone, 
  Settings, X, Check, AlertTriangle, Volume2, VolumeX
} from 'lucide-react'

interface NotificationSettings {
  email: { enabled: boolean; address: string }
  discord: { enabled: boolean; webhook: string }
  telegram: { enabled: boolean; chatId: string }
  slack: { enabled: boolean; webhook: string }
  push: { enabled: boolean; tokens: string[] }
  sound: boolean
  minAmount: number
  alertTypes: {
    whale_trade: boolean
    unusual_size: boolean
    new_wallet: boolean
    smart_money: boolean
  }
}

interface NotificationSettingsProps {
  isOpen: boolean
  onClose: () => void
  apiBase?: string
}

export default function NotificationSettingsPanel({ 
  isOpen, 
  onClose,
  apiBase = 'http://localhost:8000' 
}: NotificationSettingsProps) {
  const [settings, setSettings] = useState<NotificationSettings>({
    email: { enabled: false, address: '' },
    discord: { enabled: false, webhook: '' },
    telegram: { enabled: false, chatId: '' },
    slack: { enabled: false, webhook: '' },
    push: { enabled: false, tokens: [] },
    sound: true,
    minAmount: 10000,
    alertTypes: {
      whale_trade: true,
      unusual_size: true,
      new_wallet: true,
      smart_money: true
    }
  })
  
  const [activeTab, setActiveTab] = useState<'channels' | 'filters'>('channels')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  
  const handleSave = async () => {
    setSaving(true)
    
    // In production, save to backend
    try {
      // await fetch(`${apiBase}/settings/notifications`, {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify(settings)
      // })
      
      // Simulate save
      await new Promise(r => setTimeout(r, 500))
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      console.error('Failed to save settings')
    }
    
    setSaving(false)
  }
  
  const updateChannel = (channel: keyof NotificationSettings, key: string, value: any) => {
    setSettings(prev => ({
      ...prev,
      [channel]: { ...(prev[channel] as any), [key]: value }
    }))
  }
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-slate-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden border border-slate-700">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600/20 rounded-lg">
              <Bell className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Notification Settings</h2>
              <p className="text-sm text-slate-400">Configure how you receive whale alerts</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Tabs */}
        <div className="flex border-b border-slate-700">
          <button
            onClick={() => setActiveTab('channels')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === 'channels' 
                ? 'text-blue-400 border-b-2 border-blue-400 bg-slate-700/30' 
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Notification Channels
          </button>
          <button
            onClick={() => setActiveTab('filters')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === 'filters' 
                ? 'text-blue-400 border-b-2 border-blue-400 bg-slate-700/30' 
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Alert Filters
          </button>
        </div>
        
        {/* Content */}
        <div className="p-5 overflow-y-auto max-h-[60vh]">
          {activeTab === 'channels' && (
            <div className="space-y-4">
              {/* Email */}
              <ChannelConfig
                icon={<Mail className="w-5 h-5" />}
                title="Email Alerts"
                description="Receive alerts via email (via Resend)"
                enabled={settings.email.enabled}
                onToggle={(v) => updateChannel('email', 'enabled', v)}
              >
                <input
                  type="email"
                  placeholder="your@email.com"
                  value={settings.email.address}
                  onChange={(e) => updateChannel('email', 'address', e.target.value)}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </ChannelConfig>
              
              {/* Discord */}
              <ChannelConfig
                icon={<MessageSquare className="w-5 h-5" />}
                title="Discord Webhook"
                description="Post alerts to a Discord channel"
                enabled={settings.discord.enabled}
                onToggle={(v) => updateChannel('discord', 'enabled', v)}
              >
                <input
                  type="text"
                  placeholder="https://discord.com/api/webhooks/..."
                  value={settings.discord.webhook}
                  onChange={(e) => updateChannel('discord', 'webhook', e.target.value)}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </ChannelConfig>
              
              {/* Telegram */}
              <ChannelConfig
                icon={<Send className="w-5 h-5" />}
                title="Telegram Bot"
                description="Send alerts via Telegram bot"
                enabled={settings.telegram.enabled}
                onToggle={(v) => updateChannel('telegram', 'enabled', v)}
              >
                <input
                  type="text"
                  placeholder="Chat ID (e.g., 123456789)"
                  value={settings.telegram.chatId}
                  onChange={(e) => updateChannel('telegram', 'chatId', e.target.value)}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Message @BotFather to create a bot, then get your chat ID
                </p>
              </ChannelConfig>
              
              {/* Push */}
              <ChannelConfig
                icon={<Smartphone className="w-5 h-5" />}
                title="Push Notifications"
                description="Mobile push via Expo (requires mobile app)"
                enabled={settings.push.enabled}
                onToggle={(v) => updateChannel('push', 'enabled', v)}
              >
                <p className="text-sm text-slate-400">
                  Push notifications require the mobile app. Download it to receive real-time alerts on your phone.
                </p>
              </ChannelConfig>
              
              {/* Sound */}
              <div className="flex items-center justify-between p-4 bg-slate-700/50 rounded-xl">
                <div className="flex items-center gap-3">
                  {settings.sound ? (
                    <Volume2 className="w-5 h-5 text-blue-400" />
                  ) : (
                    <VolumeX className="w-5 h-5 text-slate-400" />
                  )}
                  <div>
                    <p className="font-medium">Alert Sound</p>
                    <p className="text-sm text-slate-400">Play sound for high severity alerts</p>
                  </div>
                </div>
                <Toggle 
                  enabled={settings.sound} 
                  onToggle={(v) => setSettings(prev => ({ ...prev, sound: v }))} 
                />
              </div>
            </div>
          )}
          
          {activeTab === 'filters' && (
            <div className="space-y-6">
              {/* Minimum Amount */}
              <div className="bg-slate-700/50 rounded-xl p-4">
                <label className="block mb-3">
                  <span className="font-medium">Minimum Trade Amount</span>
                  <span className="text-sm text-slate-400 block">Only alert for trades above this value</span>
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="100"
                    max="100000"
                    step="100"
                    value={settings.minAmount}
                    onChange={(e) => setSettings(prev => ({ ...prev, minAmount: parseInt(e.target.value) }))}
                    className="flex-1 h-2 bg-slate-600 rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="bg-slate-600 rounded-lg px-3 py-1 min-w-[100px] text-center">
                    <span className="font-mono text-green-400">${settings.minAmount.toLocaleString()}</span>
                  </div>
                </div>
              </div>
              
              {/* Alert Types */}
              <div className="bg-slate-700/50 rounded-xl p-4">
                <p className="font-medium mb-3">Alert Types</p>
                <div className="space-y-3">
                  <AlertTypeToggle
                    icon="🐋"
                    title="Whale Trades"
                    description="Large trades above threshold"
                    enabled={settings.alertTypes.whale_trade}
                    onToggle={(v) => setSettings(prev => ({
                      ...prev,
                      alertTypes: { ...prev.alertTypes, whale_trade: v }
                    }))}
                  />
                  <AlertTypeToggle
                    icon="📊"
                    title="Unusual Size"
                    description="Statistically abnormal trades"
                    enabled={settings.alertTypes.unusual_size}
                    onToggle={(v) => setSettings(prev => ({
                      ...prev,
                      alertTypes: { ...prev.alertTypes, unusual_size: v }
                    }))}
                  />
                  <AlertTypeToggle
                    icon="🆕"
                    title="New Wallet"
                    description="First-time traders making big bets"
                    enabled={settings.alertTypes.new_wallet}
                    onToggle={(v) => setSettings(prev => ({
                      ...prev,
                      alertTypes: { ...prev.alertTypes, new_wallet: v }
                    }))}
                  />
                  <AlertTypeToggle
                    icon="🧠"
                    title="Smart Money"
                    description="High win-rate wallets trading"
                    enabled={settings.alertTypes.smart_money}
                    onToggle={(v) => setSettings(prev => ({
                      ...prev,
                      alertTypes: { ...prev.alertTypes, smart_money: v }
                    }))}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* Footer */}
        <div className="flex items-center justify-between p-5 border-t border-slate-700 bg-slate-800/50">
          <p className="text-sm text-slate-400">
            Changes apply to new alerts only
          </p>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              {saving ? (
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : saved ? (
                <Check className="w-4 h-4" />
              ) : null}
              {saved ? 'Saved!' : 'Save Settings'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// Toggle component
function Toggle({ enabled, onToggle }: { enabled: boolean; onToggle: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onToggle(!enabled)}
      className={`relative w-12 h-6 rounded-full transition-colors ${
        enabled ? 'bg-blue-600' : 'bg-slate-600'
      }`}
    >
      <div className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
        enabled ? 'translate-x-7' : 'translate-x-1'
      }`} />
    </button>
  )
}

// Channel config component
function ChannelConfig({ 
  icon, 
  title, 
  description, 
  enabled, 
  onToggle, 
  children 
}: {
  icon: React.ReactNode
  title: string
  description: string
  enabled: boolean
  onToggle: (v: boolean) => void
  children?: React.ReactNode
}) {
  return (
    <div className={`rounded-xl border transition-colors ${
      enabled ? 'bg-slate-700/50 border-blue-500/50' : 'bg-slate-700/30 border-slate-700'
    }`}>
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${enabled ? 'bg-blue-600/20 text-blue-400' : 'bg-slate-600 text-slate-400'}`}>
            {icon}
          </div>
          <div>
            <p className="font-medium">{title}</p>
            <p className="text-sm text-slate-400">{description}</p>
          </div>
        </div>
        <Toggle enabled={enabled} onToggle={onToggle} />
      </div>
      {enabled && children && (
        <div className="px-4 pb-4">
          {children}
        </div>
      )}
    </div>
  )
}

// Alert type toggle
function AlertTypeToggle({
  icon,
  title,
  description,
  enabled,
  onToggle
}: {
  icon: string
  title: string
  description: string
  enabled: boolean
  onToggle: (v: boolean) => void
}) {
  return (
    <div 
      className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
        enabled ? 'bg-slate-600/50' : 'bg-slate-700/30'
      }`}
      onClick={() => onToggle(!enabled)}
    >
      <div className="flex items-center gap-3">
        <span className="text-xl">{icon}</span>
        <div>
          <p className="font-medium text-sm">{title}</p>
          <p className="text-xs text-slate-400">{description}</p>
        </div>
      </div>
      <div className={`w-5 h-5 rounded-md flex items-center justify-center transition-colors ${
        enabled ? 'bg-blue-600' : 'bg-slate-600'
      }`}>
        {enabled && <Check className="w-3 h-3" />}
      </div>
    </div>
  )
}
