"use client"
import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useAuth } from "@/components/auth/auth-provider"
import { getCurrentWorkout, startWorkout, addSet as apiAddSet, deleteSet, completeWorkout, cancelWorkout, type WorkoutSessionDetail, type WorkoutExercise, type WorkoutSet } from "@/lib/api/workouts"
import { listPlans, getPlan, type TrainingPlanDetail } from "@/lib/api/plans"
import { PageHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/shared/empty-state"
import { LoadingSkeleton } from "@/components/shared/loading-skeleton"
import { ErrorState } from "@/components/shared/error-state"
import { ApiError } from "@/lib/api/client"
import { Loader2, Plus, Trash2, CheckCircle2, Play, SkipForward, XCircle, Dumbbell, AlertCircle } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"

export default function CurrentWorkoutPage() {
  const { user } = useAuth()
  const userId = user?.id || ""
  const router = useRouter()
  const queryClient = useQueryClient()

  // Workout form state
  const [selectedPlanId, setSelectedPlanId] = useState("")
  const [selectedDayId, setSelectedDayId] = useState("")
  const [startError, setStartError] = useState("")
  const [confirmComplete, setConfirmComplete] = useState(false)
  const [workoutNotes, setWorkoutNotes] = useState("")
  const [perceivedDifficulty, setPerceivedDifficulty] = useState(7)

  const { data: workout, isLoading, error } = useQuery({
    queryKey: ["currentWorkout", userId], queryFn: () => getCurrentWorkout(userId), enabled: !!userId,
  })

  // Get the active plan summary (no days)
  const { data: plansData } = useQuery({
    queryKey: ["trainingPlans", userId],
    queryFn: () => listPlans(userId, "active"),
    enabled: !!userId && !workout,
  })

  const activePlanSummary = plansData?.items?.[0]

  // Fetch full plan detail to get real training day UUIDs
  const { data: planDetail, isLoading: planLoading } = useQuery<TrainingPlanDetail>({
    queryKey: ["planDetail", activePlanSummary?.id],
    queryFn: () => getPlan(activePlanSummary!.id),
    enabled: !!activePlanSummary?.id && !workout,
  })

  // Auto-select the plan and its first training day when detail loads
  useEffect(() => {
    if (planDetail?.id && planDetail.days?.length) {
      setSelectedPlanId(planDetail.id)
      setSelectedDayId(planDetail.days[0].id)
    }
  }, [planDetail])

  const startMutation = useMutation({
    mutationFn: () => startWorkout(userId, selectedPlanId, selectedDayId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["currentWorkout"] })
      setStartError("")
    },
    onError: (e: unknown) => {
      if (e instanceof ApiError) {
        if (e.status === 401) { router.replace("/login"); return }
        if (e.status === 409) { setStartError("A workout is already in progress."); return }
        if (e.status === 422) { setStartError("Invalid training plan or training day."); return }
        setStartError(e.detail || e.message)
      } else {
        setStartError("Failed to start workout.")
      }
    },
  })

  const completeMutation = useMutation({
    mutationFn: () => completeWorkout(workout!.id, workoutNotes, perceivedDifficulty),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["currentWorkout"] })
      queryClient.invalidateQueries({ queryKey: ["workoutHistory"] })
      queryClient.invalidateQueries({ queryKey: ["analytics"] })
      setConfirmComplete(false)
    },
  })
  const cancelMutation = useMutation({
    mutationFn: () => cancelWorkout(workout!.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["currentWorkout"] }),
  })

  if (isLoading) return <LoadingSkeleton />
  if (error) return <ErrorState title="Failed to load workout" />

  // ── No active workout → show start form ──────────────────────────────────
  if (!workout) {
    const days = planDetail?.days || []
    const canStart = !!selectedPlanId && !!selectedDayId && !startMutation.isPending && !planLoading

    return (
      <div className="flex flex-col gap-6 p-4 md:p-6">
        <PageHeader title="Start Workout" description="Begin a new training session" />
        <Card className="max-w-lg mx-auto w-full">
          <CardHeader><CardTitle className="text-lg">Start New Workout</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-4">
            {planLoading ? (
              <div className="flex items-center justify-center py-8"><Loader2 className="animate-spin size-6" /></div>
            ) : activePlanSummary ? (
              <>
                <div>
                  <Label>Active Plan</Label>
                  <p className="text-sm font-medium">{activePlanSummary.name}</p>
                </div>
                <div>
                  <Label htmlFor="day">Training Day</Label>
                  <select
                    id="day"
                    className="w-full border rounded-md p-2 text-sm"
                    value={selectedDayId}
                    onChange={e => setSelectedDayId(e.target.value)}
                  >
                    <option value="">Select a day...</option>
                    {days.map((day) => (
                      <option key={day.id} value={day.id}>
                        Day {day.day_index}: {day.title}
                      </option>
                    ))}
                  </select>
                </div>
                {startError && (
                  <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-md p-2">
                    <AlertCircle className="size-4 shrink-0" />{startError}
                  </div>
                )}
                <Button onClick={() => startMutation.mutate()} disabled={!canStart} className="w-full">
                  {startMutation.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Play className="mr-2 size-4" />}
                  Start Workout
                </Button>
              </>
            ) : (
              <EmptyState icon={Dumbbell} title="No Active Plan" description="Activate a training plan first to start a workout" action={<Link href="/plans"><Button variant="outline" className="mt-2">Go to Plans</Button></Link>} />
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  // ── Workout in progress → show tracking UI ────────────────────────────────
  return (
    <div className="flex flex-col gap-6 p-4 md:p-6">
      <PageHeader title="Current Workout" description={`Started ${new Date(workout.started_at).toLocaleTimeString()}`} actions={
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setConfirmComplete(true)} disabled={completeMutation.isPending}><CheckCircle2 className="mr-1 size-3" /> Complete</Button>
          <Button variant="ghost" size="sm" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending}><XCircle className="mr-1 size-3" /> Cancel</Button>
        </div>
      } />

      {confirmComplete && (
        <Card><CardContent className="flex flex-col gap-4 p-4">
          <p className="font-medium">Complete this workout?</p>
          <div><Label htmlFor="wnotes">Notes (optional)</Label><Input id="wnotes" value={workoutNotes} onChange={e => setWorkoutNotes(e.target.value)} /></div>
          <div><Label>Perceived Difficulty (1-10): {perceivedDifficulty}</Label><input type="range" min={1} max={10} value={perceivedDifficulty} onChange={e => setPerceivedDifficulty(Number(e.target.value))} className="w-full" /></div>
          <div className="flex gap-2">
            <Button onClick={() => completeMutation.mutate()} disabled={completeMutation.isPending}>{completeMutation.isPending && <Loader2 className="mr-2 size-4 animate-spin" />}Confirm Complete</Button>
            <Button variant="outline" onClick={() => setConfirmComplete(false)}>Cancel</Button>
          </div>
        </CardContent></Card>
      )}

      <div className="grid gap-4">
        {workout.exercises?.map((ex: WorkoutExercise) => <ExerciseCard key={ex.id} exercise={ex} sessionId={workout.id} isInProgress={workout.status === "in_progress"} />)}
      </div>

      {workout.stats && (
        <Card><CardContent className="grid grid-cols-3 gap-4 p-4 text-center text-sm">
          <div><p className="text-2xl font-bold">{workout.stats.completed_sets}</p><p className="text-muted-foreground">Sets</p></div>
          <div><p className="text-2xl font-bold">{workout.stats.total_reps}</p><p className="text-muted-foreground">Reps</p></div>
          <div><p className="text-2xl font-bold">{workout.stats.total_volume.toFixed(0)}</p><p className="text-muted-foreground">Volume (kg)</p></div>
        </CardContent></Card>
      )}
    </div>
  )
}

function ExerciseCard({ exercise, sessionId, isInProgress }: { exercise: WorkoutExercise; sessionId: string; isInProgress: boolean }) {
  const [newWeight, setNewWeight] = useState("")
  const [newReps, setNewReps] = useState("")
  const [newRpe, setNewRpe] = useState("")
  const queryClient = useQueryClient()
  const addMutation = useMutation({ mutationFn: () => apiAddSet(sessionId, exercise.id, { set_index: (exercise.sets?.length || 0) + 1, weight_kg: newWeight ? Number(newWeight) : null, reps: newReps ? Number(newReps) : null, rpe: newRpe ? Number(newRpe) : null }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["currentWorkout"] }); setNewWeight(""); setNewReps(""); setNewRpe("") } })
  const deleteMutation = useMutation({ mutationFn: (setId: string) => deleteSet(sessionId, setId), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["currentWorkout"] }) })
  const statusBadge = exercise.status === "completed" ? <Badge variant="default">Done</Badge> : exercise.status === "skipped" ? <Badge variant="secondary">Skipped</Badge> : <Badge variant="outline">Pending</Badge>
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div><CardTitle className="text-base">{exercise.exercise_name}</CardTitle><p className="text-xs text-muted-foreground">{exercise.primary_muscle} • {exercise.equipment}</p></div>
        <div className="flex items-center gap-2">{statusBadge}</div>
      </CardHeader>
      <CardContent>
        {exercise.sets?.length > 0 && <div className="mb-3 space-y-1">{exercise.sets.map((s: WorkoutSet) => (
          <div key={s.id} className="flex items-center gap-2 text-sm bg-muted/50 rounded px-2 py-1">
            <span className="font-mono text-xs w-6">#{s.set_index}</span>
            {s.weight_kg && <span>{s.weight_kg}kg</span>}{s.reps && <span>x{s.reps}</span>}
            {s.rpe && <span className="text-muted-foreground">@{s.rpe}</span>}
            {isInProgress && <button onClick={() => deleteMutation.mutate(s.id)} className="ml-auto text-red-500 hover:text-red-700"><Trash2 className="size-3" /></button>}
          </div>
        ))}</div>}
        {isInProgress && exercise.status !== "completed" && exercise.status !== "skipped" && (
          <div className="flex gap-2 items-end">
            <div className="flex-1"><Label className="text-xs">Weight</Label><Input value={newWeight} onChange={e => setNewWeight(e.target.value)} placeholder="kg" type="number" className="h-8 text-sm" /></div>
            <div className="flex-1"><Label className="text-xs">Reps</Label><Input value={newReps} onChange={e => setNewReps(e.target.value)} placeholder="#" type="number" className="h-8 text-sm" /></div>
            <div className="w-16"><Label className="text-xs">RPE</Label><Input value={newRpe} onChange={e => setNewRpe(e.target.value)} placeholder="7" type="number" min={1} max={10} className="h-8 text-sm" /></div>
            <Button size="sm" onClick={() => addMutation.mutate()} disabled={addMutation.isPending}><Plus className="size-3" /></Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
