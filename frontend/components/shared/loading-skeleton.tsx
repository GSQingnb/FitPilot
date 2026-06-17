import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { cn } from "@/lib/utils"

/** A single card-shaped skeleton placeholder. */
export function CardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <CardHeader className="gap-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-7 w-16" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-3 w-32" />
      </CardContent>
    </Card>
  )
}

interface LoadingSkeletonProps {
  /** Number of metric cards to render in the grid. */
  metricCards?: number
  /** Number of list rows to render below the grid. */
  rows?: number
  className?: string
}

/**
 * Generic dashboard-style loading skeleton: a metric card grid plus a few
 * stacked list rows. Mirrors the dashboard layout to avoid layout shift.
 */
export function LoadingSkeleton({
  metricCards = 4,
  rows = 3,
  className,
}: LoadingSkeletonProps) {
  return (
    <div className={cn("flex flex-col gap-6", className)}>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: metricCards }).map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-40" />
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {Array.from({ length: rows }).map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <Skeleton className="size-10 shrink-0 rounded-lg" />
              <div className="flex flex-1 flex-col gap-2">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-3 w-1/2" />
              </div>
              <Skeleton className="h-4 w-16" />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
