# CLAUDE.md — Yarn Selection AI Agent System
### Complete Project Context: Business Case, Architecture, Technology Stack, and Build Plan

---

## 1. Business Context

A garment factory imports yarn directly from external importers/exporters. A **yarn tech** currently manually selects and approves yarn by searching a full database of yarn options against order requirements. This process is slow and doesn't scale.

**Goal:** Automate the yarn tech's selection process — NOT fully replace their judgment, but give them a sorted, ranked shortlist of suitable yarns instead of forcing them to manually scan the entire database. The yarn tech still makes the final choice.

**Confirmed core pain point:** Slow manual filtering (NOT inconsistent picks — this was explicitly confirmed by the user). This matters because the primary value driver is speed/convenience, not necessarily smarter decision-making.

### Existing Data Sources (Databases/Tables — Already Exist, NOT Built From Scratch)
1. **`yarn_details`** — quality, lead time, price, thickness, color, fiber type, etc.
2. **`approval_history`** (previously "approved yarn per article") — historical record of which yarn was approved/rejected for which article. **Confirmed: this table tracks BOTH approved AND rejected outcomes** — meaning real positive AND negative labeled outcomes exist. This was a pivotal fact that shaped the ML approach later in the design (see Approach 5).
3. **`exporter_details`** — information about importers/exporters supplying yarn (e.g., reliability, track record).

### Key Domain Definitions
- **"Article"** = an order/batch requirement (a one-off requirement spec) — NOT a fixed product design or category. Each article has its own requirement values for color, thickness, quality, price, lead time, etc.
- **Attribute alignment confirmed:** The `yarn_details` table and the requirement fields the yarn tech enters use the same/closely aligned attribute names and scales (e.g., same quality grading system, same units). This means no complex feature-mapping/normalization layer is needed between requirements and yarn records.
- **Database engine:** PostgreSQL (Confirmed). Architecture is deliberately engine-agnostic (via SQLAlchemy) so this doesn't block progress (see Section 7.5).

---

## 2. Guiding Philosophy (Applies to Every Decision in This Document)

> **Start with the simplest, cheapest, most explainable approach that could work. Escalate to the next level of complexity ONLY when a specific, named requirement proves the simpler approach insufficient. Never add AI/ML — or any framework/tool — by default just because it's available. Every layer of complexity must be justified by a real, encountered limitation.**

This principle was applied consistently to every architectural decision below, including the later technology-stack choices (e.g., LangGraph was adopted only once a specific requirement — memory management and human-in-the-loop confirmation — could not be reasonably hand-rolled; MCP was rejected because no second consumer of the data was confirmed to exist).

### General Decision Tree (Reusable Framework for "Rules vs ML vs Agent")

```
START
  │
  ▼
Q1: Can a domain expert state the logic fully as explicit if/then rules?
  │
  ├── YES, and it rarely changes → Hardcoded backend rules
  ├── YES, but changes often / situational / business-driven → Configurable Policy/Rules Engine
  └── NO — logic lives in judgment/experience/unstructured input
         │
         ▼
       Q2: Is the difficulty in UNDERSTANDING unstructured input (free text, voice)
           rather than in the decision logic itself?
         ├── YES → AI Agent layer for interpretation ONLY (still calls deterministic logic)
         └── NO — pattern is statistical/historical
                │
                ▼
              Q3: Enough historical data (ideally 1,000s of examples)?
                ├── NO → Stay on rules/heuristics, start logging data for later
                └── YES
                       ▼
                     Q4: Both positive AND negative labeled outcomes available?
                       ├── NO, positive-only → Similarity-based retrieval/recommender
                       └── YES, both classes + sufficient volume
                              ▼
                            Q5: Is cost of a wrong/unexplainable prediction acceptable?
                              ├── NO (compliance/safety/high financial risk) →
                              │      ML only as a SUGGESTION layer, gated by rules/human approval
                              └── YES → Trained ML model (classification/learning-to-rank)
```

---

## 3. The Six Approaches — Full Evolution, Final Adopted Order

**FINAL CONFIRMED ORDERING:** The AI Agent is the LAST approach in the stack (added purely for natural-language UX). The final, correct order is:

1. Rule-Based Hard Filters
2. Weighted Scoring Formula
3. Situational Policy Engine
4. Similarity-Based Recommender
5. Trained Learning-to-Rank Model (**deferred — not built in this MVP**)
6. AI Agent (final, UX-only layer)

### Approach 1: Rule-Based Hard Filters

**What:** Direct filter logic on the yarn database — match color, thickness, quality grade, price ceiling, lead time against the article's stated requirements. Equivalent to a `WHERE` clause / deterministic query.

**Why first:** Logic is fully explicit and stable — the yarn tech can state these rules verbatim. No hidden pattern to learn.

**Can do:** Match yarn attributes exactly; eliminate all yarns failing a hard constraint, instantly, 100% reliably; fully explainable; near-zero cost/latency; solves the entire stated pain point on its own.

**Cannot do:** Cannot decide which of several equally-valid matches is "best"; cannot adapt priority per situation without code changes.

**Trigger to move on:** Need to rank multiple valid matches; priority varies case-by-case (confirmed directly by the user: "it varies," not a fixed priority like "price always wins").

