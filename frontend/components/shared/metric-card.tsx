import type { LucideIcon } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"

interface MetricCardProps {
  label: string
  value: string
  icon: LucideIcon
  /** Optional supporting text under the value, e.g. "Goal: 5". */
  hint?: string
}

export function MetricCard({ label, value, icon: Icon, hint }: MetricCardProps) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold tracking-tight tabular-nums">
            {value}
          </p>
          {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
        </div>
        <span
          className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground"
          aria-hidden="true"
        >
          <Icon className="size-5" />
        </span>
      </CardContent>
    </Card>
  )
}
