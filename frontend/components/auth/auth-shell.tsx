import type { ReactNode } from "react"
import { Activity, BarChart3, Bot } from "lucide-react"
import { Logo } from "@/components/brand/logo"

const HIGHLIGHTS = [
  {
    icon: Bot,
    title: "AI training plans",
    description: "Personalized programs that adapt to your goals and schedule.",
  },
  {
    icon: Activity,
    title: "Effortless tracking",
    description: "Log sets, weight, reps, and RPE in seconds during your session.",
  },
  {
    icon: BarChart3,
    title: "Clear progress",
    description: "Weekly reports and trends that show exactly how you're improving.",
  },
]

/**
 * Two-column shell for the auth pages: a brand panel on the left (desktop only)
 * and the form content on the right.
 */
export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: ReactNode
}) {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      {/* Brand panel */}
      <aside className="hidden flex-col justify-between bg-sidebar p-10 lg:flex">
        <Logo />
        <div className="flex max-w-md flex-col gap-8">
          <div className="flex flex-col gap-3">
            <h2 className="text-3xl font-semibold tracking-tight text-balance">
              Train smarter with an AI coach in your corner.
            </h2>
            <p className="leading-relaxed text-muted-foreground text-pretty">
              Plan, track, and analyze every session in one focused workspace.
            </p>
          </div>
          <ul className="flex flex-col gap-5">
            {HIGHLIGHTS.map((item) => {
              const Icon = item.icon
              return (
                <li key={item.title} className="flex items-start gap-3">
                  <span
                    className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground"
                    aria-hidden="true"
                  >
                    <Icon className="size-5" />
                  </span>
                  <div className="flex flex-col gap-0.5">
                    <p className="font-medium">{item.title}</p>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      {item.description}
                    </p>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
        <p className="text-xs text-muted-foreground">
          © {new Date().getFullYear()} FitPilot. All rights reserved.
        </p>
      </aside>

      {/* Form panel */}
      <main className="flex flex-col items-center justify-center px-4 py-10 sm:px-6">
        <div className="flex w-full max-w-sm flex-col gap-8">
          <div className="flex flex-col gap-6">
            <div className="lg:hidden">
              <Logo />
            </div>
            <div className="flex flex-col gap-1.5">
              <h1 className="text-2xl font-semibold tracking-tight text-balance">
                {title}
              </h1>
              <p className="text-sm leading-relaxed text-muted-foreground text-pretty">
                {subtitle}
              </p>
            </div>
          </div>
          {children}
        </div>
      </main>
    </div>
  )
}
