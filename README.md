# IntakeFlow

AI-assisted maintenance intake, with staff in control. A tenant report becomes an evidence-linked draft, a clarification conversation, and exactly one staff-approved internal work order.

Built with React 19 (JavaScript/Vite), React Router, TanStack Query, React Hook Form, Bootstrap 5, FastAPI, SQLAlchemy 2, PostgreSQL 17, Celery/Beat, Redis, LangChain and LangGraph. Direct dependencies and transitive lockfiles are pinned. No paid key is needed for the **explicitly labeled offline demo**.

## Start the Docker demo

Prerequisites: Docker Desktop/Engine with Compose v2. For host development: Python 3.12, uv 0.12.10, Node 24.14 and npm 11.

From this directory (PowerShell; on macOS/Linux use `cp` instead of `Copy-Item`):

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
docker compose up -d db redis
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m app.cli checkpoints
docker compose run --rm backend python -m app.cli seed
docker compose up -d --build
docker compose ps
```

Open **http://localhost:5173**. OpenAPI: **http://localhost:8000/docs**. Allow a few seconds for Beat to discover new jobs. Data lives in named PostgreSQL/Redis volumes. `docker compose down` stops the demo while preserving data. Migrations and checkpoint setup are explicit commands; API startup does not create or recreate tables.

Demo password for every account: `IntakeFlow-demo-2026!`

| Organization | Admin | Staff | Tenant |
| --- | --- | --- | --- |
| Cedar Property Group | admin@demo.intakeflow.app | staff@demo.intakeflow.app | tenant@demo.intakeflow.app |
| Harbour Estates | admin2@demo.intakeflow.app | staff2@demo.intakeflow.app | tenant2@demo.intakeflow.app |

The seed command is idempotent and refuses production mode. Every organization has a property, three units, one assigned tenant and three example requests. New organization registration creates its first ADMIN; use administration pages to add a property, unit, account and tenant assignment.

## Host development

Start PostgreSQL/Redis using `docker compose up -d db redis`, or provide existing instances using `backend/.env`. The backend uses a synchronous session per HTTP request or job. Run these from `backend/`:

```powershell
uv sync --locked
uv run alembic upgrade head
uv run python -m app.cli checkpoints
uv run python -m app.cli seed
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

In separate terminals, from `backend/`:

```powershell
uv run celery -A app.tasks.worker:celery worker --loglevel=INFO --pool=solo
uv run celery -A app.tasks.worker:celery beat --loglevel=INFO
```

Use the default prefork worker in Linux/Compose. `--pool=solo` is for native Windows development. Run exactly one Beat scheduler per environment.

From `frontend/`:

```powershell
npm ci
npm run dev
```

Vite proxies `/api` to the backend. All browser requests use one origin; cookies are never stored in localStorage. If only Redis is unavailable, `uv run python -m app.cli drain-jobs` executes currently pending jobs through the same graph/services. For a continuous development-only loop, from `backend/`, set `PYTHONPATH` to the absolute `backend/` path and run `uv run python ../scripts/local_job_loop.py`. This bypasses Celery transport and cannot verify Redis/Beat behavior.

## Live AI and offline mode

`AI_PROVIDER=demo` uses conservative text rules, displays “Offline demo,” and reports unknown tokens/cost. It simulates the workflow; its output is **not evidence of live-model accuracy**.

For live extraction, edit only `backend/.env`:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=your-server-side-key
OPENAI_MODEL=gpt-4.1-mini
```

The model above is a documented structured-output example, not a hardcoded application default. Choose an available model with native structured outputs. Restart backend and worker after changing configuration. No keys go in `VITE_*` variables. See [AI integration and verification](docs/ai.md) for sources, limits and the opt-in smoke test.

## Run checks

Backend tests require a **dedicated PostgreSQL database named `intakeflow_test` or `intakeflow_test_*`**. Tests truncate its business/checkpoint tables. They refuse other names. From the repository root:

```powershell
docker compose exec db createdb -U intakeflow intakeflow_test
cd backend
$env:DATABASE_URL='postgresql+psycopg://intakeflow:intakeflow@localhost:5432/intakeflow_test'
uv run alembic upgrade head
uv run python -m app.cli checkpoints
uv run pytest --cov=app --cov-report=term-missing
uv run ruff check app tests alembic
uv run ruff format --check app tests alembic
```

On POSIX shells use `export DATABASE_URL=...`. Remove the test override before running the development server. Automated tests use deterministic providers and PostgreSQL, including real separate worker processes, row locks, unique constraints, late responses, stale drafts and concurrent approval. The paid test is skipped by default.

From `frontend/`:

```powershell
npm ci
npm run lint
npm run format:check
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

