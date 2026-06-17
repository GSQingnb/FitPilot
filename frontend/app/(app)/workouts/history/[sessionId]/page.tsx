"use client"

import { useParams } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@/components/auth/auth-provider"
import { getWorkout, type WorkoutSessionDetail, type WorkoutExercise, type WorkoutSet } from "@/lib/api/workouts"
import { PageHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { LoadingSkeleton } from "@/components/shared/loading-skeleton"
import { ErrorState } from "@/components/shared/error-state"
import { Clock, Dumbbell, Target } from "lucide-react"

export default function WorkoutDetailPage() {
  const { user } = useAuth()
  const { sessionId } = useParams<{ sessionId: string }>()

  const { data: workout, isLoading, error } = useQuery<WorkoutSessionDetail>({
    queryKey: ["workoutDetail", sessionId],
    queryFn: () => getWorkout(user?.id || "", sessionId),
    enabled: !!sessionId && !!user?.id,
  })

  if (isLoading) return <LoadingSkeleton />
  if (error || !workout) return <ErrorState title="Failed to load workout" />

  const statusColor = workout.status === "completed" ? "default" : workout.status === "cancelled" ? "secondary" : "outline"

  return (
    <div className="flex flex-col gap-6 p-4 md:p-6 max-w-3xl">
      <PageHeader title={workout.training_day_title || "Workout"} description={new Date(workout.started_at).toLocaleString()} actions={
        <Badge variant={statusColor as "default" | "secondary" | "outline"}>{workout.status}</Badge>
      } />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card><CardContent className="p-4 flex items-center gap-3"><Clock className="size-5 text-lime-600" /><div><p className="text-xs text-muted-foreground">Duration</p><p className="font-medium">{workout.duration_seconds ? `${Math.round(workout.duration_seconds / 60)} min` : "N/A"}</p></div></CardContent></Card>
        <Card><CardContent className="p-4 flex items-center gap-3"><Dumbbell className="size-5 text-lime-600" /><div><p className="text-xs text-muted-foreground">Exercises</p><p className="font-medium">{workout.stats?.total_exercises || 0}</p></div></CardContent></Card>
        <Card><CardContent className="p-4 flex items-center gap-3"><Target className="size-5 text-lime-600" /><div><p className="text-xs text-muted-foreground">Difficulty</p><p className="font-medium">{workout.perceived_difficulty ?? "N/A"}/10</p></div></CardContent></Card>
      </div>

      {workout.notes && <Card><CardContent className="p-4"><p className="text-sm text-muted-foreground">{workout.notes}</p></CardContent></Card>}

      {workout.stats && (
        <Card>
          <CardContent className="grid grid-cols-3 gap-4 p-4 text-center text-sm">
            <div><p className="text-2xl font-bold">{workout.stats.completed_sets}</p><p className="text-muted-foreground">Sets</p></div>
            <div><p className="text-2xl font-bold">{workout.stats.total_reps}</p><p className="text-muted-foreground">Reps</p></div>
            <div><p className="text-2xl font-bold">{workout.stats.total_volume.toFixed(0)}</p><p className="text-muted-foreground">Volume (kg)</p></div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4">
        {workout.exercises?.map((ex: WorkoutExercise) => (
          <Card key={ex.id}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base">{ex.exercise_name}</CardTitle>
                  <p className="text-xs text-muted-foreground">{ex.primary_muscle} • {ex.equipment}</p>
                </div>
                <Badge variant={ex.status === "completed" ? "default" : ex.status === "skipped" ? "secondary" : "outline"}>
                  {ex.status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              {ex.sets && ex.sets.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground text-xs border-b">
                      <th className="py-1">Set</th><th className="py-1">Type</th><th className="py-1">Weight</th><th className="py-1">Reps</th><th className="py-1">RPE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ex.sets.map((s: WorkoutSet) => (
                      <tr key={s.id} className="border-b last:border-0">
                        <td className="py-1 font-mono">{s.set_index}</td>
                        <td className="py-1">{s.set_type}</td>
                        <td className="py-1">{s.weight_kg ? `${s.weight_kg} kg` : "-"}</td>
                        <td className="py-1">{s.reps ?? "-"}</td>
                        <td className="py-1">{s.rpe ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-sm text-muted-foreground">No sets recorded</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
