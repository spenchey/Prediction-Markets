import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: '🐋 Whale Tracker - Prediction Market Alerts',
  description: 'Track whale trades and unusual activity on prediction markets in real-time',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="min-h-screen bg-slate-900">
          {children}
        </div>
      </body>
    </html>
  )
}
