"use client"
import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@/components/auth/auth-provider"
import { listWorkouts, type WorkoutSessionSummary } from "@/lib/api/workouts"
import { PageHeader } from "@/components/shared/page-header"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { LoadingSkeleton } from "@/components/shared/loading-skeleton"
import { EmptyState } from "@/components/shared/empty-state"
import { ErrorState } from "@/components/shared/error-state"
import { Clock, BarChart3, Calendar, Dumbbell } from "lucide-react"
import Link from "next/link"

export default function WorkoutHistoryPage() {
  const { user } = useAuth()
  const userId = user?.id || ""
  const { data, isLoading, error } = useQuery({ queryKey: ["workoutHistory", userId], queryFn: () => listWorkouts(userId), enabled: !!userId })
  if (isLoading) return <LoadingSkeleton />
  if (error) return <ErrorState title="Failed to load history" />
  const items = data?.items || []
  return (
    <div className="flex flex-col gap-6 p-4 md:p-6">
      <PageHeader title="Workout History" description="Your past training sessions" />
      {items.length === 0 ? (
        <EmptyState icon={Dumbbell} title="No Workouts Yet" description="Complete your first workout to see it here" />
      ) : (
        <div className="grid gap-4">
          {items.map((w: WorkoutSessionSummary) => (
            <Link key={w.id} href={`/workouts/history/${w.id}`}>
              <Card className="hover:border-lime-500/30 transition-colors cursor-pointer">
                <CardContent className="flex items-center justify-between p-4">
                  <div><p className="font-medium">{w.training_day_title || "Workout"}</p>
                    <div className="flex items-center gap-3 text-sm text-muted-foreground mt-1">
                      <span className="flex items-center gap-1"><Calendar className="size-3" />{new Date(w.started_at).toLocaleDateString()}</span>
                      {w.duration_seconds && <span className="flex items-center gap-1"><Clock className="size-3" />{Math.round(w.duration_seconds / 60)}m</span>}
                      <span className="flex items-center gap-1"><BarChart3 className="size-3" />{w.completed_set_count} sets</span>
                    </div>
                  </div>
                  <Badge variant={w.status === "completed" ? "default" : "secondary"}>{w.status}</Badge>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
