'use client'

import { Bell, X } from 'lucide-react'

interface NotificationBannerProps {
  count: number
  onDismiss: () => void
}

export default function NotificationBanner({ count, onDismiss }: NotificationBannerProps) {
  return (
    <div className="bg-whale-600 text-white px-4 py-2 animate-slide-in">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4 animate-pulse" />
          <span className="text-sm font-medium">
            {count} new alert{count !== 1 ? 's' : ''} detected!
          </span>
        </div>
        <button
          onClick={onDismiss}
          className="p-1 hover:bg-whale-700 rounded transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
