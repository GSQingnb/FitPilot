# FitPilot Agent System

## Overview

FitPilot uses a multi-agent architecture with intent-based routing. When a user sends a message, the system:

1. Recognizes the intent via a three-way fusion strategy
2. Routes to the appropriate specialized agent
3. Optionally invokes the RAG knowledge base
4. Optionally triggers the safety layer
5. Returns the response

## Intent Categories

| Intent | Description | Example |
|--------|-------------|---------|
| `general_question` | General fitness knowledge | "What is progressive overload?" |
| `exercise_query` | Specific exercises, muscles, alternatives | "What muscles does bench press work?" |
| `plan_generation` | Request to create a training plan | "Create a 3-day dumbbell program" |
| `plan_adjustment` | Modify existing plan or replace exercises | "Replace squats, they're too hard" |
| `progress_review` | Analyze performance, plateaus | "My bench hasn't improved in 3 weeks" |
| `safety_concern` | Pain, injury, medical questions | "Sharp knee pain during squats" |
| `greeting` | Hello, hi | "Hello" |
| `feedback` | Positive or negative feedback | "This plan is great!" |
| `other` | Unclassifiable input | (fallback) |

## Intent Recognition

The system uses a **three-way fusion strategy**:

1. **LLM Semantic (70% weight)** — Primary engine. Uses few-shot prompting with Claude to classify intent.
2. **Embedding Similarity (20% weight)** — Compares user message against template embeddings using character n-gram vectors.
3. **Pattern Matching (10% weight)** — Zero-latency keyword matching as a fallback.

LLM and Embedding are called in parallel. Results are merged via weighted voting. If confidence is below threshold (0.5), the intent degrades to `other`.

## Agents

### CoachAgent

Handles: `general_question`, `exercise_query`, `greeting`, `feedback`, `safety_concern`.

Responsibilities:
- General fitness knowledge and terminology
- Exercise form, target muscles, and alternatives
- Safety boundary enforcement
- Fallback agent when no specialist matches

Prompt rules:
- Clear, concise, actionable answers
- Never fabricate medical conditions
- Distinguish between general advice and medical conclusions
- Explicitly state that advice is for general fitness information only

### PlanAgent

Handles: `plan_generation`, `plan_adjustment`.

Responsibilities:
- Generate structured training plans from user profiles
- Explain training splits
- Replace unsuitable exercises
- Reserve capability for future structured plan features

Generation flow:
1. Read user's FitnessProfile
2. Filter exercises by equipment, experience, and exclusions
3. Build a prompt with profile + candidate exercises + JSON schema
4. Call LLM with low temperature (0.3)
5. Validate output with Pydantic
6. Run business rules (equipment checks, rep ranges, etc.)
7. Persist in a single transaction

If validation fails, the LLM is retried up to 2 times with error feedback. After that, a 502 error is returned — no partial plan is saved.

### ProgressAgent

Handles: `progress_review`.

Responsibilities:
- Analyze user-reported training data
- Detect plateaus, under-recovery, or overtraining
- Provide adjustment suggestions
- Distinguish between "factual data" and "inference"

If insufficient data is provided, the agent explicitly lists what's missing (e.g., recent weights, reps, RPE, frequency, sleep).

## Multi-Agent Collaboration

Complex queries can trigger parallel agent execution:

| Query Pattern | Agents Invoked |
|---------------|---------------|
| Plan + exercise question | PlanAgent + CoachAgent |
| Progress + plan adjustment | ProgressAgent + PlanAgent |
| Safety keywords detected | CoachAgent only (safety priority) |

Results from parallel agents are merged and returned as a combined response.

## Safety Layer

The safety system is a reusable module applied uniformly across all agents. It activates when:

- Intent is `safety_concern`
- Message contains any of 21 safety keywords (pain, injury, disease, medication, etc.)

When triggered, a standardized disclaimer is prepended to the response:
- Does not diagnose or guarantee safety
- Recommends stopping aggravating activity
- Advises consulting a doctor, physiotherapist, or qualified professional
- Suggests emergency help for severe symptoms

## Weekly Report Generation

Weekly reports combine SQL analytics with LLM summarization:

1. AnalyticsRepository computes period metrics (workouts, sets, volume, streaks)
2. Comparison metrics are computed for the previous equal-length period
3. A structured prompt with both datasets is sent to the LLM
4. The LLM returns JSON with summary, highlights, issues, and recommendations
5. If the LLM fails, a rule-based fallback generates a basic report
6. Metrics are snapshotted in the `weekly_reports` table

Reports never modify training plans — they are read-only summaries.