---

### Approach 2: Weighted Scoring Formula

**What:** A scoring formula applied to whatever survives Approach 1's filters. Weights (importance of price vs. quality vs. lead time vs. exporter reliability) are ADJUSTABLE PER REQUEST — set by the yarn tech at request time, not fixed in code.

**Can do:** Ranked shortlist instead of flat list; priority shifts per order without code changes; fully explainable; handles cases where criteria are known/stable but relative importance varies.

**Cannot do:** Cannot enforce a business/sourcing constraint unrelated to the yarn's own technical attributes; cannot be safely edited by non-engineers if hardcoded; no concept of time-bound rules.

**Trigger to move on:** Situational, business-driven sourcing constraints exist — e.g., "company needs to get all materials from ONE importer for reasons like getting a discount, easier tracking — changeable, not fixed, decided outside the yarn's technical attributes, cannot be predicted in advance."

---

### Approach 3: Situational Policy / Constraint Engine

**What:** A separate, data-driven database table (`sourcing_constraints`) holding active business constraints. Read at query time and applied as an additional filter or score-boost — layered ON TOP of Approaches 1 and 2, never mixed into their code.

**Schema:**
```
sourcing_constraints
─────────────────────
id
constraint_type   -- e.g. "prefer_importer", "exclude_importer", "restrict_to_category"
target_value       -- e.g. importer_id
scope              -- "all_orders" / "material_category:cotton" / specific article_id
action             -- "boost" (soft preference) OR "hard_restrict" (must use / must exclude)
weight             -- if action = boost, how strong (e.g. +0.3 to score)
priority           -- tie-breaker if multiple constraints conflict
start_date
end_date           -- enables automatic expiry, no manual cleanup needed
reason             -- free text, for audit ("Q3 discount agreement with Importer X")
set_by             -- who added it, for accountability
active             -- boolean or derived from date range
```

**Integration flow (exact order matters):**
```
1. New article requirement comes in
2. Query sourcing_constraints WHERE active = true AND scope matches this article/category
3. Split results into hard_restrict rules and boost rules
4. Apply Approach 1 (hard technical filters) → candidate list A
5. Apply hard_restrict policy constraints on candidate list A:
   - "must use Importer X" → candidate list A = A ∩ {yarns from Importer X}
   - "must exclude Importer Y" → candidate list A = A − {yarns from Importer Y}
   → candidate list B
6. Apply Approach 2 (weighted scoring) and/or similarity/ML score on candidate list B
   → produces base_score per yarn
7. Apply boost policy constraints on top of base_score:
   final_score = base_score + Σ(weight of any matching active boost constraint)
8. Sort candidate list B by final_score, descending
9. Return ranked shortlist to yarn tech
```

**CRITICAL precedence rule:** Approach 1 (technical hard filters) ALWAYS wins over hard_restrict policy constraints. If "must use Importer X" is active but Importer X's yarn fails a technical filter, the policy constraint does NOT force it through — surface as "no valid yarn found under active sourcing policy — flag for manual review."

**Design decision (final):** A `hard_restrict` failure logs a warning/flag and proceeds rather than blocking the entire request — keeps the system usable while remaining transparent about policy conflicts.

**Cannot do:** Cannot interpret free-text/natural-language requirement input; cannot handle ambiguity or ask clarifying questions.

**Trigger to move on (toward Approach 6 eventually):** Yarn tech should describe requirements in plain language; system should ask clarifying questions. This was intentionally NOT acted on immediately — the next approach pursued, per final agreed ordering, was the Similarity-Based Recommender.

---

### Approach 4: Similarity-Based Recommender (Lightweight ML)

**What it is:** NOT a trained model. A live similarity/retrieval computation — same family as "customers who bought this also bought" recommenders (content-based filtering / case-based reasoning). No training phase, no model file, no gradient descent.

**The problem it solves:** Captures a "historically works well" signal not present in any single explicit field.

**Why ML enters here specifically:** First requirement that genuinely fails Q1 of the decision tree — "what tends to get approved" is a pattern living in historical data, not something anyone can state as an if/then rule.

**How it works:**
1. Represent every article's requirements and every yarn's attributes as feature vectors (thickness, quality_grade, price, lead_time, color — normalized to comparable scale, e.g. 0-1).
2. For a NEW article, compute similarity (cosine similarity or Euclidean distance) against every PAST article that has an approved yarn on record.
3. Pull the approved yarn(s) attached to each of those similar past articles.
4. Aggregate: score each candidate yarn by how often + how strongly it appears across similar past articles:
   ```
   similarity_score(yarn) = Σ similarity(new_article, past_article_i)
                             for every past_article_i where this yarn was approved
   ```
5. Feed that score into Approach 2's weighted scoring formula as one more factor.

**Output format:**
```json
[
  {"yarn_id": 101, "similarity_score": 0.95, "based_on": ["Article A1"]},
  {"yarn_id": 205, "similarity_score": 0.80, "based_on": ["Article A2"]}
]
```

**Can do:** Works correctly with positive-only data (though rejection data also exists now, per Approach 5); no training/retraining cycle; fully explainable; works with MODERATE data volume (hundreds of records — the current confirmed data volume); integrates as one more weighted factor.

