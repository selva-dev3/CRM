# Backend Project Rules — Python + FastAPI + PostgreSQL + REST

Intha rules follow pannina, backend consistent ah, scalable ah, secure ah,

and future-la oru new dev join pannalum easy ah puriyura maadhiri irukkum.

---

## 1. Project Structure

```

app/

api/

v1/

routers/            # FastAPI routers — only request/response wiring

users.py

payroll.py

deps.py               # shared dependencies (get\_db, get\_current\_user)

core/

config.py               # pydantic Settings, env vars

security.py              # JWT, password hashing

logging.py                # logger config

db/

session.py                # SQLAlchemy engine/session factory

base.py                    # Base declarative model

migrations/                # Alembic migrations

models/                        # SQLAlchemy ORM models, one file per entity

user.py

payroll\_item.py

schemas/                        # Pydantic schemas (request/response DTOs)

user.py

payroll\_item.py

services/                        # business logic — the only layer that

user\_service.py                 # talks to repositories and enforces rules

payroll\_service.py

repositories/                      # DB query layer — no business logic here

user\_repository.py

payroll\_repository.py

workers/                             # background jobs / celery tasks

tests/

unit/

integration/

main.py                                # FastAPI app instantiation only

alembic.ini

.env.example

```

**Rule:** Routers only handle request parsing, calling a service, and

returning a response. No DB queries, no business logic inside a router

function — that belongs in `services/` and `repositories/`.

**Layering rule (strict):** `router → service → repository → model`. A

router never imports a repository directly, and a service never writes raw

SQL/ORM queries inline — it calls a repository function.

---

## 2. API Design Rules

1. **Versioned routes**: everything under `/api/v1/...`. Breaking changes

get a new version (`/api/v2/...`), never a silent breaking change to v1.

2. **Resource-based, plural nouns**: `/users`, `/payroll-items/{id}` — not

verbs in the URL (`/getUser`).

3. **HTTP methods used correctly**: `GET` (read, no side effects), `POST`

(create), `PUT`/`PATCH` (update — `PATCH` for partial), `DELETE` (remove).

4. **Status codes are meaningful**: `200` OK, `201` Created, `204` No

Content, `400` validation error, `401` unauthenticated, `403`

unauthorized, `404` not found, `409` conflict, `422` unprocessable

entity, `500` only for genuinely unexpected server errors.

5. **Pagination on every list endpoint** — `limit`/`offset` or cursor-based;

never return an unbounded list from the DB.

6. **Filtering/sorting via query params**, validated against an allow-list

of sortable/filterable fields — never pass raw user input into `ORDER BY`.

7. **Idempotency**: `PUT`/`DELETE` must be idempotent. For `POST` endpoints

that create side effects (payments, etc.), support an idempotency key.

---

## 3. FastAPI Rules

1. **Dependency Injection** for everything cross-cutting: DB session

(`get_db`), current user (`get_current_user`), pagination params — via

`Depends()`, not manual instantiation inside route functions.

2. **Pydantic schemas for every request/response** — never return a raw

SQLAlchemy model or `dict` directly. `response_model=` set explicitly on

every route.

3. **Separate schemas** for `Create`, `Update`, and `Read` per entity

(`UserCreate`, `UserUpdate`, `UserRead`) — don't reuse one schema for all

three when the fields genuinely differ (e.g. `id`, `created_at` only on

`Read`).

4. **Routers stay thin** — one router per resource, registered in

`main.py`/`api/v1/__init__.py` with a prefix and tags.

5. **Async by default** for I/O-bound routes (`async def`) when using an

async DB driver (`asyncpg`); don't mix sync blocking calls inside an

async route without `run_in_threadpool`.

6. **Background tasks**: use FastAPI `BackgroundTasks` only for

fire-and-forget, non-critical work (e.g. sending a notification). Use a

real task queue (Celery/RQ + Redis) for anything that must survive a

process restart or needs retries.

7. Auto-generated docs (`/docs`, `/redoc`) kept accurate by writing proper

docstrings, `response_model`, and `Field(description=...)` on schemas —

don't leave endpoints undocumented.

---

## 4. Python / Typing Rules

1. **Type hints everywhere** — every function signature (params + return

type). Run `mypy` (or `pyright`) in CI; no untyped functions in

`services/`, `repositories/`, or `schemas/`.

2. No bare `except:` — always catch a specific exception type. No silent

