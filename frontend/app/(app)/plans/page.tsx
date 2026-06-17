"use client"
import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useAuth } from "@/components/auth/auth-provider"
import { listPlans, generatePlan, activatePlan, archivePlan, type TrainingPlanSummary } from "@/lib/api/plans"
import { PageHeader } from "@/components/shared/page-header"
import { LoadingSkeleton } from "@/components/shared/loading-skeleton"
import { ErrorState } from "@/components/shared/error-state"
import { EmptyState } from "@/components/shared/empty-state"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Calendar, Loader2, Plus, CheckCircle2, Archive } from "lucide-react"
import Link from "next/link"
import { ApiError } from "@/lib/api/client"

export default function PlansPage() {
  const { user } = useAuth()
  const userId = user?.id || ""
  const qc = useQueryClient()
  const [sg, setSg] = useState(false)
  const [gn, setGn] = useState("")
  const [gw, setGw] = useState(4)
  const [gp, setGp] = useState("")
  const [ge, setGe] = useState("")

  const { data, isLoading, error } = useQuery({ queryKey: ["tp", userId], queryFn: () => listPlans(userId), enabled: !!userId })
  const gm = useMutation({ mutationFn: () => generatePlan(userId, { name: gn || undefined, duration_weeks: gw, additional_preferences: gp || undefined }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["tp"] }); setSg(false); setGe("") }, onError: (e: unknown) => { setGe(e instanceof ApiError ? e.detail || e.message : "Failed") } })
  const am = useMutation({ mutationFn: (id: string) => activatePlan(userId, id), onSuccess: () => qc.invalidateQueries({ queryKey: ["tp"] }) })
  const arm = useMutation({ mutationFn: (id: string) => archivePlan(userId, id), onSuccess: () => qc.invalidateQueries({ queryKey: ["tp"] }) })

  if (isLoading) return <LoadingSkeleton />
  if (error) return <ErrorState title="Failed to load plans" />
  const plans = data?.items || []

  return (
    <div className="flex flex-col gap-6 p-4 md:p-6">
      <PageHeader title="Training Plans" description="AI-generated training programs" actions={<Button onClick={() => setSg(!sg)}><Plus className="mr-2 size-4" />Generate Plan</Button>} />
      {sg && (
        <Card><CardHeader><CardTitle className="text-lg">Generate AI Plan</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div><Label>Name (optional)</Label><Input value={gn} onChange={e => setGn(e.target.value)} placeholder="My Plan" /></div>
              <div><Label>Duration (weeks)</Label><Input type="number" min={1} max={12} value={gw} onChange={e => setGw(Number(e.target.value))} /></div>
            </div>
            <div><Label>Additional Preferences</Label><Input value={gp} onChange={e => setGp(e.target.value)} placeholder="e.g. Focus on upper body, limit to 60 min sessions" /></div>
            {ge && <p className="text-sm text-red-500">{ge}</p>}
            <div className="flex gap-2">
              <Button onClick={() => gm.mutate()} disabled={gm.isPending}>{gm.isPending && <Loader2 className="mr-2 size-4 animate-spin" />}Generate</Button>
              <Button variant="outline" onClick={() => { setSg(false); setGe("") }}>Cancel</Button>
            </div>
          </CardContent></Card>
      )}
      {plans.length === 0 ? (
        <EmptyState icon={Calendar} title="No Training Plans" description="Generate your first AI-powered training plan to get started." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {plans.map((p) => (
            <Card key={p.id}><CardHeader><div className="flex items-center justify-between"><CardTitle className="text-base">{p.name}</CardTitle><Badge variant={p.status === "active" ? "default" : p.status === "draft" ? "secondary" : "outline"}>{p.status}</Badge></div><CardDescription>{p.goal} | {p.duration_weeks}w | {p.weekly_frequency}x/wk | v{p.version}</CardDescription></CardHeader>
              <CardContent className="flex gap-2">
                <Link href={`/plans/${p.id}`}><Button variant="outline" size="sm">Details</Button></Link>
                {p.status !== "active" && <Button size="sm" onClick={() => am.mutate(p.id)} disabled={am.isPending}><CheckCircle2 className="mr-1 size-3" />Activate</Button>}
                {p.status !== "archived" && <Button size="sm" variant="ghost" onClick={() => arm.mutate(p.id)} disabled={arm.isPending}><Archive className="mr-1 size-3" />Archive</Button>}
              </CardContent></Card>
          ))}
        </div>
      )}
    </div>
  )
}