The E2E suite expects the seeded app, API, and background worker at http://localhost:5173. It exercises the complete tenant → staff clarification → tenant reply → new AI revision → staff correction/priority → confirmed approval → exactly one order → tenant status flow. It also checks a 390px mobile layout. Set `PLAYWRIGHT_BASE_URL` for a different origin and match `APP_ORIGIN` on the backend. Traces and screenshots are retained on failure. GitHub Actions defines backend, frontend, and Compose E2E jobs; it never runs paid AI evaluations.

## Evaluate extraction quality

There are **64 independently labeled synthetic conversations: 40 development and 24 held-out** in [evals/dataset.jsonl](evals/dataset.jsonl). The prompt never consumes gold labels. Cases include unclear reports, missing fields, clarifications, contradictions, prompt injection, unsupported facts, unrelated issues and correction preservation.

From `backend/`:

```powershell
# Free, simulated plumbing check; results must not be called live AI accuracy.
uv run python -m app.ai.evaluate --provider demo --split dev

# Explicit paid runs, after configuring OPENAI_MODEL and OPENAI_API_KEY.
uv run python -m app.ai.evaluate --provider openai --allow-paid --split dev --output ../evals/results/live-dev.json
uv run python -m app.ai.evaluate --provider openai --allow-paid --split heldout --output ../evals/results/live-heldout.json
```

JSON and Markdown reports include provider/model, prompt, schema, dataset and split versions, schema success, category accuracy, scalar field precision/recall, lexical symptom precision/recall and combined field metrics, unsupported scalar rate, evidence validity, missing-field detection, latency and known estimated cost. Exact matching is intentionally auditable and undercounts semantically correct paraphrases. Follow-up relevance and semantic correctness require the human rubric in [evals/rubric.md](evals/rubric.md); they remain unknown until reviewed. Use the supplied score-import command to calculate human metrics. Never tune the prompt against held-out cases. [The included development report](evals/results/demo-dev.md) is explicitly simulated.

## Architecture

```mermaid
flowchart LR
  Browser[React / Router / Query / RHF] -->|same-origin Fetch + CSRF cookie| API[FastAPI routes]
  API --> Services[Authorized business services]
  Services --> DB[(PostgreSQL 17)]
  DB --> Jobs[Durable jobs]
  Beat[Celery Beat] -->|discover every 5 seconds| Jobs
  Jobs --> Redis[(Redis broker)]
  Redis --> Worker[Celery worker]
  Worker --> Graph[LangGraph]
  Graph --> Provider[Demo or LangChain ChatOpenAI]
  Graph --> Checkpoints[(PostgreSQL checkpoints)]
  Graph --> Services
```

Routes translate HTTP. Services enforce roles, ownership, versions, state transitions and transaction boundaries. Repositories contain reusable queries. AI modules build prompts, validate output and evidence, and coordinate the graph. Tasks call services; they do not own business rules.

```mermaid
flowchart TD
  Pause[Real LangGraph review interrupt] -->|server-loaded durable job| Kind{Job kind}
  Kind -->|EXTRACT| Load[Load authorized source snapshot]
  Load --> Extract[Bounded structured extraction]
  Extract --> Validate[Schema and exact evidence validation]
  Validate --> Persist[Persist immutable AI revision if current]
  Persist --> Pause
  Kind -->|COMMAND| Check[Recheck membership, role and both revisions]
  Check --> Action{Review action}
  Action -->|revise / clarify| Commit[Commit idempotent command receipt and audit]
  Commit --> Pause
  Action -->|approve| Order[Atomically create unique work order + audit + receipt]
  Action -->|reject| Rejected[Record reason and notification]
  Order --> End[End]
  Rejected --> End
```

The graph pauses before extraction as well as after it, so manual commands can be processed without invoking a broken model. This still follows load → extract → validate → persist → human review for extraction jobs. The server supplies the thread ID and job ID. There is no public graph-resume endpoint. Tenant answers enqueue extraction; they never approve.