**Cannot do:** Cannot detect non-obvious/interaction patterns; has no concept of rejection even though rejection data now exists (structurally can't use it); cold-start problem for novel article types; sensitive to feature weighting/normalization; cannot outperform a properly trained ranking model once real negative/contrastive data is leveraged.

**Trigger to move on:** Data maturity confirmed (both approvals AND rejections logged), sufficient volume, and/or a specific case where similarity-based scoring is demonstrably underperforming.

---

### Approach 5: Trained Learning-to-Rank Model (DEFERRED — Not Built in This MVP)

**What it is:** Genuine trained ML — a model that learns weights/parameters from labeled data via an optimization/training process.

**Why this is justified in principle:** CONFIRMED — the `approval_history` table tracks BOTH approved AND rejected outcomes, providing real negative examples (a classifier cannot be reliably built on positive-only data — absence ≠ rejection).

**Inputs (training):** For each (article, yarn) pair: article features + yarn features + derived/interaction features (thickness delta, over/under budget amount, exporter historical approval/rejection rate) + label (1 = approved, 0 = rejected).

**Inputs (inference):** New article's features + candidate yarn features (only for candidates already surviving Approaches 1 and 3's filtering).

**Model choices (in order of complexity, matched to moderate data volume):**
1. **Logistic Regression** — simplest, explainable, clean probability output. Good starting point.
2. **Gradient Boosted Trees (XGBoost/LightGBM)** — handles non-linear interactions, industry-standard for tabular data at moderate scale.
3. **Learning-to-rank objectives** (LambdaMART, pairwise/Bayesian Personalized Ranking) — trains for correct ORDERING rather than raw probability — most technically correct once enough pairs-per-article exist.

**Confirmed inference pattern:** The model scores EVERY candidate that survived Approaches 1+3's filtering, then ranks by that probability — it never operates on the raw unfiltered database.
```
Article requirement → Approach 1 filters + Approach 3 policy → N valid candidates
   → Trained model scores EACH candidate → sort descending → top-ranked yarn(s) presented
```

**Problems / risks (must be raised proactively):** Class imbalance (approve/reject ratio likely skewed); "rejected" may just mean "never chosen among shown options" rather than "actively declined" — this distinction must be verified before trusting labels; feature leakage (e.g., exporter approval-rate features must be computed point-in-time, not cumulative-to-date); cold start for new yarns/exporters; overfitting risk at moderate data volume; model drift requiring a retraining plan; harder explainability under dispute; still only ranks what Approaches 1+3 already allowed through — NEVER a replacement for hard filters/policy.

**Why this CANNOT stand alone (core architectural point):** ML models APPROXIMATE patterns; rules ENFORCE guarantees. A pure ML model has no concept of a non-negotiable constraint, no way to guarantee compliance, and is blind to cold-start items (brand new yarns with no history). Situational policy changes can't be retroactively known by a model trained on past data. This mirrors the industry-standard recommender-system pattern: **candidate generation (rules) → ranking (ML) → business-rule re-ranking (policy)** — used at every scale, for exactly these reasons.

**Current status: NOT YET BUILT. Deliberately deferred** until (a) rejection labels are confirmed clean/meaningful, (b) data volume grows meaningfully, and (c) there's a specific case where Approach 4 is demonstrably underperforming.

---

### Approach 6: AI Agent (FINAL Layer — UX Only)

**What it is:** An LLM-based agent that parses free-text/voice input into the structured requirement objects Approaches 1-5 already expect, asks clarifying questions when confidence is low, and calls the deterministic backend AS TOOLS — never computing the match/decision itself.

**THE CORE BOUNDARY (most important design principle for this layer):**
> **The agent may decide WHAT to extract from user input, or WHAT to ask about. It should NEVER decide WHAT LOGIC TO RUN, WHAT CODE TO EXECUTE, or WHAT TO PERMANENTLY CHANGE IN THE DATABASE without confirmation.**

**Specific guardrails established:**

1. **Filtering:** Agent does NOT generate/execute raw database queries (too risky — malformed queries, prompt injection, non-determinism). Agent extracts structured parameters and calls a FIXED, pre-written, tested tool — e.g. `get_matching_yarns(color, thickness, quality_min, price_max, lead_time_max)`.

2. **Weighted scoring / priority weights — FINAL AGREED LOGIC:**
   ```
   1. Agent parses initial request for stated priority signals
      (e.g., "need it fast" → lead_time weighted higher)
   2. IF explicit priority stated → use those values directly
      → (optional) confirm back: "Prioritizing lead time and price. Sound right?"
   3. IF no priority stated → ASK the user: "Any priority among price, quality,
      lead time, and exporter reliability — or should I weight them equally?"
   4. IF user responds with specific values → use those values
   5. IF user doesn't respond meaningfully / says "just default"/"you decide"
      → fall back to EQUAL WEIGHTING (documented default)
      → state clearly that a default was used
   ```
   **Explicitly rejected alternative:** "Agent decides weights based on its own judgment" — unsafe, produces non-deterministic, unauditable results. The agent must NEVER silently invent a judgment call.

