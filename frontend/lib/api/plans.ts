import { apiFetch } from "./client"

export interface TrainingPlanSummary {
  id: string
  user_id: string
  name: string
  goal: string
  duration_weeks: number
  weekly_frequency: number
  status: string
  source: string
  version: number
  created_at: string
  updated_at: string
}

export interface PlannedExercise {
  id: string
  exercise_id: string
  exercise_name: string
  primary_muscle: string
  equipment: string
  order_index: number
  sets: number
  reps_min: number
  reps_max: number
  rest_seconds: number
  target_rpe: number | null
  notes: string | null
}

export interface TrainingDay {
  id: string
  day_index: number
  title: string
  notes: string | null
  exercises: PlannedExercise[]
}

export interface TrainingPlanDetail extends TrainingPlanSummary {
  days: TrainingDay[]
}

export interface PlanListResponse {
  total: number
  limit: number
  offset: number
  items: TrainingPlanSummary[]
}

export interface GeneratePlanRequest {
  name?: string
  duration_weeks?: number
  additional_preferences?: string
}

export async function listPlans(userId: string, status?: string): Promise<PlanListResponse> {
  const params = status ? `?status=${status}` : ""
  return apiFetch<PlanListResponse>(`/users/${userId}/training-plans${params}`)
}

export async function getPlan(planId: string): Promise<TrainingPlanDetail> {
  return apiFetch<TrainingPlanDetail>(`/training-plans/${planId}`)
}

export async function generatePlan(userId: string, data: GeneratePlanRequest): Promise<TrainingPlanDetail> {
  return apiFetch<TrainingPlanDetail>(`/users/${userId}/training-plans/generate`, {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export async function activatePlan(userId: string, planId: string): Promise<TrainingPlanDetail> {
  return apiFetch<TrainingPlanDetail>(`/users/${userId}/training-plans/${planId}/activate`, { method: "POST" })
}

export async function archivePlan(userId: string, planId: string): Promise<TrainingPlanDetail> {
  return apiFetch<TrainingPlanDetail>(`/users/${userId}/training-plans/${planId}/archive`, { method: "POST" })
}