**Checkpoint commits and business commits are separate.** A PostgreSQL durable job is saved with the request/message/review command. Beat may deliver it multiple times. Workers claim jobs with leases, serialize graph access using a session advisory lock per request, reserve every model call durably, and record immutable revisions unique by job. A graph node may replay after interruption: command receipts make completed actions idempotent, source/draft checks reject stale commands, and a unique request-to-order constraint is the final duplicate-order barrier. A crash after a business commit but before a checkpoint can replay the operation safely. No business transaction remains open during model I/O; the advisory-lock connection runs in autocommit.

```mermaid
erDiagram
  ORGANIZATION ||--o{ MEMBERSHIP : scopes
  USER ||--o{ MEMBERSHIP : joins
  MEMBERSHIP ||--o{ SESSION : authenticates
  ORGANIZATION ||--o{ PROPERTY : owns
  PROPERTY ||--o{ UNIT : contains
  UNIT ||--o{ TENANT_UNIT_ASSIGNMENT : assigned
  MEMBERSHIP ||--o{ TENANT_UNIT_ASSIGNMENT : permits
  UNIT ||--o{ MAINTENANCE_REQUEST : receives
  MAINTENANCE_REQUEST ||--o{ REQUEST_MESSAGE : preserves
  MAINTENANCE_REQUEST ||--o{ AI_EXTRACTION_REVISION : suggests
  MAINTENANCE_REQUEST ||--o{ REVIEWED_DRAFT_REVISION : reviews
  REVIEWED_DRAFT_REVISION ||--o{ FIELD_CORRECTION : records
  MAINTENANCE_REQUEST ||--o{ WORKFLOW_COMMAND : resumes
  MAINTENANCE_REQUEST ||--o| WORK_ORDER : approves
  MAINTENANCE_REQUEST ||--o{ DURABLE_JOB : schedules
  DURABLE_JOB ||--o{ MODEL_INVOCATION : measures
  ORGANIZATION ||--o{ AUDIT_EVENT : records
```

The diagram shows logical relationships; organization-aware composite foreign keys protect trusted unit, requester and request relationships. PostgreSQL triggers reject updates/deletes to source messages, extraction/draft revisions, corrections and audit events. Request title, original body, ownership and graph-thread identity are immutable. All timestamps are UTC; the UI uses the organization’s IANA timezone, default Asia/Karachi.

## State and approval rules

Central mappings live in `backend/app/services/states.py`.

| Current request state | Allowed next states |
| --- | --- |
| PROCESSING | NEEDS_REVIEW, PROCESSING_FAILED, WAITING_FOR_TENANT, APPROVED, REJECTED |
| NEEDS_REVIEW | PROCESSING, WAITING_FOR_TENANT, APPROVED, REJECTED |
| WAITING_FOR_TENANT | PROCESSING, NEEDS_REVIEW, APPROVED, REJECTED |
| PROCESSING_FAILED | PROCESSING, NEEDS_REVIEW, WAITING_FOR_TENANT, APPROVED, REJECTED |
| APPROVED / REJECTED | Terminal |

Manual staff review can complete a processing or failed request. Work orders transition OPEN → IN_PROGRESS → COMPLETED; OPEN or IN_PROGRESS may become CANCELED. Completed/canceled states are terminal. Explicit description edits remain audited.

Approval requires a verified assigned unit/property, a current reviewed category (UNKNOWN is incomplete; OTHER is allowed), affected area, description of at least 10 characters, staff-selected ROUTINE/PRIORITY/URGENT, and the deterministic category team. Multiple-issue flags additionally require explicit staff separation acknowledgment. Staff must save against the latest conversation. A later extraction adds proposed differences and never overwrites a staff correction. After approval, tenant discussion is preserved without regenerating extraction or changing the order.

HTTP approval returns **202 pending**, not success-as-approved. React polls while processing or a command is pending, and only displays approval after the server confirms the committed request state. Mutations invalidate affected queries. Conflicts preserve unsaved edits and offer an explicit reload.

## Retry, recovery and operations

- Input: 5,000 characters per tenant message, 30 conversation messages, and a 24,000-character extraction cap. Oversized conversations fail visibly for manual processing.
- Default provider timeout: 45 seconds. At most two transport retries, one malformed-output repair, and four total calls including retries/repair/replay per job. Authentication/configuration/evidence failures are not retried automatically. SDK retries are disabled.
- Each call reserves its budget and records provider/model, prompt/schema/source version and outcome before inference. Available tokens/cost and latency are then recorded. A crashed call can remain STARTED, accurately reflecting an unknown outcome. No secrets or full reports are logged by default.
- Jobs use a 300-second lease; Beat rediscovers abandoned RUNNING jobs. Duplicate task deliveries are harmless. Redis loss does not lose business jobs.
- Failed extraction exposes retry to staff and leaves the manual reviewed-draft path available. Failed infrastructure stays recoverable after lease expiry. Request command ownership serializes staff actions, while new messages invalidate drafts.
- `/api/v1/health/live` checks the API; `/api/v1/health/ready` checks database migration/checkpoint tables and Redis. Worker/Beat containers have separate health checks. Logs include request ID, route template, status and latency, without tenant bodies.

