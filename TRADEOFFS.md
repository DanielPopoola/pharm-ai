# PharmAI — Key Design Tradeoffs

A record of the non-obvious decisions made during development, why each option
was chosen, and what was given up. Intended as the foundation for the technical
writeup (PHARMAI-033).

---

## 1. Crash-Resistant Ingestion Pipeline

### The problem
The ingestion pipeline talks to three external services in sequence: OpenFDA,
Gemini, and Postgres. Each can fail independently. The naive design treats the
whole pipeline as one transaction — a Gemini failure after a successful OpenFDA
fetch loses all fetched data and forces a full restart.

### My solution
Write one file per therapeutic class after each stage. A class is the natural
unit of work for OpenFDA pagination. On failure, the next run skips already
checkpointed classes and resumes from the failed one. Simpler file management,
acceptable retry granularity given the token budget math.

This was chosen over checkpointing per-drug because each label contains at least 50+ drugs meaning there'd be a lot of files to track. The tradeoff is that precision for recovery as each
checkpoint per-drug is more precise than checkpointing a whole class. If the pipeline fails, you can recover to the latest class rather than to the last drug

### Checkpoint lifecycle
Checkpoints persist until the full pipeline completes successfully, then are
wiped. This gives crash-resume within a run while guaranteeing fresh data on
the next daily run. A failed partial run leaves checkpoints intact so the next
manual retry or scheduled run resumes exactly where it left off.

---

## 2. Hybrid Retrieval with Reciprocal Rank Fusion

### The problem
_[Your summary of why neither pure semantic nor pure lexical search is sufficient
for a drug reference tool]_

### Options considered

**Option A — Pure semantic search (pgvector cosine similarity)**
_[Your talking point]_

**Option B — Pure lexical search (Postgres full-text search)**
_[Your talking point]_

**Option C — Hybrid with RRF (chosen)**
_[Your talking point]_

### What was chosen and why
_[Your reasoning]_

### What was given up
_[Your answer — what RRF doesn't solve, what weighted fusion would give you]_

---

## 3. pgvector over a Dedicated Vector Database

### The problem
_[Your summary of the decision — why not Pinecone, Qdrant, Weaviate]_

### Options considered

**Option A — Dedicated vector database (Pinecone / Qdrant)**
_[Your talking point]_

**Option B — pgvector in Postgres (chosen)**
_[Your talking point]_

### What was chosen and why
_[Your reasoning — operational simplicity, hybrid retrieval in one DB, Alembic]_

### What was given up
_[Your answer — what dedicated vector DBs give you that pgvector doesn't]_

---

## 4. Fixed Sequential Tool Calling over Open-Ended Agent Planning

### The problem
_[Your summary — why a clinical tool needs deterministic behaviour]_

### Options considered

**Option A — Open-ended agent (LLM decides what tools to call)**
_[Your talking point]_

**Option B — Fixed sequential chain (chosen)**
lookup → find_similar → check_contraindications, always in that order

_[Your talking point]_

### What was chosen and why
_[Your reasoning — auditability, clinical safety, no tool skipping]_

### What was given up
_[Your answer — flexibility, handling edge cases where the fixed order is suboptimal]_

---

## 5. PydanticAI over LangChain

### The problem
_[Your summary of the choice]_

### Options considered

**Option A — LangChain**
_[Your talking point]_

**Option B — PydanticAI (chosen)**
_[Your talking point]_

### What was chosen and why
_[Your reasoning — typed outputs, simpler mental model, less magic]_

### What was given up
_[Your answer — ecosystem, tooling, community resources]_

---

## 6. Seed + Cache-Miss over Full Ingestion

### The problem
_[Your summary — why not ingest all of OpenFDA upfront]_

### Options considered

**Option A — Full ingestion (all of OpenFDA on first run)**
_[Your talking point]_

**Option B — Seed only (fixed therapeutic classes)**
_[Your talking point]_

**Option C — Seed + cache-miss on demand (chosen)**
_[Your talking point]_

### What was chosen and why
_[Your reasoning — covers 80% of queries, no cold-start problem, cache-miss
handles the long tail without wasting quota on noise]_

### What was given up
_[Your answer — first-query latency for uncached drugs, complexity of the
degraded response path]_

---

## 7. Evaluation as a First-Class Component

### The problem
_[Your summary — why bolting on evaluation after the fact is a liability for a
clinical tool]_

### What was built
- Retrieval evaluation: precision@k and recall@k against a golden dataset
- Generation evaluation: LLM-as-judge scoring contraindication accuracy,
  alternative quality, and hallucination

### What was given up
_[Your answer — time, complexity, what you would do differently with a larger
golden dataset or human clinical reviewers]_