3. **Situational policy — split READ vs WRITE:**
   - **Reading** ("what's our current sourcing policy") → ALWAYS via tool call to the deterministic policy table (`get_active_policies(scope)`), never "recalled" from conversation.
   - **Writing** ("prefer Importer X for cotton this quarter") → agent parses into a structured constraint object, but REQUIRES explicit user confirmation before committing to the database (this is a real business action).

4. **Similarity recommendation** — agent calls it as a tool (always a read), no special guardrail beyond the general read/write distinction.

**Full integration flow (current architecture):**
```
Yarn Tech (natural language input via chat)
        ↓
AI Agent — Intent/Requirement Parser
   → extracts structured requirements + priority weights (per logic above)
   → asks clarifying questions if ambiguous
        ↓
Agent calls backend functions AS TOOLS (direct function calls, NO MCP):
   - get_matching_yarns(filters)                         [Approach 1]
   - score_yarns(candidates, weights)                     [Approach 2]
   - get_active_policies(scope) / add_sourcing_constraint(...)  [Approach 3]
   - get_similarity_recommendations(article)               [Approach 4]
   - (get_ml_ranking — future, NOT currently built)        [Approach 5]
        ↓
Deterministic backend executes actual logic, returns structured results
        ↓
Agent — Response Composer
   → turns structured results into natural-language explanation
        ↓
Yarn Tech reviews, can refine → agent re-calls tool(s) → loop
        ↓
Final selection logged → feeds future similarity recommender + future ML training data
```

**Can do:** Converts loose human language into structured filters/weights; asks follow-up questions; explains results in plain language; handles iterative refinement; lowers training burden for new/non-technical staff.

**Cannot / should NOT do:** Cannot be trusted to compute the match/ranking itself (hallucination risk); cannot learn from historical patterns itself (that's Approaches 4/5's job); adds real cost/complexity (LLM calls, latency, prompt engineering); does NOT improve match accuracy — only improves how requirements get captured.

**Why positioned LAST:** Explicitly corrected during design discussion — the agent is the FINAL, lowest-necessity, UX-only layer, not "the smart part." It should only be built once structured input is a PROVEN, real friction point.

---

## 4. Full Layered Architecture (Runtime Flow, Top-Down)

```
┌─────────────────────────────────────────────────────────────┐
│  Yarn Tech Input (natural language OR structured form)       │
└───────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 6 — AI Agent (interpretation only, FINAL/optional)     │
│  Parses free text → structured requirement object              │
│  Asks clarifying questions on ambiguity                        │
│  Calls Layers 1-5 as DIRECT TOOLS (no MCP) — never computes    │
│  results itself. Built on LangGraph (see Section 7.3).          │
└───────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 5 — Trained Learning-to-Rank Model (DEFERRED, future)  │
│  Uses real approve/reject labeled data                         │
│  Scores every candidate that survived Layers 1+3                │
└───────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 4 — Similarity-Based Recommender (lightweight ML)       │
│  Positive-history-based vector similarity, live computation     │
└───────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3 — Situational Policy / Constraint Engine               │
│  Data-driven, time-bound business rules                         │
│  hard_restrict applied BEFORE scoring; boost applied AFTER       │
└───────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2 — Weighted Scoring Formula                              │
│  Price fit + Lead time fit + Quality fit + Exporter reliability │
│  Weights adjustable per request (agent-mediated per Approach 6) │
└───────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1 — Hard Filters (deterministic backend rules)            │
│  Color / thickness / quality / price / lead time must-match     │
│  ALWAYS the final gate — nothing bypasses this layer, including │
│  policy hard_restrict and any ML/agent output                    │
└───────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  Ranked Shortlist Output → Yarn Tech reviews & approves          │
│  → Decision logged → feeds back into Layer 4/5's training data  │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Three-Tier Code Architecture — Where Logic Actually Lives

This clarification resolved a specific point of confusion: **where do database read/write functions live — in the "backend" or in the "agent tools"?** Answer: database access ALWAYS lives in the backend. Agent "tools" are never a separate implementation — just a thin schema/wrapper around backend functions.

```
Tier 3 — Agent Tool Layer (Module 4)
   Thin wrapper/schema so the LLM can call Tier 2 functions.
   Does NOT touch the database directly. Does NOT contain business logic.
        ↓ calls
Tier 2 — Business Logic Layer (Module 3)
   The actual decision-making: filtering, scoring, policy rules, similarity.
   Uses Tier 1 functions to get/save data. Contains all the "smart" logic.
        ↓ calls
Tier 1 — Data Access Layer (Module 2)
   Raw CRUD functions that talk directly to the SQL database.
   No business logic here — just "get this row," "insert this row."
```

**Example:**
```python
# Tier 1 (Module 2 — Data Access)
def db_select_yarns(where_clause):
    return cursor.execute(f"SELECT * FROM yarn_details WHERE {where_clause}")

def db_insert_policy(row_data):
    return cursor.execute("INSERT INTO sourcing_constraints ...", row_data)

# Tier 2 (Module 3 — Backend Business Logic)
def get_matching_yarns(color, thickness, quality_min, price_max, lead_time_max):
    where_clause = build_filter_conditions(color, thickness, quality_min, price_max, lead_time_max)
    return db_select_yarns(where_clause)   # calls Tier 1

