import { CalendarRange, Layers, TrendingUp } from "lucide-react"
import type { TrainingPlanSummary } from "@/types"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface TrainingPlanCardProps {
  plan: TrainingPlanSummary
  className?: string
}

export function TrainingPlanCard({ plan, className }: TrainingPlanCardProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1.5">
            <CardTitle className="flex items-center gap-2">
              {plan.name}
              {plan.isActive && <Badge>Active</Badge>}
            </CardTitle>
            <CardDescription className="text-pretty">
              {plan.description}
            </CardDescription>
          </div>
          <Badge variant="outline" className="shrink-0 capitalize">
            {plan.level}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <CalendarRange className="size-4" aria-hidden="true" />
            {plan.daysPerWeek} days / week
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Layers className="size-4" aria-hidden="true" />
            {plan.durationWeeks} weeks
          </span>
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-sm">
            <span className="inline-flex items-center gap-1.5 text-muted-foreground">
              <TrendingUp className="size-4" aria-hidden="true" />
              Progress
            </span>
            <span className="font-medium tabular-nums">
              {plan.progressPercent}%
            </span>
          </div>
          <div
            className="h-2 w-full overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-valuenow={plan.progressPercent}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className={cn("h-full rounded-full bg-primary transition-all")}
              style={{ width: `${plan.progressPercent}%` }}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
