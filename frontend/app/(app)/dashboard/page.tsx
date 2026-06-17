"use client"
import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@/components/auth/auth-provider"
import { getOverview, getWeeklyActivity, type AnalyticsOverview, type WeeklyAnalyticsPoint } from "@/lib/api/analytics"
import { listPlans } from "@/lib/api/plans"
import { getCurrentWorkout } from "@/lib/api/workouts"
import { MetricCard } from "@/components/shared/metric-card"
import { PageHeader } from "@/components/shared/page-header"
import { LoadingSkeleton } from "@/components/shared/loading-skeleton"
import { ErrorState } from "@/components/shared/error-state"
import { EmptyState } from "@/components/shared/empty-state"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Dumbbell, BarChart3, Target, Flame, TrendingUp, Calendar } from "lucide-react"
import Link from "next/link"

export default function DashboardPage() {
  const { user } = useAuth()
  const userId = user?.id || ""
  const { data: overview, isLoading, error } = useQuery<AnalyticsOverview>({ queryKey: ["analyticsOverview", userId], queryFn: () => getOverview(userId), enabled: !!userId })
  const { data: weekly } = useQuery<WeeklyAnalyticsPoint[]>({ queryKey: ["weeklyAnalytics", userId], queryFn: () => getWeeklyActivity(userId, 4), enabled: !!userId })
  const { data: plans } = useQuery({ queryKey: ["trainingPlans", userId], queryFn: () => listPlans(userId, "active"), enabled: !!userId })
  const { data: currentWorkout } = useQuery({ queryKey: ["currentWorkout", userId], queryFn: () => getCurrentWorkout(userId), enabled: !!userId })

  if (isLoading) return <LoadingSkeleton />
  if (error) return <ErrorState title="Failed to load dashboard" />

  return (
    <div className="flex flex-col gap-6 p-4 md:p-6">
      <PageHeader title={`Welcome, ${user?.display_name?.split(" ")[0] || "Athlete"}`} description="Your training at a glance" />

      {currentWorkout && (
        <Card className="border-lime-500/30 bg-lime-50/30">
          <CardContent className="flex items-center justify-between p-4">
            <div><p className="font-semibold text-sm text-lime-700">Workout in Progress</p><p className="text-sm text-muted-foreground">{currentWorkout.exercises?.length || 0} exercises</p></div>
            <Link href="/workouts/current"><Button size="sm">Resume</Button></Link>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Workouts (28d)" value={String(overview?.completed_workouts || 0)} icon={Dumbbell} />
        <MetricCard label="Total Volume" value={((overview?.total_volume || 0) > 999 ? `${((overview?.total_volume || 0) / 1000).toFixed(1)}k` : String((overview?.total_volume || 0)))} icon={BarChart3} />
        <MetricCard label="Completed Sets" value={String(overview?.completed_sets || 0)} icon={Target} />
        <MetricCard label="Current Streak" value={`${overview?.current_streak_days || 0} days`} icon={Flame} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card><CardHeader><CardTitle className="text-lg">Weekly Activity</CardTitle></CardHeader><CardContent>{weekly && weekly.length > 0 ? <div className="flex items-end gap-2 h-40">{weekly.slice(-4).map((w, i) => { const max = Math.max(...weekly.map(x => x.completed_workouts), 1); const pct = (w.completed_workouts / max) * 100; return <div key={i} className="flex-1 flex flex-col items-center gap-1"><span className="text-xs font-medium">{w.completed_workouts}</span><div className="w-full bg-lime-500 rounded-t" style={{ height: `${Math.max(pct, 4)}%` }} /><span className="text-xs text-muted-foreground">{new Date(w.week_start).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span></div> })}</div> : <EmptyState icon={Dumbbell} title="No recent activity" description="Complete your first workout to see weekly activity" />}</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-lg">Quick Actions</CardTitle></CardHeader><CardContent className="flex flex-col gap-2">{plans && plans.items.length > 0 ? <><Link href="/plans"><Button variant="outline" className="w-full justify-start"><Calendar className="mr-2 size-4" />View Training Plans</Button></Link><Link href="/workouts/current"><Button variant="outline" className="w-full justify-start"><Dumbbell className="mr-2 size-4" />Start Workout</Button></Link></> : <><Link href="/plans"><Button variant="outline" className="w-full justify-start"><Calendar className="mr-2 size-4" />Generate Your First Plan</Button></Link><Link href="/profile"><Button variant="outline" className="w-full justify-start"><Target className="mr-2 size-4" />Set Up Fitness Profile</Button></Link></>}<Link href="/analytics"><Button variant="outline" className="w-full justify-start"><TrendingUp className="mr-2 size-4" />View Analytics</Button></Link></CardContent></Card>
      </div>

      {overview && overview.completed_workouts === 0 && (
        <Card><CardContent className="p-6 text-center"><EmptyState icon={Target} title="Start Your Fitness Journey" description="Set up your fitness profile and generate your first training plan to get started." /><div className="flex gap-3 justify-center mt-4"><Link href="/profile"><Button>Set Up Profile</Button></Link><Link href="/plans"><Button variant="outline">Generate Plan</Button></Link></div></CardContent></Card>
      )}
    </div>
  )
}
