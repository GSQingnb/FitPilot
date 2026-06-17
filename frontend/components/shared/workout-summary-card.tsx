import { CalendarDays, Clock, Dumbbell, Layers } from "lucide-react"
import type { WorkoutStatus, WorkoutSummary } from "@/types"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const STATUS_LABELS: Record<WorkoutStatus, string> = {
  completed: "Completed",
  "in-progress": "In progress",
  scheduled: "Scheduled",
  skipped: "Skipped",
}

function statusVariant(
  status: WorkoutStatus,
): "default" | "secondary" | "outline" | "destructive" {
  switch (status) {
    case "completed":
      return "default"
    case "in-progress":
      return "secondary"
    case "skipped":
      return "destructive"
    default:
      return "outline"
  }
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  })
}

interface WorkoutSummaryCardProps {
  workout: WorkoutSummary
  className?: string
}

export function WorkoutSummaryCard({
  workout,
  className,
}: WorkoutSummaryCardProps) {
  const isCompleted = workout.status === "completed"

  return (
    <div
      className={cn(
        "flex items-center gap-4 rounded-lg border bg-card p-4",
        className,
      )}
    >
      <span
        className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground"
        aria-hidden="true"
      >
        <Dumbbell className="size-5" />
      </span>

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-center gap-2">
          <p className="truncate font-medium">{workout.title}</p>
          <Badge variant={statusVariant(workout.status)}>
            {STATUS_LABELS[workout.status]}
          </Badge>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <CalendarDays className="size-3.5" aria-hidden="true" />
            {formatDate(workout.date)}
          </span>
          <span className="inline-flex items-center gap-1">
            <Clock className="size-3.5" aria-hidden="true" />
            {workout.durationMinutes} min
          </span>
          <span className="inline-flex items-center gap-1">
            <Layers className="size-3.5" aria-hidden="true" />
            {workout.totalSets} sets
          </span>
        </div>
      </div>

      <div className="hidden shrink-0 flex-col items-end gap-0.5 sm:flex">
        <span className="text-sm font-semibold tabular-nums">
          {isCompleted ? `${workout.volumeKg.toLocaleString()} kg` : "—"}
        </span>
        <span className="text-xs text-muted-foreground">{workout.focus}</span>
      </div>
    </div>
  )
}
