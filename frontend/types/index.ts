/**
 * Shared domain types for FitPilot.
 *
 * These mirror the shapes the FastAPI backend is expected to return so the
 * frontend can swap mock functions for real network calls with minimal churn.
 */

export interface User {
  id: string
  displayName: string
  email: string
  /** Optional avatar URL. When absent the UI falls back to initials. */
  avatarUrl?: string
  createdAt: string
}

export type WorkoutStatus = "completed" | "in-progress" | "scheduled" | "skipped"

export interface WorkoutSummary {
  id: string
  title: string
  /** ISO date string. */
  date: string
  /** Primary muscle groups or focus, e.g. "Push", "Legs". */
  focus: string
  status: WorkoutStatus
  /** Duration in minutes. */
  durationMinutes: number
  totalSets: number
  /** Total training volume in kilograms. */
  volumeKg: number
}

export type TrainingPlanLevel = "beginner" | "intermediate" | "advanced"

export interface TrainingPlanSummary {
  id: string
  name: string
  description: string
  level: TrainingPlanLevel
  /** Number of training days per week. */
  daysPerWeek: number
  durationWeeks: number
  /** Progress through the plan, 0-100. */
  progressPercent: number
  isActive: boolean
}

export interface MetricPoint {
  /** Short label for the axis, e.g. "Mon". */
  label: string
  /** Training volume in kilograms for the day. */
  volumeKg: number
}

export interface DashboardOverview {
  user: User
  nextWorkout: WorkoutSummary | null
  activePlan: TrainingPlanSummary | null
  metrics: {
    workoutsThisWeek: number
    workoutsGoal: number
    completedSets: number
    totalVolumeKg: number
    currentStreakDays: number
  }
  recentWorkouts: WorkoutSummary[]
  weeklyActivity: MetricPoint[]
}