def add_sourcing_constraint(constraint_data):
    validate_constraint(constraint_data)
    return db_insert_policy(constraint_data)  # calls Tier 1

# Tier 3 (Module 4 — Agent Tool Wrapper) — NOT new logic, just a schema/description
agent_tool_schema = {
    "name": "get_matching_yarns",
    "description": "Find yarns matching color, thickness, quality, price, lead time",
    "parameters": {"color": str, "thickness": float, "quality_min": str, "price_max": float, "lead_time_max": int}
}
# When the LLM calls this tool, it invokes the Tier 2 function directly.
```

**Why this separation matters:** If DB logic were embedded inside "agent tools" directly, business logic would end up duplicated/scattered depending on which interface calls it — bad for testing and maintenance. It also protects the core guarantee: the agent never touches data directly, it only ever routes to code that already exists and is already trusted.

---

## 6. Data Layer Details

**Existing tables (already exist, NOT built from scratch):** `yarn_details`, `approval_history` (tracks both approved AND rejected outcomes), `exporter_details`.

**New table needed (does not exist yet):** `sourcing_constraints` — the situational policy table (full schema in Section 3, Approach 3).

**Data layer tasks (confirmed final scope):**
- Existing schema review & data mapping (map existing tables → feature vectors needed for filtering/scoring/similarity/ML)
- Database connection setup & pooling (connect to EXISTING instance — do not provision new DB)
- New table schema design for `sourcing_constraints` only
- Migration script to create `sourcing_constraints` table only (NOT the whole schema)
- ORM/query layer setup mapping BOTH existing tables and the new table
- Sample/test data needed ONLY for the new policy table (existing tables already have real production data)
- CRUD utility functions: read existing tables, read/write policy table
- Data validation & constraints — applies mainly to the new policy table

**Database engine:** PostgreSQL (Confirmed). Architecture uses SQLAlchemy specifically to make this a low-risk open item — switching engines later mainly changes a connection string and driver, not query logic.

---

## 7. Full Technology Stack

### 7.1 Summary Table

| Layer | Technology | Why |
|---|---|---|
| Backend framework | **Python — FastAPI** | Async-native, built-in request validation, ideal for AI agent workloads (Section 7.2) |
| Agent orchestration | **LangGraph** | State-graph framework purpose-built for tool-calling loops, human-in-the-loop confirmation, and short/long-term memory (Section 7.3) |
| Agent observability | **LangSmith** | Native tracing/debugging companion for LangGraph — full visibility into every reasoning/tool-call step |
| LLM provider (Phase 1 — Dev/Prototype) | **Google Gemini API (free tier)** | Genuinely free tier with function-calling support, no trial-credit expiry pressure |
| LLM provider (Phase 2 — Production) | **OpenAI GPT (paid)**, fallback **Anthropic Claude** | Matches existing paid subscription; both have mature function-calling support |
| Database | **PostgreSQL** | Existing company database; confirmed as PostgreSQL |
| ORM / query layer | **SQLAlchemy** | Works identically across PostgreSQL and MySQL — removes risk from DB-engine uncertainty |
| Frontend (Chat UI) | **React** | Component-based, huge ecosystem for chat-style UIs, easy to iterate on |
| API communication | **REST (JSON over HTTP)** | Simple, sufficient for MVP request/response pattern |
| Testing | **Pytest** (backend), **React Testing Library** (frontend) | Standard, integrates cleanly with FastAPI |
| Environment management | **venv + pip** (or Poetry) | Standard Python practice, reproducible environment |
| Version control | **Git** | Standard |

### 7.2 Why FastAPI Over Flask

| Concern | Flask | FastAPI | Why it matters here |
|---|---|---|---|
| Async support | Bolted on | Native (`async`/`await`) | LLM calls are slow (seconds) — async lets backend handle other requests while waiting |
| Request/response validation | Manual | Built-in (Pydantic) | Structured tool parameters (filters, weights, policy objects) validated before reaching business logic |
| Auto-generated API docs | Not built-in | Built-in (Swagger/OpenAPI) | Useful for testing tool endpoints directly during development |
| Streaming responses | Clunky | Native | Useful for showing agent "typing"/streaming tool-call progress later |
| Performance | Good | Better (ASGI/Starlette) | Matters more given multiple sequential LLM + tool round-trips per request |

**Decision: FastAPI.** The core workload (agent reasoning → tool call → wait for DB → maybe another tool call → compose response) is naturally asynchronous.

### 7.3 Agent Orchestration — Why LangGraph (Not Raw SDK Calls, Not Full LangChain)

Given the explicit requirement for **industry-level maintainability, scalability, and real memory management**, agent orchestration is built on **LangGraph** — a narrower, lower-level framework than full LangChain, focused specifically on structuring an agent as an explicit state graph.

| Requirement | LangGraph Feature |
|---|---|
| Tool-calling loop (LLM ↔ Tools until done) | Core primitive — nodes for LLM calls and tool calls, conditional edges to loop or exit |
| Weight-clarification flow | Naturally expressed as a conditional edge |
| Policy write confirmation (pause, wait for approval, resume) | Built-in **human-in-the-loop interrupt pattern** |
| Short-term memory (current conversation) | Built-in **checkpointing** — persists conversation state per thread |
| Long-term memory (cross-session) | Built-in **cross-thread store** |
| Scalability (multiple concurrent yarn techs) | Checkpointer backed by Postgres/Redis — production-grade persistence out of the box |
| Maintainability | Explicit, visualizable graph — new engineers see the whole flow structure |

**Why this earns its cost (vs. the earlier "skip frameworks" default):** A minimal tool-calling loop without memory is simple enough to hand-roll. But reliable checkpointing, interrupt/resume for policy-write confirmation, and cross-session memory are exactly the kind of infrastructure that's expensive and error-prone to build and maintain from scratch — LangGraph provides all three as first-class, tested features.

**Deciding factor — LangSmith support:** LangGraph integrates natively with **LangSmith**. Because this agent makes multi-step decisions (parse intent → call tool → maybe call another tool → compose response), full tracing of exactly what the agent reasoned and called at each step is critical for debugging and trust — especially once policy writes and multi-turn refinement are involved. Building equivalent observability by hand would be a non-trivial ongoing cost; LangGraph provides it by adopting the ecosystem.

**Why full LangChain is still NOT used:** The heavier LangChain abstractions (chains, prompt template managers, its own multi-provider wrappers) are intentionally avoided — added complexity without solving a project-specific problem, and a track record of breaking changes between versions. LangGraph is adopted narrowly, for orchestration/memory/interrupts only.

```
LangGraph State Graph
   ├─ Node: parse_intent
   ├─ Node: call_llm  ──┐
   ├─ Node: call_tool   │  (conditional edge loops between these until done)
   ├─ Node: check_needs_confirmation → [INTERRUPT if policy write] → wait for human → resume
   ├─ Node: compose_response
   ├─ Checkpointer (Postgres-backed) → short-term / thread-scoped memory
   └─ Store (Postgres-backed) → long-term / cross-session memory
        │
        ▼ (each LLM-calling node internally uses)
  LLM Provider Interface (call_llm, format_tools, parse_response)
        │
   ┌────┴────┬─────────────┐
   ▼         ▼             ▼
 Gemini    OpenAI        Claude
 (Phase 1) (Phase 2)   (fallback)
