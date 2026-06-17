import { apiFetch } from "./client"

export interface FitnessProfile {
  id: string
  user_id: string
  goal: string
  experience_level: string
  weekly_frequency: number
  session_duration_minutes: number
  available_equipment: string[]
  target_muscles: string[]
  excluded_exercises: string[]
  limitations: string | null
  created_at: string
  updated_at: string
}

export interface FitnessProfileUpsert {
  goal: string
  experience_level: string
  weekly_frequency: number
  session_duration_minutes: number
  available_equipment: string[]
  target_muscles: string[]
  excluded_exercises: string[]
  limitations?: string | null
}

export async function getProfile(userId: string): Promise<FitnessProfile | null> {
  try {
    return await apiFetch<FitnessProfile>(`/users/${userId}/fitness-profile`)
  } catch (e: unknown) {
    if (e instanceof Error && "status" in e && (e as { status: number }).status === 404) return null
    throw e
  }
}

export async function upsertProfile(userId: string, data: FitnessProfileUpsert): Promise<FitnessProfile> {
  return apiFetch<FitnessProfile>(`/users/${userId}/fitness-profile`, {
    method: "PUT",
    body: JSON.stringify(data),
  })
}
