import { apiFetch } from "./client"

export interface AnalyticsOverview {
  period: { start: string; end: string }
  completed_workouts: number
  total_duration_seconds: number
  average_duration_seconds: number
  completed_sets: number
  total_reps: number
  total_volume: number
  average_rpe: number | null
  current_streak_days: number
  longest_streak_days: number
  data_quality: { has_weight_data: boolean; has_rpe_data: boolean }
}

export interface WeeklyAnalyticsPoint {
  week_start: string
  completed_workouts: number
  completed_sets: number
  total_reps: number
  total_volume: number
  average_rpe: number | null
  total_duration_seconds: number
}

export interface ExerciseTrendResponse {
  exercise: { id: string; name: string }
  summary: {
    session_count: number; completed_set_count: number; total_reps: number
    total_volume: number; max_weight: number | null; best_set_reps: number | null
    average_rpe: number | null; last_performed_at: string | null
  }
  trend: { date: string; max_weight: number | null; total_volume: number; total_reps: number; average_rpe: number | null }[]
  trend_direction: string
}

export interface MuscleDistributionItem {
  primary_muscle: string
  completed_sets: number
  total_reps: number
  total_volume: number
  percentage_by_sets: number
}

export async function getOverview(userId: string, from?: string, to?: string): Promise<AnalyticsOverview> {
  const params = new URLSearchParams()
  if (from) params.set("date_from", from)
  if (to) params.set("date_to", to)
  const qs = params.toString() ? "?" + params.toString() : ""
  return apiFetch<AnalyticsOverview>(`/users/${userId}/analytics/overview${qs}`)
}

export async function getWeeklyActivity(userId: string, weeks = 8): Promise<WeeklyAnalyticsPoint[]> {
  return apiFetch<WeeklyAnalyticsPoint[]>(`/users/${userId}/analytics/weekly?weeks=${weeks}`)
}

export async function getExerciseTrend(userId: string, exerciseId: string): Promise<ExerciseTrendResponse> {
  return apiFetch<ExerciseTrendResponse>(`/users/${userId}/analytics/exercises/${exerciseId}`)
}

export async function getMuscleDistribution(userId: string): Promise<MuscleDistributionItem[]> {
  return apiFetch<MuscleDistributionItem[]>(`/users/${userId}/analytics/muscles`)
}
