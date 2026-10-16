# Verification record

Executed on Windows with Python 3.12.10, Node 24.14.0, uv 0.12.10, and a workspace-local **real PostgreSQL 17.10** instance. The initial workspace was empty. No existing user code was replaced.

| Check | Result |
| --- | --- |
| Python frozen dependency installation | `uv sync --locked --offline` passed with the generated uv.lock |
| Fresh PostgreSQL migrations and LangGraph checkpoint setup | Passed on a separate test database |
| Alembic metadata drift | `alembic check` passed; no upgrade operations detected |
| Ruff lint and formatting | Passed |
| Backend pytest | 28 passed, 1 explicitly skipped paid smoke test; 78% overall coverage |
| Frontend clean npm lockfile installation | `npm ci --offline` passed after stopping Vite to release a native Windows module lock |
| Frontend lint, formatting and production build | Passed |
| Vitest / React Testing Library | 11 passed |
| Playwright Chromium | 3 passed: full clarification/approval workflow, 390px layout/navigation, administration directories/usage/audit |
| Simulated development evaluation | 40 labeled cases executed; JSON and Markdown report saved |
| Docker Compose schema/configuration | `docker compose config --quiet` passed |
| Live OpenAI adapter request/parse path | Passed using the installed LangChain/OpenAI SDKs and mocked HTTP transport; asserted strict JSON Schema, configured model ID and usage |

Backend tests cover organization and same-organization tenant isolation, roles, CSRF/origin checks, opaque hashed sessions, logout, rate limiting, idempotency, immutable source triggers, malformed output, exact evidence rejection, bounded transport/repair calls, old drafts, late responses, preserved corrections, authorized workflow commands, separate worker processes, competing approval, duplicate delivery, expired leases, manual handling during provider outage, and explicit work-order transitions. The browser suite was run against the real API and PostgreSQL, with the documented local development job loop processing the same durable jobs and LangGraph graph.

## Not verified here

The Docker daemon was unavailable (`npipe ... docker_engine ... system cannot find the file`). Container builds/startup, actual Redis broker delivery, Celery worker/Beat integration and their container health checks were **not executed locally**. The local job loop does not verify those components. The GitHub Actions Compose job is configured to verify them; it has not been run remotely from this workspace.

To verify the full infrastructure, start Docker Desktop and run the exact README startup sequence, then:

```text
docker compose ps
docker compose logs --tail=100 backend worker beat
curl http://localhost:8000/api/v1/health/ready
cd frontend
npm run test:e2e
```

The paid OpenAI network path and live-model semantic accuracy were not exercised. To verify those, configure backend-only credentials/model, run the opt-in smoke test and explicit `--provider openai --allow-paid` evaluation commands in the README. Human question/semantic scores require a person applying the rubric; they have not been invented from simulated results.

The local preview and QA processes were stopped after verification. Database files and generated test reports remain ignored under `.local/`, `backend/coverage.xml`, `frontend/playwright-report/`, and `frontend/test-results/`. Use the documented startup commands to run the app.