`except Exception: pass`.

3. Follow **PEP 8**, enforced via `ruff`/`flake8` + `black` formatting — not

manual style debates.

4. Use `pydantic` models (not raw dicts) for any structured data crossing a

function boundary (API payloads, config, service inputs/outputs).

5. Prefer `pathlib` over `os.path` string manipulation for file paths.

6. Use dataclasses or Pydantic models instead of loose tuples/dicts for

anything with more than 2 related fields.

---

## 5. Database (PostgreSQL) Rules

1. **SQLAlchemy ORM** (2.0-style, or your chosen ORM) for all queries —

raw SQL only for genuinely complex reporting queries, and even then,

parameterized (never string-formatted SQL — SQL injection risk).

2. **Alembic migrations** for every schema change — no manual `ALTER TABLE`

run directly against a database. One migration per logical change,

reviewed like code.

3. **Indexes** on every foreign key and every column used in a `WHERE`/

`ORDER BY` on a frequently-queried table. Verify with `EXPLAIN ANALYZE`

on slow queries before shipping.

4. **Constraints at the DB level** (`NOT NULL`, `UNIQUE`, `CHECK`, foreign

keys with `ON DELETE` behavior defined) — don't rely on application code

alone to enforce data integrity.

5. **Connection pooling** configured explicitly (pool size, timeout,

`pool_pre_ping=True`) — don't use default/unbounded connections in

production.

6. **Transactions**: wrap multi-step writes in a single transaction

(`session.begin()`); roll back fully on any failure — no partial writes.

7. **N+1 query prevention**: use `selectinload`/`joinedload` explicitly for

relationships accessed in a loop; don't lazy-load inside a list endpoint.

8. Soft-delete (`deleted_at` column) only where genuinely needed for audit/

recovery — don't default every table to soft-delete if hard-delete is

fine.

---

## 6. Repository & Service Layer Rules

1. **Repositories** contain only DB query logic (get, list, create, update,

delete) — no business rules, no validation beyond what the DB enforces.

2. **Services** contain business logic: validation rules beyond schema

validation, orchestrating multiple repository calls, enforcing

authorization rules specific to the domain, raising domain exceptions.

3. A service never returns a raw SQLAlchemy model to a router — it returns

data the router converts via a Pydantic schema (or the service itself

returns the schema).

4. One service class/module per domain entity/feature — don't create a

single giant `services.py` with everything mixed in.

---

## 7. Authentication & Authorization Rules

1. **JWT-based auth** (access + refresh token pattern) via `python-jose`/

`pyjwt`, or session-based via signed cookies — pick one, stay consistent.

2. Passwords hashed with `bcrypt`/`argon2` (via `passlib`) — never store or

log plaintext passwords.

3. **Role/permission checks** enforced in a dependency (`Depends(require_role("admin"))`)

reused across routes — never duplicated `if user.role != "admin"` checks

scattered per endpoint.

4. Access tokens short-lived; refresh tokens stored securely (httpOnly

cookie or hashed in DB) with rotation on use.

5. Never trust a client-supplied user ID/role in the request body for

authorization decisions — always derive identity from the verified

token via `get_current_user`.

---

## 8. Validation & Error Handling Rules

1. **Pydantic validates all input at the schema boundary** — routers never

manually re-validate fields that the schema already covers.

2. **One standardized error response shape**

(`{ "code": str, "message": str, "fields": dict | None }`) returned by a

global exception handler (`@app.exception_handler`) — no per-endpoint

ad hoc error bodies.

3. **Custom domain exceptions** (`UserNotFoundError`, `InsufficientFundsError`)

raised in services, caught once at a global handler and mapped to the

right HTTP status — routers don't `try/except` around every call.

4. Never leak internal details (stack traces, raw DB errors, file paths) in

an API error response — log the full detail server-side, return a safe

generic message to the client.