```

### 7.4 LLM Provider Strategy — Phased Approach

**Phase 1 (Development/Prototype): Google Gemini API, free tier.** Reasoning: OpenAI has no genuinely ongoing free API tier (only expiring trial credits), risky for active development with many test calls. Gemini's free tier is generous and supports function-calling.

**Phase 2 (Production): OpenAI GPT (paid), preferred since the user already has a paid subscription — with Anthropic Claude as fallback.**

**Critical design decision supporting this switch cheaply:** A thin LLM-provider abstraction (`call_llm(messages, tools)`) isolates provider-specific SDK code, so switching Gemini → OpenAI → Claude is a change in one file, not a rewrite of agent logic. This abstraction sits BELOW LangGraph — LangGraph orchestrates the flow between nodes; individual nodes call this provider interface internally.

### 7.5 Database — Open Item

Exact engine (PostgreSQL vs. MySQL) not yet confirmed — verify with whoever manages the existing database before Module 2 begins. SQLAlchemy keeps this low-risk: switching engines later mainly means changing a connection string and driver (`psycopg2` vs `mysqlclient`/`pymysql`), not query logic.

### 7.6 Frontend — React, Deliberately Simple for MVP

Needs: message list, input box, structured result display (yarn cards/tables in chat), loading/error states. React chosen over heavier alternatives (Next.js, full Vue framework) because there's no SSR/SEO need (internal tool), component reusability is still valuable, and the ecosystem reduces custom code for basic chat patterns.

### 7.7 Alternatives Considered and Rejected

| Alternative | Rejected Because |
|---|---|
| Django (backend) | Heavier, more opinionated, built for traditional CRUD/admin apps — overkill for an API-first agent backend |
| Node.js/Express (backend) | Python was the confirmed preference; also stronger AI/ML ecosystem if similarity/ML layers extend later |
| Raw SQL (no ORM) | Ties codebase to one DB engine's syntax — risky given engine isn't confirmed yet |
| GraphQL (API layer) | Adds complexity with no clear benefit for this MVP's simple request/response pattern |
| Committing to one LLM provider permanently | Locks in cost/risk if pricing, rate limits, or capabilities change |
| Raw hand-rolled tool-calling loop (no framework) | Would require building checkpointing, interrupt/resume, and cross-session memory from scratch — reasonable for a trivial agent, not one requiring real memory management and human-in-the-loop confirmation |
| Full LangChain (chains, prompt template managers, provider wrappers) | Broader than needed, added abstraction and breaking-change risk without solving a project-specific problem; LangGraph alone covers the actual requirement |
| MCP (Model Context Protocol) server for tool access | See Section 8 — rejected for this MVP, no confirmed second consumer of the data |

---

## 8. MCP Decision — Full Reasoning (Rejected for This MVP)

**What MCP is:** A standardized protocol for exposing tools/data sources to AI agents via a separate server, so any MCP-compatible agent/client can discover and call them.

**When MCP would be justified:** If multiple agents/tools (a separate reporting agent, a future Slack bot, org-wide standardization) need to access the same yarn data.

**When MCP is unnecessary overhead:** If this agent is the only consumer of this database — MCP adds a separate protocol server, discovery/schema layer, and hosting/running overhead to expose tools that direct function calls already do more simply.

**Status at time of discussion:** User was "not yet sure" if other agents/tools will need this data in future, but expressed interest in MCP for future-proofing. A full effort estimation WAS built for the MCP-inclusive version (added ~19.8-23 hours: MCP server framework setup, MCP tool implementation, MCP client integration, basic auth/access control, tool discovery/invocation testing).

**FINAL DECISION: Build the AI agent WITHOUT MCP — using only direct tool/function calls.** If multiple consumers become a confirmed real need in the future, MCP can be introduced later as a refactor of this tool layer — not built preemptively now.

---

## 9. Tool Contract Table (Final — No `get_ml_ranking`, Since That Tool Doesn't Exist Yet)

| Tool | Purpose | Type |
|---|---|---|
| `get_matching_yarns(color, thickness, quality_min, price_max, lead_time_max)` | Approach 1 — hard filter query | Read |
| `score_yarns(candidate_list, weights)` | Approach 2 — weighted scoring | Read/compute |
| `get_active_policies(scope)` | Approach 3 — read active sourcing constraints | Read |
| `add_sourcing_constraint(constraint_type, target_value, scope, action, weight, start_date, end_date, reason)` | Approach 3 — create new policy (REQUIRES user confirmation before commit) | Write |
| `get_similarity_recommendations(article_features)` | Approach 4 — similarity-based scoring | Read/compute |

**Note:** `get_ml_ranking(...)` is intentionally excluded from the current tool set — Approach 5 (trained model) is deferred and not yet built. This tool should only be added once Approach 5 is actually implemented.

---

## 10. Final MVP Work Breakdown Structure (WBS)

**Scope:** Chat interface + AI Agent backend (LangGraph orchestration, direct tool calls, NO MCP) + Existing SQL database (extended with one new table) + Approaches 1-4 (Approach 5/trained ML explicitly DEFERRED/out of scope).

**Estimation method:** PERT 3-point estimation — Expected = (Optimistic + 4×Most Likely + Pessimistic) / 6.

### Module 1: Project Setup & Planning
- Requirements finalization / sign-off — Low
- Tech stack selection (LLM provider, agent framework, frontend framework, database engine) — Low
- Repo, environment, project scaffolding — Low

### Module 2: Data Layer (Existing SQL Database)
- Existing schema review & data mapping (yarn_details, approval_history, exporter_details → feature vectors) — Medium
- Database connection setup & pooling (connect to existing instance) — Low
- New table schema design — sourcing_constraints (policy table only) — Low
- Migration script — create sourcing_constraints table only — Low
- ORM / query layer setup (models mapped to existing + new tables) — Medium
- Sample/test data for new policy table only — Low
- CRUD utility functions (read existing tables, read/write policy table) — Medium
- Data validation & constraints (new policy table only) — Low

### Module 3: Core Backend Logic
- Hard filter function — SQL query construction & execution (Approach 1) — Medium
- Weighted scoring function (Approach 2) — Medium
- Situational policy engine — read active constraints via SQL (Approach 3) — Medium
- Situational policy engine — write/validate new constraints (INSERT + transaction handling) — Medium
- Precedence/conflict resolution logic (filters vs policy vs scoring order) — High
- Similarity-based recommender (vectorization + similarity calc + aggregation) — High

### Module 4: AI Agent Layer (LangGraph-Based)
- LangGraph state graph setup (nodes, edges, conditional routing) — High
- Agent framework / LLM provider integration (Gemini free tier, provider abstraction layer) — High
- Tool definitions/schemas (all backend functions exposed as tools — direct function calls, no MCP) — Medium
- Intent parsing (free text → structured filter parameters) — High
- Weight-clarification conversational flow (ask, use stated, default fallback) — Medium
- Policy write confirmation flow (LangGraph human-in-the-loop interrupt pattern) — Medium
- Response composition (structured results → natural language explanation) — Medium
- Checkpointing setup (short-term/thread-scoped memory) — Medium
- Cross-thread store setup (long-term memory) — Medium
- LangSmith tracing integration — Low

### Module 5: Chat Interface (Frontend)
- Basic chat UI (message list, input box, layout) — Medium
- Connect frontend to agent backend (API integration) — Low
- Display structured results (yarn cards/tables in chat) — Medium
- Loading states, error handling in UI — Low

### Module 6: Integration & End-to-End Flow
- Wire full round trip (chat → agent → tools → SQL DB → response) — Medium
- Edge case handling (no matches, policy conflicts, ambiguous input) — High

### Module 7: Testing
- Unit tests — filter logic — Low
- Unit tests — scoring & policy logic — Medium
- Database integration tests (query correctness, transaction handling) — Medium
- Agent behavior testing (varied phrasings → correct tool calls) — High
- LangGraph flow testing (interrupt/resume, memory persistence) — High
- End-to-end manual test scenarios (realistic yarn tech requests) — Medium
- Bug-fixing pass — High

### Module 8: Documentation & Handover
- Setup/run instructions (including DB setup steps) — Low
- Architecture doc (brief) — Low
- Known limitations / MVP scope boundaries doc — Low

**Explicitly OUT OF SCOPE for this MVP:** Trained ML model (Approach 5), MCP server, authentication (beyond basic access control), multi-user support, production deployment/DevOps, cloud DB hosting setup.

**Note:** This WBS supersedes earlier versions in this project's history — LangGraph-specific tasks (state graph setup, checkpointing, cross-thread store, LangSmith integration) were added to Module 4 after the memory-management and maintainability requirement was introduced; MCP-related tasks were removed after the final "no MCP" decision.

---

## 11. Diagrams Already Created (Reference for Consistency)

The following diagrams have been generated in this project (as inline visuals and/or downloadable SVG/HTML files) and should be treated as the canonical visual reference — reuse the same terminology, box names, and colors if regenerating or extending them:

1. **Container Diagram** — Yarn tech → Chat interface → AI agent backend → Existing SQL database, with LLM provider as an external dependency of the agent backend.
2. **Decision Flow Diagram** — Vertical stack of the 6 approaches (Hard filters → Weighted scoring → Policy engine → Similarity recommender → Trained ranking model [deferred, gray] → AI agent [interface-only, coral]), each with a short subtitle naming the trigger that caused escalation, plus a color legend.
3. **Tool Contract Table** — Styled HTML/SVG table listing each tool's function signature, purpose, and Read/Write type (matches Section 9 above).
4. **Tool-Calling Loop Diagram (DAG)** — User input → Chat UI → Backend → AI agent (dashed container) containing an LLM box and a Tools box (listing all 5 named tools) connected by a bidirectional loop ("call tool" / "tool result"), with a loop annotation ("↻ loops until no more tools needed"), exiting to a final "Selected yarn(s)" output box.

**Diagrams not yet created (identified as still needed):** Sequence Diagram (step-by-step time-ordered request flow, including the LangGraph interrupt/resume pattern for policy writes), Layered Architecture Diagram (the stacked 6-layer view in Section 4 above, as a standalone visual), Entity-Relationship Diagram (yarn_details, approval_history, exporter_details, sourcing_constraints with relationships — likely best built in Mermaid.js rather than raw SVG, since Mermaid handles ER layout automatically).

---

## 12. Key Design Principles Summary (Quick Reference)

1. **Escalate complexity only when a named requirement forces it** — never by default. Applies to approach selection (rules → ML → agent) AND technology selection (LangGraph adopted only once memory/confirmation requirements existed; MCP rejected due to no confirmed second consumer).
2. **Hard filters are the non-negotiable final gate** — nothing (policy, similarity score, ML score, or agent output) can bypass Approach 1's technical validity check.
3. **The agent interprets; it never decides.** It may extract parameters or ask questions; it may never invent logic, execute arbitrary code, or write to the database without explicit confirmation.
4. **Read operations run freely; write operations require confirmation.** Reading yarn matches, active policies, or similarity scores needs no gate. Adding a new sourcing constraint always requires the yarn tech's explicit confirmation before committing.
5. **Data access lives only in the backend (Tiers 1-2).** Agent "tools" (Tier 3) are thin schemas/wrappers around backend functions — never a separate implementation of business or data logic.
6. **Every default/fallback the agent uses must be transparent and stated aloud** (e.g., "using equal weighting since no priority was given") — never a silent, unexplainable judgment call.
7. **Technology choices favor flexibility where change is likely (LLM provider, via the abstraction layer) and stability/reliability where correctness matters most (database access via SQLAlchemy, business logic in Python/FastAPI).**

---

## 13. Talking Points / Narrative for Senior Presentation

**Opening framing:** "We started from the simplest possible approach and escalated only when a specific, real requirement proved the simpler approach insufficient — not by defaulting to more advanced technology, in either the decision logic or the tech stack."

**Per-approach one-liners:**
- Approach 1 (Filters): "A yarn tech can state this logic out loud — there's nothing to learn, only to look up."
- Approach 2 (Weighted Scoring): "Still not AI/ML — priority varies per order, so we let the human state it each time instead of guessing."
- Approach 3 (Policy Engine): "Business rules are volatile and non-technical — this gives management control without needing a developer for every change."
- Approach 4 (Similarity Recommender): "The first genuine pattern-learning step — but lightweight, no training, fully explainable."
- Approach 5 (Trained ML): "The biggest complexity jump in the whole stack — deliberately deferred until data volume and label quality justify it."
- Approach 6 (AI Agent): "The last layer, added purely for conversational convenience — it never makes decisions, it only interprets input and explains output."

**Tech stack framing:** "Same philosophy applied to tooling — FastAPI because the workload is genuinely async and I/O-heavy, LangGraph specifically because we need real memory and human-in-the-loop confirmation (not because frameworks are impressive), and no MCP because we don't yet have a second consumer of this data to justify that overhead."

**Closing line (designed to be quotable):** *"Every layer of complexity — in the decision logic and in the technology choices — was added because a real requirement forced it, not because a more advanced option was available."*

**Core defensive principle if challenged on "why not just use AI for everything":** ML models approximate patterns; rules enforce guarantees. For a purchasing decision involving real money and delivery deadlines, guarantees matter more than probabilistic convenience — which is why hard filters remain the mandatory final gate even in the most AI-enabled version of this system.
