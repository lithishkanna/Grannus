import type { Metadata } from 'next'
import { Inter, Outfit, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import { Navbar } from '@/components/layout/navbar'
import { Footer } from '@/components/layout/footer'
import { Toaster } from '@/components/ui/sonner'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })
const outfit = Outfit({ subsets: ['latin'], variable: '--font-outfit' })
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-jetbrains' })

export const metadata: Metadata = {
  title: 'Grannus — RuralCare AI',
  description: 'Bridging the healthcare & language gap between rural patients and urban doctors. AI-powered voice triage in 11 Indian languages.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${outfit.variable} ${jetbrainsMono.variable} font-sans antialiased min-h-screen flex flex-col bg-paper-grain`}>
        <aside aria-label="Demo Synthetic Data Disclaimer" className="w-full bg-amber-500/15 border-b border-amber-500/30 text-amber-900 dark:text-amber-300 py-1.5 px-4 text-center text-xs font-medium tracking-wide flex items-center justify-center gap-2 z-50">
          <span className="inline-block w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          <span>Demo: synthetic data, not medical advice</span>
        </aside>
        <Navbar />
        <main className="flex-1">
          {children}
        </main>
        <Footer />
        <Toaster />
      </body>
    </html>
  )
}
