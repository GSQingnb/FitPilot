import { apiFetch } from "./client"

export interface WorkoutSet {
  id: string
  set_index: number
  set_type: string
  weight_kg: number | null
  reps: number | null
  duration_seconds: number | null
  distance_meters: number | null
  rpe: number | null
  is_completed: boolean
  notes: string | null
}

export interface WorkoutExercise {
  id: string
  exercise_id: string
  exercise_name: string
  primary_muscle: string
  equipment: string
  status: string
  order_index: number
  planned_sets: number | null
  planned_reps_min: number | null
  planned_reps_max: number | null
  notes: string | null
  sets: WorkoutSet[]
}

export interface WorkoutStats {
  total_exercises: number
  completed_exercises: number
  skipped_exercises: number
  total_sets: number
  completed_sets: number
  total_reps: number
  total_volume: number
}

export interface WorkoutSessionDetail {
  id: string
  user_id: string
  status: string
  started_at: string
  completed_at: string | null
  duration_seconds: number | null
  training_plan_id: string | null
  training_day_id: string | null
  training_day_title: string | null
  exercise_count: number
  completed_set_count: number
  notes: string | null
  perceived_difficulty: number | null
  exercises: WorkoutExercise[]
  stats: WorkoutStats
}

export interface WorkoutSessionSummary {
  id: string
  user_id: string
  status: string
  started_at: string
  completed_at: string | null
  duration_seconds: number | null
  training_plan_id: string | null
  training_day_id: string | null
  training_day_title: string | null
  exercise_count: number
  completed_set_count: number
  notes: string | null
  perceived_difficulty: number | null
}

export interface WorkoutListResponse {
  total: number
  limit: number
  offset: number
  items: WorkoutSessionSummary[]
}

export async function startWorkout(userId: string, trainingPlanId: string, trainingDayId: string): Promise<WorkoutSessionDetail> {
  return apiFetch<WorkoutSessionDetail>(`/users/${userId}/workouts/start`, {
    method: "POST",
    body: JSON.stringify({ training_plan_id: trainingPlanId, training_day_id: trainingDayId }),
  })
}

export async function getCurrentWorkout(userId: string): Promise<WorkoutSessionDetail | null> {
  try {
    return await apiFetch<WorkoutSessionDetail>(`/users/${userId}/workouts/current`)
  } catch (e: unknown) {
    if (e instanceof Error && "status" in e && (e as { status: number }).status === 404) return null
    throw e
  }
}

export async function getWorkout(userId: string, sessionId: string): Promise<WorkoutSessionDetail> {
  return apiFetch<WorkoutSessionDetail>(`/users/${userId}/workouts/${sessionId}`)
}

export async function listWorkouts(userId: string, params?: Record<string, string>): Promise<WorkoutListResponse> {
  const qs = params ? "?" + new URLSearchParams(params).toString() : ""
  return apiFetch<WorkoutListResponse>(`/users/${userId}/workouts${qs}`)
}

export async function addSet(sessionId: string, exerciseId: string, data: {
  set_index: number; set_type?: string; weight_kg?: number | null; reps?: number | null;
  duration_seconds?: number | null; rpe?: number | null; notes?: string | null;
}): Promise<WorkoutSet> {
  return apiFetch<WorkoutSet>(`/workouts/${sessionId}/exercises/${exerciseId}/sets`, {
    method: "POST", body: JSON.stringify(data),
  })
}

export async function updateSet(sessionId: string, setId: string, data: Record<string, unknown>): Promise<WorkoutSet> {
  return apiFetch<WorkoutSet>(`/workouts/${sessionId}/sets/${setId}`, {
    method: "PUT", body: JSON.stringify(data),
  })
}

export async function deleteSet(sessionId: string, setId: string): Promise<void> {
  return apiFetch(`/workouts/${sessionId}/sets/${setId}`, { method: "DELETE" })
}

export async function completeWorkout(sessionId: string, notes?: string, difficulty?: number): Promise<WorkoutSessionDetail> {
  return apiFetch<WorkoutSessionDetail>(`/workouts/${sessionId}/complete`, {
    method: "POST", body: JSON.stringify({ notes, perceived_difficulty: difficulty }),
  })
}

export async function cancelWorkout(sessionId: string, reason?: string): Promise<WorkoutSessionDetail> {
  return apiFetch<WorkoutSessionDetail>(`/workouts/${sessionId}/cancel`, {
    method: "POST", body: JSON.stringify({ reason }),
  })
}

export async function completeExercise(sessionId: string, exerciseId: string): Promise<void> {
  return apiFetch(`/workouts/${sessionId}/exercises/${exerciseId}/complete`, { method: "POST" })
}

export async function skipExercise(sessionId: string, exerciseId: string, reason?: string): Promise<void> {
  return apiFetch(`/workouts/${sessionId}/exercises/${exerciseId}/skip`, {
    method: "POST", body: JSON.stringify({ reason }),
  })
}
