"use client"
import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@/components/auth/auth-provider"
import { getOverview, getWeeklyActivity, type AnalyticsOverview, type WeeklyAnalyticsPoint } from "@/lib/api/analytics"
import { PageHeader } from "@/components/shared/page-header"
import { MetricCard } from "@/components/shared/metric-card"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { LoadingSkeleton } from "@/components/shared/loading-skeleton"
import { ErrorState } from "@/components/shared/error-state"
import { EmptyState } from "@/components/shared/empty-state"
import { Dumbbell, Target, TrendingUp, Flame, BarChart3, Timer } from "lucide-react"

export default function AnalyticsPage() {
  const { user } = useAuth()
  const userId = user?.id || ""
  const { data: overview, isLoading, error } = useQuery<AnalyticsOverview>({ queryKey: ["ao", userId], queryFn: () => getOverview(userId), enabled: !!userId })
  const { data: weekly } = useQuery<WeeklyAnalyticsPoint[]>({ queryKey: ["wa", userId], queryFn: () => getWeeklyActivity(userId, 8), enabled: !!userId })
  if (isLoading) return <LoadingSkeleton />
  if (error) return <ErrorState title="Failed to load analytics" />
  if (!overview || overview.completed_workouts === 0) return <div className="flex flex-col gap-6 p-4 md:p-6"><PageHeader title="Analytics" description="Training progress and trends" /><EmptyState icon={Dumbbell} title="No Data Yet" description="Complete your first workout to see analytics" /></div>
  return (
    <div className="flex flex-col gap-6 p-4 md:p-6">
      <PageHeader title="Analytics" description={`${overview.period.start} to ${overview.period.end}`} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Workouts" value={String(overview.completed_workouts)} icon={Dumbbell} />
        <MetricCard label="Total Volume" value={(overview.total_volume > 999 ? `${(overview.total_volume / 1000).toFixed(1)}k` : String(overview.total_volume)) + " kg"} icon={BarChart3} />
        <MetricCard label="Completed Sets" value={String(overview.completed_sets)} icon={Target} />
        <MetricCard label="Total Reps" value={String(overview.total_reps)} icon={TrendingUp} />
        <MetricCard label="Avg RPE" value={overview.average_rpe?.toFixed(1) || "-"} icon={Flame} />
        <MetricCard label="Streak" value={`${overview.current_streak_days} days`} icon={Flame} />
        <MetricCard label="Best Streak" value={`${overview.longest_streak_days} days`} icon={Timer} />
        <MetricCard label="Avg Duration" value={`${Math.round(overview.average_duration_seconds / 60)} min`} icon={Timer} />
      </div>
      <Card><CardHeader><CardTitle className="text-lg">Weekly Activity</CardTitle></CardHeader><CardContent>{weekly && weekly.length > 0 ? <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left text-muted-foreground"><th className="py-2">Week</th><th className="py-2">Workouts</th><th className="py-2">Sets</th><th className="py-2">Reps</th><th className="py-2">Volume (kg)</th><th className="py-2">Avg RPE</th><th className="py-2">Duration (min)</th></tr></thead><tbody>{weekly.filter(w => w.completed_workouts > 0).map((w, i) => <tr key={i} className="border-b last:border-0"><td className="py-2 font-medium">{new Date(w.week_start).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</td><td className="py-2">{w.completed_workouts}</td><td className="py-2">{w.completed_sets}</td><td className="py-2">{w.total_reps}</td><td className="py-2">{w.total_volume.toFixed(0)}</td><td className="py-2">{w.average_rpe?.toFixed(1) || "-"}</td><td className="py-2">{Math.round(w.total_duration_seconds / 60)}</td></tr>)}</tbody></table></div> : <EmptyState icon={BarChart3} title="No weekly data" />}</CardContent></Card>
    </div>
  )
}
