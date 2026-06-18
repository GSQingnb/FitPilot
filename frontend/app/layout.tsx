import type { Metadata, Viewport } from "next"
import { AppProviders } from "@/components/providers/app-providers"
import "./globals.css"

export const metadata: Metadata = {
  title: "FitPilot — AI Fitness Planning & Workout Tracking",
  description: "FitPilot helps you build fitness profiles, generate AI training plans, track workouts, and review progress.",
}

export const viewport: Viewport = { colorScheme: "light", themeColor: "#ffffff" }

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="light">
      <body className="bg-background font-sans antialiased">
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  )
}
