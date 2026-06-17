"use client"

import { useParams } from "next/navigation"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useAuth } from "@/components/auth/auth-provider"
import { getPlan, activatePlan, archivePlan, type TrainingPlanDetail } from "@/lib/api/plans"
import { PageHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { LoadingSkeleton } from "@/components/shared/loading-skeleton"
import { ErrorState } from "@/components/shared/error-state"
import { CheckCircle2, Archive, Clock, Target, Calendar } from "lucide-react"

export default function PlanDetailPage() {
  const { user } = useAuth()
  const { planId } = useParams<{ planId: string }>()
  const qc = useQueryClient()

  const { data: plan, isLoading, error } = useQuery<TrainingPlanDetail>({
    queryKey: ["planDetail", planId],
    queryFn: () => getPlan(planId),
    enabled: !!planId,
  })

  const am = useMutation({
    mutationFn: () => activatePlan(user?.id || "", planId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["planDetail"] }),
  })
  const arm = useMutation({
    mutationFn: () => archivePlan(user?.id || "", planId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["planDetail"] }),
  })

  if (isLoading) return <LoadingSkeleton />
  if (error || !plan) return <ErrorState title="Failed to load plan" />

  return (
    <div className="flex flex-col gap-6 p-4 md:p-6 max-w-3xl">
      <PageHeader title={plan.name} description={`v${plan.version} • ${plan.source}`} actions={
        <div className="flex gap-2">
          {plan.status !== "active" && (
            <Button size="sm" onClick={() => am.mutate()} disabled={am.isPending}>
              <CheckCircle2 className="mr-1 size-4" /> Activate
            </Button>
          )}
          {plan.status !== "archived" && (
            <Button size="sm" variant="outline" onClick={() => arm.mutate()} disabled={arm.isPending}>
              <Archive className="mr-1 size-4" /> Archive
            </Button>
          )}
        </div>
      } />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card><CardContent className="p-4 flex items-center gap-3"><Target className="size-5 text-lime-600" /><div><p className="text-xs text-muted-foreground">Goal</p><p className="font-medium">{plan.goal}</p></div></CardContent></Card>
        <Card><CardContent className="p-4 flex items-center gap-3"><Calendar className="size-5 text-lime-600" /><div><p className="text-xs text-muted-foreground">Schedule</p><p className="font-medium">{plan.weekly_frequency}x/wk • {plan.duration_weeks}w</p></div></CardContent></Card>
        <Card><CardContent className="p-4 flex items-center gap-3"><Clock className="size-5 text-lime-600" /><div><p className="text-xs text-muted-foreground">Status</p><Badge variant={plan.status === "active" ? "default" : "secondary"}>{plan.status}</Badge></div></CardContent></Card>
      </div>

      <div className="grid gap-4">
        {plan.days?.map((day) => (
          <Card key={day.id}>
            <CardHeader>
              <CardTitle className="text-base">Day {day.day_index}: {day.title}</CardTitle>
              {day.notes && <CardDescription>{day.notes}</CardDescription>}
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {day.exercises?.map((ex) => (
                  <div key={ex.id} className="flex items-center justify-between text-sm border-b last:border-0 pb-2 last:pb-0">
                    <div>
                      <p className="font-medium">{ex.exercise_name}</p>
                      <p className="text-xs text-muted-foreground">{ex.primary_muscle} • {ex.equipment}</p>
                    </div>
                    <div className="text-right text-xs text-muted-foreground">
                      <p>{ex.sets} sets × {ex.reps_min}-{ex.reps_max} reps</p>
                      <p>Rest: {ex.rest_seconds}s{ex.target_rpe ? ` • RPE ${ex.target_rpe}` : ""}</p>
                      {ex.notes && <p className="italic">{ex.notes}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
