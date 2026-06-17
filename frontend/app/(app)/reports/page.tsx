"use client"
import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useAuth } from "@/components/auth/auth-provider"
import { generateReport, listReports, type WeeklyReport } from "@/lib/api/reports"
import { PageHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingSkeleton } from "@/components/shared/loading-skeleton"
import { ErrorState } from "@/components/shared/error-state"
import { EmptyState } from "@/components/shared/empty-state"
import { Loader2, Sparkles, FileText, Dumbbell } from "lucide-react"
import { ApiError } from "@/lib/api/client"

export default function ReportsPage() {
  const { user } = useAuth()
  const uid = user?.id || ""
  const qc = useQueryClient()
  const [gs, setGs] = useState("")
  const [ge, setGe] = useState("")
  const [gerr, setGerr] = useState("")
  const { data, isLoading, error } = useQuery({ queryKey:["wr",uid], queryFn:()=>listReports(uid), enabled:!!uid })
  const gm = useMutation({ mutationFn:()=>generateReport(uid, gs||undefined, ge||undefined), onSuccess:()=>{qc.invalidateQueries({queryKey:["wr"]});setGerr("")}, onError:(e:unknown)=>{setGerr(e instanceof ApiError?e.detail||e.message:"Failed")} })
  if (isLoading) return <LoadingSkeleton />
  if (error) return <ErrorState title="Failed to load reports" />
  const items = data?.items||[]

  return <div className="flex flex-col gap-6 p-4 md:p-6">
    <PageHeader title="Weekly Reports" description="AI-generated training summaries" />
    <Card><CardHeader><CardTitle className="text-lg">Generate Report</CardTitle></CardHeader><CardContent className="flex flex-col gap-4"><div className="grid gap-4 sm:grid-cols-2"><div><Label>Start</Label><Input type="date" value={gs} onChange={e=>setGs(e.target.value)}/></div><div><Label>End</Label><Input type="date" value={ge} onChange={e=>setGe(e.target.value)}/></div></div>{gerr&&<p className="text-sm text-red-500">{gerr}</p>}<Button onClick={()=>gm.mutate()} disabled={gm.isPending} className="w-full sm:w-auto">{gm.isPending?<Loader2 className="mr-2 size-4 animate-spin"/>:<Sparkles className="mr-2 size-4"/>}Generate</Button></CardContent></Card>
    {items.length===0?<EmptyState icon={Dumbbell} title="No Reports Yet" description="Generate your first weekly training report"/>:<div className="grid gap-4">{items.map(r=><Card key={r.id}><CardHeader><div className="flex items-center justify-between"><CardTitle className="text-base">{r.period_start} to {r.period_end}</CardTitle><div className="flex gap-2"><Badge variant={r.source==="ai"?"default":"secondary"}>{r.source==="ai"?<Sparkles className="mr-1 size-3"/>:<FileText className="mr-1 size-3"/>}{r.source}</Badge><Badge variant="outline">{r.status}</Badge></div></div><CardDescription>{r.summary}</CardDescription></CardHeader><CardContent>{r.highlights?.length>0&&<div className="mb-2"><p className="text-xs font-medium text-muted-foreground mb-1">Highlights</p><ul className="list-disc pl-4 text-sm space-y-1">{r.highlights.slice(0,3).map((h,i)=><li key={i}>{h}</li>)}</ul></div>}{r.recommendations?.length>0&&<div><p className="text-xs font-medium text-muted-foreground mb-1">Recommendations</p><ul className="list-disc pl-4 text-sm space-y-1">{r.recommendations.slice(0,3).map((rec,i)=><li key={i}>{rec}</li>)}</ul></div>}</CardContent></Card>)}</div>}
  </div>
}
