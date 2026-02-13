import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import { AppShell } from '@/components/layout/AppShell'
import { Toaster } from 'react-hot-toast'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

export const metadata: Metadata = {
  title: 'Vibarr - Music Discovery',
  description: 'Music Metadata Discovery & Recommendation Engine',
  icons: {
    icon: '/vibarr-icon.svg',
    apple: '/vibarr-icon.svg',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans bg-surface-950 text-white`}>
        <Providers>
          <AppShell>{children}</AppShell>
          <Toaster
            position="bottom-right"
            toastOptions={{
              className: 'bg-surface-800 text-white border border-surface-700',
              duration: 5000,
            }}
          />
        </Providers>
      </body>
    </html>
  )
}
