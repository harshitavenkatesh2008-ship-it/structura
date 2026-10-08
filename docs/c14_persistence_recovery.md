# Component C14: Supabase Persistence & Failure Recovery

## Overview

Component C14 introduces resilient persistence and failure recovery for Structura backend jobs, document metadata, and canonical Document Graph outputs. It enables backend state to survive process restarts, node crashes, and network interruptions while maintaining strict compatibility with existing C8–C10 API envelopes and state machines.

---

## Architecture & Deliverables

1. **Supabase Client Wrapper (`backend/app/services/supabase_client.py`):**
   - High-level async interface communicating with Supabase PostgREST tables and Storage API via `httpx`.
   - **Secret Masking:** API keys are encapsulated in Pydantic `SecretStr` and masked (`key='***'`) in representations and logs.
   - **Error Handling:** Translates network and HTTP errors into controlled exceptions (`SupabaseConnectionError`, `SupabaseApiError`).

2. **Supabase Job Repository (`backend/app/repositories/supabase_job_repository.py`):**
   - Direct drop-in implementation of the abstract `JobRepository` interface.
   - Idempotently creates, reads, updates, and atomically modifies jobs in the Supabase `jobs` table.
   - Enforces unique constraint violation handling via `DuplicateJobError`.

3. **Document & Graph Persistence Service (`backend/app/services/persistence_service.py`):**
   - Persists ingested document metadata (`documents` table).
   - Stores and retrieves canonical Document Graph JSON outputs (`documents` storage bucket).
   - Records processing outcomes, failure diagnostics, and partial success details (`job_outcomes` table).

4. **Failure & Interrupted Job Recovery Service (`backend/app/services/recovery_service.py`):**
   - Automatically executed upon FastAPI startup.
   - Inspects active jobs (`queued`, `running`, `escalating`, `retry_wait`) and identifies orphaned jobs interrupted by a crash or restart.
   - Idempotently transitions interrupted jobs to `failed` (or `retry_wait`), recording structured timeout and diagnostic information without corrupting valid runs.

5. **Safe Local Fallback Mode:**
   - In offline test environments or when `SUPABASE_URL` / `SUPABASE_KEY` are not set, all persistence seamlessly falls back to in-memory and local filesystem stores.
   - Developers and CI test runners do not need live Supabase credentials to run tests.

---

## Configuration Reference

Add the following environment variables (or `.env` file entries):

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `SUPABASE_URL` | `string` | `None` | Supabase project URL (e.g., `https://xyz.supabase.co`). |
| `SUPABASE_KEY` | `string` (Secret) | `None` | Supabase anon or service role API key. |
| `SUPABASE_SERVICE_ROLE_KEY` | `string` (Secret) | `None` | Supabase service role key (preferred for backend persistence). |
| `SUPABASE_BUCKET` | `string` | `"documents"` | Supabase Storage bucket for Document Graph outputs. |
| `PERSISTENCE_BACKEND` | `string` | `"auto"` | Set to `"supabase"`, `"memory"`, or `"auto"` (uses Supabase if configured). |
| `JOB_RECOVERY_ENABLED` | `boolean` | `true` | Enables startup inspection and recovery of stale/interrupted jobs. |
| `JOB_STALE_TIMEOUT_SECONDS` | `integer` | `3600` | Inactivity threshold before an active job is marked as interrupted. |

---

## Database Schema (PostgreSQL / Supabase DDL)

Execute the following SQL migration in your Supabase SQL editor:

```sql
-- 1. Documents Metadata Table
CREATE TABLE IF NOT EXISTS public.documents (
    document_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    format TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    storage_key TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Jobs Table
CREATE TABLE IF NOT EXISTS public.jobs (
    job_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES public.documents(document_id) ON DELETE CASCADE,
    state TEXT NOT NULL CHECK (state IN ('queued', 'running', 'retry_wait', 'escalating', 'completed', 'failed', 'cancelled')),
    stage TEXT,
    progress JSONB,
    parent_job_id TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_state ON public.jobs(state);
CREATE INDEX IF NOT EXISTS idx_jobs_document_id ON public.jobs(document_id);

-- 3. Document Graphs Table
CREATE TABLE IF NOT EXISTS public.document_graphs (
    document_id TEXT PRIMARY KEY REFERENCES public.documents(document_id) ON DELETE CASCADE,
    job_id TEXT,
    storage_key TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Job Outcomes / Error Diagnostics Table
CREATE TABLE IF NOT EXISTS public.job_outcomes (
    job_id TEXT PRIMARY KEY REFERENCES public.jobs(job_id) ON DELETE CASCADE,
    document_id TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT,
    partial_results JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Storage Bucket (Create via Dashboard or Storage API)
-- Bucket name: 'documents'
```

---

## Testing & Offline Verification

Run all C14 persistence tests offline:

```bash
pytest tests/test_supabase_persistence.py -v
```

Run the entire backend test suite:

```bash
pytest -v
```
