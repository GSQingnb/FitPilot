"use client"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useAuth } from "@/components/auth/auth-provider"
import { getProfile, upsertProfile, type FitnessProfile, type FitnessProfileUpsert } from "@/lib/api/profile"
import { PageHeader } from "@/components/shared/page-header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingSkeleton } from "@/components/shared/loading-skeleton"
import { Loader2, Save } from "lucide-react"
import { useState, useEffect } from "react"

const GOALS = ["muscle_gain","fat_loss","strength","general_fitness"]
const LEVELS = ["beginner","intermediate","advanced"]
const EQ = ["bodyweight","dumbbell","barbell","machine","cable","kettlebell","resistance_band","other"]

export default function ProfilePage() {
  const { user } = useAuth()
  const uid = user?.id || ""
  const qc = useQueryClient()
  const { data: profile, isLoading } = useQuery<FitnessProfile|null>({ queryKey:["profile",uid], queryFn:()=>getProfile(uid), enabled:!!uid })
  const [f, setF] = useState<FitnessProfileUpsert>({goal:"muscle_gain",experience_level:"beginner",weekly_frequency:3,session_duration_minutes:60,available_equipment:[],target_muscles:[],excluded_exercises:[],limitations:null})
  const [saved, setSaved] = useState(false)

  useEffect(() => { if (profile) setF({goal:profile.goal,experience_level:profile.experience_level,weekly_frequency:profile.weekly_frequency,session_duration_minutes:profile.session_duration_minutes,available_equipment:profile.available_equipment,target_muscles:profile.target_muscles,excluded_exercises:profile.excluded_exercises,limitations:profile.limitations}) }, [profile])

  const m = useMutation({ mutationFn: (d: FitnessProfileUpsert) => upsertProfile(uid, d), onSuccess: () => { qc.invalidateQueries({ queryKey: ["profile"] }); setSaved(true); setTimeout(() => setSaved(false), 3000) } })
  const toggle = (item: string) => setF(f => ({...f, available_equipment: f.available_equipment.includes(item) ? f.available_equipment.filter(e => e !== item) : [...f.available_equipment, item] }))
  if (isLoading) return <LoadingSkeleton />

  return <div className="flex flex-col gap-6 p-4 md:p-6 max-w-2xl">
    <PageHeader title="Fitness Profile" description={profile?"Update your fitness settings":"Set up your fitness profile"} />
    <form onSubmit={e => { e.preventDefault(); m.mutate(f) }}>
      <Card><CardHeader><CardTitle className="text-lg">Training Preferences</CardTitle></CardHeader><CardContent className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div><Label>Goal</Label><select value={f.goal} onChange={e => setF(f => ({...f, goal: e.target.value}))} className="w-full border rounded-md p-2 text-sm">{GOALS.map(g => <option key={g} value={g}>{g}</option>)}</select></div>
          <div><Label>Experience</Label><select value={f.experience_level} onChange={e => setF(f => ({...f, experience_level: e.target.value}))} className="w-full border rounded-md p-2 text-sm">{LEVELS.map(l => <option key={l} value={l}>{l}</option>)}</select></div>
          <div><Label>Weekly Frequency</Label><Input type="number" min={1} max={7} value={f.weekly_frequency} onChange={e => setF(f => ({...f, weekly_frequency: Number(e.target.value)}))} /></div>
          <div><Label>Duration (min)</Label><Input type="number" min={15} max={240} value={f.session_duration_minutes} onChange={e => setF(f => ({...f, session_duration_minutes: Number(e.target.value)}))} /></div>
        </div>
        <div><Label className="mb-2 block">Equipment</Label><div className="flex flex-wrap gap-2">{EQ.map(eq => <button key={eq} type="button" onClick={() => toggle(eq)} className={`px-3 py-1 text-xs rounded-full border transition-colors ${f.available_equipment.includes(eq)?"bg-lime-500 text-white border-lime-500":"bg-background border-border hover:border-lime-300"}`}>{eq}</button>)}</div></div>
        <div><Label>Limitations (optional)</Label><Input value={f.limitations||""} onChange={e => setF(f => ({...f, limitations: e.target.value || null}))} placeholder="e.g. Knee sensitivity" /></div>
        <Button type="submit" disabled={m.isPending} className="w-full sm:w-auto">{m.isPending?<Loader2 className="mr-2 size-4 animate-spin"/>:<Save className="mr-2 size-4"/>}{m.isPending?"Saving...":saved?"Saved!":"Save Profile"}</Button>
      </CardContent></Card>
    </form>
  </div>
}