5. `422` reserved for request validation errors (FastAPI's default);

`400`/domain-specific codes for business-rule violations.

---

## 9. Security Rules

1. **CORS** explicitly configured with an allow-list of origins — never

`allow_origins=["*"]` in production.

2. **Rate limiting** on public/auth endpoints (login, password reset,

signup) via `slowapi` or a reverse-proxy/API-gateway layer.

3. **Input sanitization**: never interpolate raw user input into SQL,

shell commands, or file paths. Use parameterized queries and `pathlib`

safely.

4. **Secrets** (DB creds, JWT secret, third-party API keys) only via

environment variables / a secrets manager — never committed, never

hardcoded.

5. **Security headers** via middleware (`Strict-Transport-Security`,

`X-Content-Type-Options`, `X-Frame-Options`) — e.g. `secure` package or

reverse proxy config.

6. **Dependency hygiene**: `pip-audit`/`safety` run regularly in CI; pin

versions in `requirements.txt`/`pyproject.toml` (lockfile via `poetry`

or `pip-tools`).

7. File uploads: validate content-type and size server-side, scan/limit

before persisting; never trust the client-reported extension alone.

---

## 10. Caching Rules

1. **Redis** for cache — cache read-heavy, expensive, or rarely-changing

data (e.g. computed reports, lookup tables), not everything by default.

2. Explicit **TTL** on every cache key — no cache entry lives forever

unintentionally.

3. **Cache invalidation** happens explicitly on the write path (update/

delete the cache key when the underlying data changes) — don't rely on

TTL alone for correctness-sensitive data.

4. Cache keys namespaced consistently (`user:{id}`, `payroll:items:{filters_hash}`)

so invalidation and debugging are predictable.

---

## 11. Background Jobs / Queue Rules

1. **Celery + Redis/RabbitMQ** (or equivalent) for anything that must

survive a restart, needs retries, or takes longer than a request cycle

should reasonably block for.

2. Every task is **idempotent** — safe to run twice (e.g. use an

idempotency key or check-before-write) since queues can redeliver.

3. **Retry policy** defined per task (max retries, backoff) — don't let a

failing task retry forever or silently die after one failure.

4. Long-running/scheduled jobs (reports, cleanups) via `celery beat` or a

scheduler — not a cron script duplicating logic that lives in the app.

---

## 12. Testing Rules

1. **Unit tests** for every service function (business logic), mocking the

repository layer — fast, no real DB needed.

2. **Integration tests** for every API endpoint against a real (test)

PostgreSQL database (via `pytest` + `testcontainers` or a dedicated test

DB), covering: happy path, validation failure, auth failure, not-found.

3. **Repository tests** against a real test DB to catch query bugs

(N+1, wrong joins, missing filters) that mocks would hide.

4. Test DB reset/seeded per test run (fixtures/factories via

`factory_boy` or similar) — tests never depend on shared mutable state.

5. Coverage tracked (`pytest-cov`); critical paths (auth, payments, data

mutation) require close to full coverage — not an arbitrary global %.

---

## 13. Performance Rules

1. **Async I/O** (async DB driver, async HTTP clients via `httpx`) for

endpoints under real concurrent load — avoid blocking calls in async

routes.

2. **Query optimization**: avoid N+1 (see §5.7), use `EXPLAIN ANALYZE` on

slow endpoints, add indexes based on actual query patterns not guesses.

3. **Pagination everywhere** (see §2.5) — never load an entire table into

memory to filter/sort in Python.

4. **Connection pooling** tuned for expected concurrency (see §5.5).

5. Profile before optimizing — use `py-spy`/APM tooling to find the actual

bottleneck rather than guessing.

---

## 14. Logging & Monitoring Rules

1. **Structured logging** (`structlog` or `python-json-logger`) — logs as

JSON with consistent fields (`request_id`, `user_id`, `level`,

`message`), not free-text `print()`/ad hoc `logging.info(f"...")`.

2. **Request ID / correlation ID** generated per request (middleware),

propagated through service/repository logs and to any downstream calls,

so a single request's full trace is grep-able.

3. **No `print()` statements** in committed code — always the logger.

4. Error tracking (Sentry or equivalent) wired in for unhandled exceptions

— not just server logs that nobody watches.

5. **Health check endpoint** (`/health`) that verifies DB connectivity, not

just "process is alive."

6. Log levels used correctly: `DEBUG` (dev only), `INFO` (normal

operations), `WARNING` (recoverable issue), `ERROR` (needs attention) —

don't log everything at `INFO`.

---

## 15. Environment & Config Rules

1. **Pydantic `Settings`** class (`core/config.py`) loads all env vars with

types and defaults — no scattered `os.getenv()` calls across the

codebase.

2. `.env.local`/`.env` for real secrets (never committed); `.env.example`

committed with all required keys present, values blank/placeholder.

3. Separate configs per environment (`local`, `staging`, `production`) via

env var, injected at deploy time — never hardcoded environment checks

sprinkled through business logic.

4. Feature flags (if used) centralized in one config/module, not ad hoc

conditionals scattered across services.

---

## 16. Naming Conventions

- Modules/files: `snake_case.py` (`payroll_service.py`)

- Classes: `PascalCase` (`PayrollService`, `UserRepository`)

- Functions/variables: `snake_case` (`get_user_by_id`)

- Pydantic schemas: `PascalCase`, suffixed by intent

(`UserCreate`, `UserRead`, `UserUpdate`)

- SQLAlchemy models: `PascalCase`, singular (`User`, `PayrollItem`)

- DB tables: `snake_case`, plural (`users`, `payroll_items`)

- Constants: `UPPER_SNAKE_CASE`

---

## 17. Reuse-First Rule (Check Before You Create)

**Before writing any new service function, repository method, schema, or

util — search the codebase first. Creating a duplicate is a rule

violation.**

1. Check `repositories/` for an existing query before writing a new one.

2. Check `schemas/` for an existing Pydantic model before defining a new

shape for the same entity.

3. Check `core/`/shared `utils` modules before writing a new helper.

4. If something similar exists but doesn't quite fit, **extend it**

(add a param, add an optional field) rather than duplicating it —

unless extending would break an existing caller's contract.

---

## 18. Analysis-Before-Implementation Rule

1. For any non-trivial bug fix or feature: analyze root cause (bugs) or

full scope (features) first — don't jump straight into code.

2. **Present the analysis + plan, then stop and ask** for explicit

confirmation before implementing, unless pre-approved for the session.

3. Implement exactly what was approved. If the real fix needs to go beyond

scope mid-implementation, stop and re-confirm — don't silently expand.

4. After implementing: state what changed (files touched, behavior

before/after) and any follow-up tests/migrations still needed.

5. Applies to both a human developer and any AI coding assistant working

in this repo — no exceptions for "it's a small fix."

---

## 19. Git / Workflow Rules

See the root [`AGENT.md`](../AGENT.md) for git/workflow rules.

---

## 20. Code Quality & Tooling Rules

1. **`ruff`** (lint) + **`black`** (format) + **`mypy`** (type-check)

enforced project-wide via one shared config — no per-file style

disagreements.

2. **`pre-commit`** hooks: run lint + format + type-check on changed files

before a commit is allowed — bad code never reaches the remote branch.

3. No commented-out dead code left in — delete it (git history keeps it).

4. No `print()`/debug statements left in committed code (see §14.3).

5. Dependencies pinned via `poetry.lock` / `requirements.txt` generated

from `pip-compile` — no unpinned installs in production images.

---

## 21. CI/CD & Deployment Rules

1. **Pipeline order**: lint → type-check (`mypy`) → unit tests → migration

check (Alembic upgrade runs clean) → integration tests → build (Docker

image) → deploy. Fail fast.

2. Every PR gets CI run against a real test PostgreSQL instance (Docker

service in CI), not just mocked DB calls for integration tests.

3. Separate environments: `local` → `staging` → `production`. Production

deploys only from `main` after CI is green and required approvals are

in.

4. **Migrations run automatically** as part of deploy (`alembic upgrade

head`) before the new app version starts serving traffic — never a

manual, undocumented migration step.

5. Rollback plan: previous Docker image/build stays deployable; migrations

written to be backward-compatible where possible (avoid destructive

changes in the same deploy as the code that depends on them).

6. Containerized via **Docker**; `docker-compose` for local dev

(app + Postgres + Redis) so environment parity is real.

---

## 22. API Documentation Rules

1. OpenAPI/Swagger docs (`/docs`) are the single source of truth — kept

accurate via proper `response_model`, docstrings, and `Field(description=...)`

on every schema/route (see §3.7).

2. Non-obvious business rules (why a field is required, why a status

transition is restricted) documented as a short comment or in the

route/service docstring — not left implicit.

3. If the API is consumed by a separate frontend team, publish the OpenAPI

spec (`/openapi.json`) so client types/SDKs can be generated instead of

hand-typed on their side.

---

**

Additional Senior Backend Engineering Rules — Production Quality

The existing backend rules already cover API design, FastAPI layering, typing, PostgreSQL, repositories/services, authentication, validation, security, caching, background jobs, testing, performance, observability, CI/CD, and API documentation. The following rules add only the remaining cross-cutting safeguards.

1. Transaction & Data Integrity Safety

Define transaction boundaries deliberately. A business operation containing multiple dependent writes must commit atomically; do not leave partially completed workflows.

Do not hold database transactions longer than necessary. Perform slow external I/O outside the transaction when correctness allows.

Never perform irreversible external side effects before the database state is safely committed unless the operation has an explicit compensation/idempotency strategy.

Use database constraints as the final protection against concurrent writes. Application checks such as “does this already exist?” must not be the only protection against duplicates or race conditions.

Handle transaction conflicts explicitly. Unique-constraint, serialization, deadlock, and optimistic-concurrency failures should map to predictable domain/API responses where applicable.

Use optimistic locking/version checks for resources that can be concurrently edited when last-write-wins would be unsafe.

2. Concurrency & Idempotency

Every retryable operation must have a safe retry story. Requests, jobs, and external calls must not create duplicate side effects when retried.

Protect state-changing endpoints from accidental duplicate requests. Use idempotency keys, uniqueness constraints, or domain-specific safeguards where appropriate.

Never assume a request is processed exactly once. Design for retries, client reconnects, proxy retries, and worker redelivery.

Define lock scope and ordering when using database locks. Avoid unnecessary locks and inconsistent lock ordering that can create deadlocks.

Do not use process-local state for correctness in a multi-worker deployment. Shared correctness state belongs in the database, Redis, or another shared system.

3. API Contract & Compatibility

Treat API contracts as public interfaces. A response field removal, type change, required-field change, or semantic change is a breaking change even if the endpoint URL stays the same.

Prefer additive, backward-compatible API changes. Introduce new fields before removing old ones and document deprecation periods when consumers need migration time.

Validate pagination boundaries. Enforce sensible maximum page sizes; never allow an unbounded or attacker-controlled database workload through limit/offset.

Validate sort and filter parameters against explicit allow-lists. Never dynamically construct column names from unchecked user input.

Return consistent representations. Equivalent endpoints should use consistent naming, nullability, pagination metadata, timestamps, and error semantics.

Use UTC for persisted timestamps and define timezone behavior explicitly at API boundaries. Never rely on server-local timezone for business logic.

4. Database & Migration Safety

Every migration must be reversible or have a documented recovery strategy. Review destructive changes separately from ordinary schema additions.

Prefer expand → migrate/backfill → switch → contract for risky schema changes. Do not deploy code that requires a column or constraint before compatible schema changes are safely available.

Large data migrations must be bounded and resumable. Avoid one enormous transaction that can lock tables or exhaust resources.

Review indexes for write cost as well as read benefit. An index is not automatically beneficial just because a column is queried.

Never load unbounded database results into application memory. Stream, paginate, batch, or aggregate at the database layer.

Explicitly define cascade behavior for every relationship. Deleting a parent must not unexpectedly delete or orphan data.

Use database constraints for uniqueness and referential integrity even when equivalent service validation exists.

5. External Service & Network Safety

Every outbound network call needs explicit timeout settings. Never allow an external dependency to hold a request indefinitely.

Define retry behavior by failure type. Retry transient failures only; never blindly retry non-idempotent operations.

Use bounded retries with exponential backoff and jitter where appropriate.

Treat external services as unreliable dependencies. Handle timeout, connection failure, malformed response, rate limit, and service-unavailable cases explicitly.

Use circuit-breaking or equivalent protection for repeatedly failing critical dependencies when the system's scale requires it.

Validate and constrain outbound URLs and redirects when URLs originate from user-controlled or external data.

6. Authentication, Authorization & Session Safety

Authorization must be checked at the resource level, not only at the route level. A valid role does not automatically grant access to every resource.

Enforce tenant/organization boundaries at the service/repository layer when multi-tenant data exists. Never rely only on frontend filtering.

Deny by default when permission information is missing or ambiguous.

Avoid exposing whether a sensitive account/resource exists when that distinction can enable enumeration.

Invalidate or rotate sessions/tokens after security-sensitive events such as password changes, credential resets, or account compromise.

Never log access tokens, refresh tokens, passwords, session cookies, authorization headers, or other credentials.

7. Input, Output & File Safety

Apply maximum lengths and size limits to externally supplied input. Validation should protect both correctness and resource usage.

Validate uploaded files by actual content/type and size, not only filename extension or client MIME type.

Store uploaded files outside executable/application code paths and use generated safe filenames.

Encode or sanitize output according to its destination. Data safe for JSON is not automatically safe for HTML, SQL, shell commands, logs, or headers.

Never pass user-controlled input directly to shell commands, dynamic SQL, filesystem paths, or template execution.

8. Caching & Consistency

Cache only data whose staleness behavior is explicitly understood. Do not cache correctness-sensitive data without a defined consistency strategy.

Cache keys must include every input that changes the result. Missing a filter, tenant, locale, permission scope, or version can return incorrect data.

Never allow one tenant/user's cached data to be returned to another tenant/user.

Invalidate or version caches when schema or representation changes make old entries incompatible.

Define behavior when Redis/cache is unavailable. The application should fail safely or fall back appropriately rather than silently returning incorrect data.

9. Background Job Reliability

Persist enough job state to determine whether work completed, failed, or needs retry.

Make jobs observable. Record useful job identifiers, attempt counts, durations, and failure reasons without logging secrets.

Separate transient failures from permanent failures. Permanent validation/domain errors should not retry indefinitely.

Design job workflows for partial failure. If a job performs several external or database operations, define how it resumes or compensates after interruption.

Set explicit execution, retry, and dead-letter limits for long-running queues.

10. Observability & Operational Readiness

Every request should be traceable through a correlation/request ID. Propagate it to logs and downstream calls where possible.

Measure important backend behavior, not only errors. Track latency, throughput, error rates, database performance, queue health, and dependency failures.

Health checks should distinguish liveness from readiness. A process can be alive while its database or critical dependency is unavailable.

Do not put secrets or sensitive personal data into logs, metrics, traces, or error reports.

Log enough context to reproduce an incident without logging confidential payloads.

Define alert thresholds for critical production failures. Monitoring without actionable alerts does not provide operational safety.

11. Configuration & Deployment Safety

Fail fast on invalid required configuration at startup. Do not allow the application to start in a partially configured state.

Keep configuration validation centralized. Services and repositories should consume typed settings rather than reading environment variables directly.

Use backward-compatible deployments for schema/API changes whenever rolling deployments are possible.

Do not assume all application instances deploy simultaneously. During rollout, old and new versions may run together.

Make migrations safe for the currently running application version before deploying code that depends on them.

12. Testing & Verification

Test concurrency-sensitive behavior explicitly. Unique constraints, simultaneous updates, duplicate requests, and retry scenarios should have tests where they matter.

Test authorization boundaries, not only successful authorization. Include forbidden cross-user, cross-role, and cross-tenant access where applicable.

Test migration paths against representative data. A migration that works on an empty database is not sufficient.

Test external dependency failures. Cover timeout, unavailable service, malformed response, and rate-limit behavior for critical integrations.

Test idempotency. Repeating the same request/job should produce the intended final state without unintended duplicate side effects.

Critical production bugs require regression tests whenever the behavior is testable.

Final Backend Production Review Gate

Before reporting a backend feature or bug fix as complete, confirm:

API contract and compatibility impact were reviewed.

Router → service → repository → model layering remains intact.

Request/response validation and error mapping are consistent.

Authorization is enforced at the correct resource/domain boundary.

Transactions and concurrency behavior are safe.

Duplicate requests and retries cannot create unintended side effects.

Database constraints, indexes, migrations, and cascade behavior were reviewed.

External calls have timeouts and appropriate retry behavior.

Cache keys, invalidation, and tenant/user isolation are correct.

Background jobs are idempotent, bounded, observable, and retry-safe.

Logs and telemetry contain useful diagnostics without secrets or sensitive data.

Relevant unit, integration, repository, migration, and E2E tests were run.

Actual API behavior was verified before claiming completion.

23. Critical Transaction & Failure-Path Rules

These rules are mandatory and supplement the existing transaction, exception, API, and testing rules above.

Never bypass an established transaction helper. If the service/class already provides a _commit, transaction wrapper, or equivalent helper, every commit path in that service must use it unless there is a documented reason not to.

Audit every conditional branch for transaction consistency. A safe commit path in one branch does not make another direct db.commit() safe.

A required persistence failure must propagate. After rollback, re-raise the original exception or convert it into the application's intentional domain/API error. Do not silently continue.

Rollback is recovery, not success. Calling rollback() must never by itself turn a failed write into a successful service operation.

Never return a successful API response when a required database write failed. 200/201/204 must represent an actually successful operation according to the endpoint contract.

Never use a broad exception handler as a success fallback. except Exception must not end with only rollback() or pass when the failed operation is required.

Do not silently swallow persistence errors. If an exception is intentionally handled, it must have an explicit recovery/partial-success contract and sufficient logging; otherwise it must propagate.

Preserve the original exception during cleanup failures. If rollback itself fails, record the rollback failure without replacing the original business/database failure used for diagnosis.

Before completing a service change, search the entire modified service for every commit(), flush(), rollback(), and broad exception path. Review them as one transaction/error-handling design.

24. Cross-Layer Contract Consistency Rules

Business allow-lists and enums must have one authoritative source whenever practical. Do not independently maintain frontend and backend lists for currencies, statuses, roles, categories, units, or similar values when they can drift.

When a shared source is not practical, add an automated contract test. CI must detect values accepted or returned by one layer but rejected by another.

Do not use runtime/browser capability as the business contract. Runtime APIs may describe platform support, but application-supported values must come from the product/API contract.

Every value the backend can return must be accepted by the frontend runtime validator. Test both supported values and unknown/mismatched values.

Unknown metadata must have intentional behavior. Either reject it with a clear contract error or normalize/fallback according to an explicitly documented rule; one invalid metadata field must not accidentally collapse an otherwise valid data section.

When changing a shared enum/allow-list, search all producers, consumers, schemas, validators, fixtures, seeds, and tests before implementation.

Update producer and consumer contracts together whenever possible. Do not merge a backend contract change while leaving a known incompatible frontend validator.

Type declarations are not runtime validation. Cross-service compatibility must be verified against actual serialized API responses.

25. Mandatory Regression Tests for Persistence & Contracts

For applicable changes, tests must prove:

Successful database commit persists the intended state.

Commit failure rolls back and propagates a failure.

Required write failure cannot produce a false-success API response.

Exceptions are not silently swallowed.

Conditional branches use the same safe transaction/error strategy.

Supported shared enum/allow-list values pass both backend and frontend validation.

Unsupported or mismatched values follow the intentional fallback/rejection behavior.

A valid response with invalid optional metadata does not unexpectedly fail an unrelated data section unless the contract explicitly requires the entire response to fail.

26. Backend Review Gate — Before PR

Before requesting review or reporting a backend change as complete:

Search for every direct db.commit() in modified services and confirm it follows the project's established transaction pattern.

Search for except Exception, bare except, pass, and silent rollback paths and verify none can hide a required failure.

Confirm every required write has truthful success/failure semantics.

Check all frontend/backend shared contracts for drift.

Add or update regression/contract tests for changed failure paths and shared values.

Run the relevant test suite plus lint/type checks.

Verify the actual API response, not only the Python type/schema.

Quick Checklist for Any New Feature**

- [ ] **Analyzed the issue/requirement fully, found root cause (bugs) or

full scope (features), and got explicit permission before

implementing (§18)\*\*

- [ ] **Checked for existing repository method/schema/service/util first —

reused or extended instead of duplicating (§17)\*\*

- [ ] Router stays thin — logic lives in service, queries live in

repository (§1, §6)

- [ ] Pydantic schemas defined for request and response, `response_model`

set (§3)

- [ ] Input validated at schema boundary; business rules validated in

service (§8)

- [ ] DB migration written via Alembic, reviewed, backward-compatible

where possible (§5, §21.4)

- [ ] Indexes added for new/foreign-key/frequently-queried columns (§5.3)

- [ ] Auth/permission check applied via shared dependency, not ad hoc

(§7.3)

- [ ] Errors mapped through the standardized error shape/global handler

(§8.2–8.3)

- [ ] Pagination added to any new list endpoint (§2.5)

- [ ] N+1 queries checked/avoided (`selectinload`/`joinedload`) (§5.7)

- [ ] Unit tests for service logic, integration tests for the endpoint

(§12)

- [ ] Structured logging with request ID, no `print()` left in (§14)

- [ ] Secrets/config via env vars only, `.env.example` updated if new keys

added (§15)

- [ ] Type hints complete, `mypy` passes, lint/format pass (§4, §20)

- [ ] OpenAPI docs accurate for the new/changed endpoint (§22)

- [ ] CI green: lint → type-check → unit tests → migration check →

integration tests → build (§21)