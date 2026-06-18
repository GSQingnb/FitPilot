# FitPilot System Architecture

## Deployment Architecture

```mermaid
graph TB
    Browser[Browser :80] --> Nginx[Nginx Reverse Proxy]
    Nginx -->|/| Frontend[Next.js :3000]
    Nginx -->|/api/| Backend[FastAPI :8000]
    Backend --> PG[(PostgreSQL :5432)]
    Backend --> Redis[(Redis :6379)]
    Backend --> ChromaDB[(ChromaDB :8000)]
    Prometheus[Prometheus :9090] --> Backend
```

**Nginx** is the single entry point. The `/api/` prefix is stripped before forwarding to FastAPI, enabling same-origin deployment without CORS issues. The frontend is built with `NEXT_PUBLIC_API_BASE_URL=/api` so all browser API calls go to the same host.

**FastAPI** handles all business logic. It uses async SQLAlchemy for PostgreSQL, Redis for token storage and rate limiting, and ChromaDB for the fitness knowledge base (RAG).

**PostgreSQL** stores all business data: users, profiles, exercises, training plans, workout records, and reports.

**Redis** stores refresh token blacklist entries, generation locks, login attempt counters, and conversational working memory.

**ChromaDB** stores the fitness knowledge base (exercise guides, training principles) for semantic search via the `/api/search` endpoint.

## Agent Workflow

```mermaid
graph TD
    User[User Message] --> Intent[Intent Recognition]
    Intent -->|LLM 70%| L[LLM Semantic]
    Intent -->|Embedding 20%| E[Embedding Similarity]
    Intent -->|Pattern 10%| P[Pattern Match]
    L --> Vote[Weighted Vote]
    E --> Vote
    P --> Vote
    Vote -->|Low Confidence| Other[OTHER intent]
    Vote --> Router[Agent Router]
    Router -->|general_question| Coach[CoachAgent]
    Router -->|exercise_query| Coach
    Router -->|plan_generation| Plan[PlanAgent]
    Router -->|plan_adjustment| Plan
    Router -->|progress_review| Progress[ProgressAgent]
    Router -->|safety_concern| CoachSafe[CoachAgent + Safety]
    Router -->|greeting/feedback| Coach
    Coach --> KB[Knowledge Base RAG]
    Plan --> KB
    Progress --> KB
    CoachSafe --> Safety[Safety Disclaimer]
    Coach --> Response[Response]
    Plan --> Response
    Progress --> Response
```

The three-way intent fusion (LLM 70%, Embedding 20%, Pattern 10%) runs LLM and embedding in parallel, then weighted-votes to select the final intent. Low-confidence results degrade to `OTHER`.

The safety layer activates when `safety_concern` is detected or keywords (pain, injury, medical terms) are matched. It prepends a safety disclaimer before the agent's response.

## Training Plan Generation Flow

```mermaid
graph TD
    Profile[User Fitness Profile] --> Filter[Filter Candidates]
    Filter -->|equipment + experience| Candidates[Candidate Exercises]
    Candidates --> LLM[LLM Structured Generation]
    LLM -->|JSON Schema| Parse[Pydantic Validation]
    Parse -->|Fail| Retry[Retry up to 2x]
    Parse -->|Pass| BizRules[Business Rule Validation]
    Retry -->|Retry| LLM
    Retry -->|Still Fail| Error502[502 Error]
    BizRules -->|Fail| Retry
    BizRules -->|Pass| Save[Txn Save]
    Save -->|Success| Response[Plan Created]
    Save -->|Error| Rollback[Rollback]
```

Key constraints:
- Only exercises matching the user's equipment and experience are candidates
- The LLM must output `exercise_id` from the candidate list — no invented exercises
- Business rules validate set counts, rep ranges, RPE, and training day structure
- Everything saves in a single transaction — partial plans are never persisted

## Core Business Data Flow

```mermaid
graph LR
    Profile[Profile] --> PlanGen[Plan Generation]
    PlanGen --> PlanActive[Active Plan]
    PlanActive --> Workout[Workout Session]
    Workout --> Sets[Workout Sets]
    Sets --> Analytics[Analytics Engine]
    Analytics --> Report[Weekly Report]
    Report --> Profile
```

1. User sets up their fitness profile (goals, equipment, experience)
2. AI generates a structured training plan from filtered exercises
3. User activates the plan
4. Workout sessions copy planned exercises as workout exercises
5. User records sets with weight, reps, and RPE
6. Analytics aggregates completed sessions and sets via SQL
7. Weekly reports snapshot analytics + LLM summary into persistent records