## Accounts and administration

ADMIN can manage organization properties, units, accounts and assignments and view usage/audits. STAFF reviews organization requests and updates work orders. TENANT submits only for assigned units and reads only their own requests/orders. Backend services enforce every write permission. List/detail query scopes enforce read permissions.

From `backend/` (also available through `docker compose exec backend ...`):

```powershell
uv run python -m app.cli create-user --organization ORG_UUID --email staff@example.com --name "Staff Member" --role STAFF
uv run python -m app.cli create-user --organization ORG_UUID --email tenant@example.com --name "Tenant Member" --role TENANT
uv run python -m app.cli assign-unit --organization ORG_UUID --email tenant@example.com --unit UNIT_UUID
```

Passwords are prompted without echo, hashed with Argon2id, and never passed as shell arguments. Existing accounts can gain an organization membership through the command. Invite email is out of scope. IDs appear in administration views and API responses.

## Deployment assumptions

Compose is a local-development configuration with local credentials and loopback ports. For deployment, terminate HTTPS, serve `frontend`’s Dockerfile `production` target and route `/api/` to FastAPI on the same hostname using the supplied Nginx configuration. Set `APP_ORIGIN=https://your-host`, `SECURE_COOKIES=true`, `ENVIRONMENT=production`, `DEMO_ACCOUNTS_ENABLED=false`, and `AI_PROVIDER=openai`. Production settings reject demo accounts, demo AI, or insecure cookies. Supply database/broker passwords via your secret manager rather than the development Compose values. Run migrations/checkpoint setup as a release job before application replicas. Preserve database storage and use a least-privilege application database account.

Assumptions: one issue per request; immutable trusted unit assignment at submission; staff chooses final priority; team routing is deterministic; no automatic merging. Organization timezone is selected at registration. A user with multiple memberships supplies an organization ID on login.

## Five-minute demonstration

1. **0:00–0:45** Sign in as tenant, choose Cedar A-101, submit “The sink has been leaking since yesterday and the cupboard underneath is wet.” Leave location absent. Watch processing become NEEDS_REVIEW.
2. **0:45–1:45** In another browser profile sign in as staff. Open the request. Inspect the original message, suggested fields, unknown location and exact evidence links. Note that priority is unset.
3. **1:45–2:30** Staff sends “Which room is the sink in?” Tenant reloads, answers “The sink is in the kitchen,” and sees processing. No automatic approval occurs.
4. **2:30–3:30** Staff reloads, inspects the second AI revision and proposed differences, adopts or enters kitchen, corrects the description, selects PRIORITY and saves. The previous draft remains in history. Save advances the durable review command.
5. **3:30–4:15** Approve after the save command finishes. Confirm the dialog. Observe queued → server-confirmed APPROVED and a single OPEN work order. Tenant reloads and opens its status.
6. **4:15–5:00** Show admin usage and audit pages. Explain unknown demo usage/cost, immutable corrections, isolation between organizations, and the worker-restart test. Optionally stop/restart the worker while a request waits for human review; its checkpoint remains in PostgreSQL.

## Interview discussion and limits

Useful implemented examples: transactional durable jobs instead of a best-effort enqueue; idempotent graph side effects across separate checkpoint commits; provenance validation versus factual correctness; optimistic staff review; tenant and organization scope in composite foreign keys; explicit human priority; unknown usage instead of misleading zero; and deterministic tests separate from paid model evaluation.

Current scope is English text and internal work orders only. No RAG/vector store, attachments, dispatch, scheduling, payments, email/SMS, password reset or invitations. The rule-based offline provider is deliberately limited and can miss ambiguity/contradiction; it must not be used as a live-model quality proxy. Human evaluation scores remain pending until a person applies the rubric. Administration selectors show paginated directories; exceptionally large organizations would benefit from searchable selectors. See [verification record](docs/verification.md) for what was actually executed and environment limits.
