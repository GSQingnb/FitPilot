# FitPilot Demo Guide

This guide walks through a complete demonstration of FitPilot's features. Follow each step in order.

**Prerequisites**: Docker running, Anthropic API key configured in `.env`, services started (`docker compose up -d`).

## Step 1: Start the System

```bash
docker compose up -d
# Wait for all services to be healthy
docker compose ps
```

Open **http://localhost** in your browser.

## Step 2: Register

1. Click "Create one" on the login page
2. Enter email, name, and password (8+ characters)
3. Click "Register"

You should be redirected to the Dashboard with an empty state.

## Step 3: Set Up Fitness Profile

1. Click "Fitness Profile" in the sidebar
2. Configure your profile:
   - **Goal**: muscle_gain, fat_loss, strength, or general_fitness
   - **Experience**: beginner, intermediate, or advanced
   - **Weekly Frequency**: 3-4 days
   - **Session Duration**: 45-90 minutes
   - **Equipment**: Select what you have (e.g., dumbbell, bodyweight)
3. Click "Save Profile"

## Step 4: Generate a Training Plan

1. Click "Training Plans" in the sidebar
2. Click "Generate Plan"
3. Set duration (4 weeks recommended) and any preferences
4. Click "Generate"

> ⚠️ **Requires valid Anthropic API key**. If you see a 502 error, your API key is missing or invalid. Check `.env`.

Expected: A new plan appears with AI-generated training days and exercises.

## Step 5: View Plan Details

1. Click "Details" on the generated plan
2. Review the training days, exercises, sets, reps, and rest times
3. Notice the plan status badge (draft)

## Step 6: Activate the Plan

1. On the plan list or detail page, click "Activate"
2. The plan status changes to "active"

Only one plan can be active at a time. Activating a new plan archives the old one.

## Step 7: Start a Workout

1. Click "Current Workout" in the sidebar
2. Select your active plan and a training day
3. Click "Start Workout"

The system creates a workout session and copies planned exercises as workout exercises.

## Step 8: Record Sets

1. Find the first exercise in your workout
2. Enter:
   - **Weight** (kg) — e.g., 20
   - **Reps** — e.g., 10
   - **RPE** — e.g., 7 (how hard it felt, 1-10)
3. Click the + button to add the set
4. Repeat for additional sets

Each set is saved immediately. You can delete a set by clicking the trash icon.

## Step 9: Complete Exercises

After finishing all sets for an exercise, click the checkmark to mark it complete. You can also skip exercises with the skip button.

## Step 10: Finish the Workout

1. Click "Complete" at the top of the page
2. Optionally add notes and rate perceived difficulty (1-10)
3. Click "Confirm Complete"

The workout session is now completed. Stats (total sets, reps, volume) are displayed.

## Step 11: View Workout History

1. Click "Workout History" in the sidebar
2. Browse your completed sessions
3. Click any session to see full details (every set with weight/reps/RPE)

## Step 12: Check Analytics

1. Click "Analytics" in the sidebar
2. Review:
   - Total workouts, volume, sets, reps
   - Current streak
   - Weekly activity table

> Note: Analytics only include completed workouts. Empty state is shown if no workouts exist.

## Step 13: Generate a Weekly Report

1. Click "Weekly Reports" in the sidebar
2. Set a date range (or leave empty for last full week)
3. Click "Generate Report"

> ⚠️ Requires valid API key. Without it, a rule-based fallback report is generated.

Review the summary, highlights, issues, and recommendations.

## Step 14: Use the AI Coach

1. Click "AI Coach" in the sidebar
2. Ask a fitness question, e.g.:
   - "What's the best way to progressive overload with only dumbbells?"
   - "How do I know if I'm recovering enough between sessions?"
3. The coach responds with domain-aware advice
4. Safety-triggering questions (e.g., about pain or injury) will show a safety disclaimer

> ⚠️ Requires valid API key. Returns 502 error without it.

## Step 15: Logout

1. Click your avatar in the bottom-left of the sidebar
2. Click "Sign out"
3. You are redirected to the login page
4. Trying to access `/dashboard` redirects back to login

## What to Show in a Demo

If you have limited time, focus on:

1. Register → Profile → Generate Plan → Activate → Start Workout → Add Sets → Complete → History
2. Analytics dashboard
3. AI Coach with a sample question
4. Logout

## Steps That Fail Without API Key

These features require a valid `ANTHROPIC_API_KEY`:

- Plan generation (Step 4) — returns 502
- Weekly report generation (Step 13) — falls back to rule-based
- AI Coach (Step 14) — returns 502

All other features (auth, profile, workout tracking, analytics, history) work without an API key.
