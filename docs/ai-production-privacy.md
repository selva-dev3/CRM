# CRM AI privacy and lifecycle

The CRM database and authorization services remain the source of truth. The
provider receives only context that has passed tenant/RBAC/record-scope checks
and the centralized `AIDataClassificationService`.

## Local persistence

- Conversation prompts and final assistant text are retained for
  `AI_CONVERSATION_RETENTION_DAYS` (30 days by default).
- Validated action proposal payloads are retained for
  `AI_ACTION_RETENTION_DAYS` (30 days by default), then removed by scheduled
  cleanup. The resulting task keeps only its normal business fields and the
  nullable idempotency reference.
- Raw CRM result bodies are not retained in conversation history. Persisted
  result blocks contain bounded operational references and summaries.
- Deleting an owned conversation deletes its prompt history through the
  existing database cascade. The scheduled cleanup removes expired
  conversations. Organization deletion cascades organization-owned AI rows.
- Tool audits contain request/user/organization/tool/timing/result-count/error
  metadata only. They do not contain prompts or CRM result bodies.
- Legal hold is not implemented. A deployment that requires legal hold must
  suspend scheduled deletion under an approved operational process.

## Provider controls

- Susanoox is the only supported CRM LLM provider. The integration uses its
  OpenAI-compatible transport with request storage explicitly disabled via
  `store=False` and sends centrally minimized context only.
- Susanoox prompt/response retention, training use, deletion guarantees,
  residency, and provider-side logging remain **UNVERIFIED — EXTERNAL PROVIDER
  CONTRACT REQUIRED**. Source code cannot verify account-level or contractual
  controls; production approval requires written provider terms and a staging
  privacy review.
- OpenAI, Anthropic, and Gemini credentials/configuration are not accepted by
  the CRM AI runtime.

Never put provider credentials in the frontend or AI conversation records.
Pricing is deployment-owned configuration and unknown model pricing remains
explicitly `unknown`.

## Governed architecture

The canonical UI calls `POST /api/v1/ai/sales-assistant/chat` or its `/stream`
variant. FastAPI derives the user and effective organization from the
authenticated session/API key, then the AI domain service creates a validated
plan. Every CRM lookup is mapped to the provider-neutral `AIToolRegistry`,
validated again, permission/record-scope checked, and executed through an
existing CRM service where one exposes the required operation. Bounded advanced
reporting remains behind the same registry and authorization layer while it is
incrementally extracted from the legacy AI repository. The provider never
receives a database session, arbitrary SQL, URL, or Python function.

Initial registered capabilities include lead, contact, company, deal, task,
meeting, pipeline, and dashboard lookups. Each registration declares its
Pydantic arguments/results, permission, record-scope requirement, result cap,
timeout, sensitive-data policy, executor, and metadata-only audit policy.

`create_task` is the only enabled write action. It always requires explicit
confirmation. The action proposal ID is stored as a database-unique task
idempotency key, and the action/task update is committed atomically.

## Configuration

- `AI_CONVERSATION_RETENTION_DAYS`: local conversation retention (default 30).
- `AI_ACTION_RETENTION_DAYS`: local proposal-payload retention (default 30).
- `AI_RATE_LIMIT`: tenant request admission window.
- `AI_MONTHLY_COST_LIMIT_USD`: tenant default cost ceiling.
- `AI_MAX_OUTPUT_TOKENS`: hard output ceiling used for admission reservations.
- `AI_MODEL_PRICING_JSON`: deployment-owned Susanoox model pricing catalog.
- `SUSANOOX_AI_KEY`: backend-only provider credential; it must never use a
  `NEXT_PUBLIC_` prefix.

Each pricing entry declares input/output price per million tokens, currency,
and effective date. Missing or invalid entries produce `UNKNOWN`; provider calls
fail closed with `AI_PRICING_UNAVAILABLE` rather than fabricating or recording a
zero cost. Admission reserves the configured maximum output cost before the
request and reconciles it to actual usage after completion.

## Operations and verification

Every request gets a validated/generated `X-Request-ID`, which is returned to
the client and propagated through runs, tools, audits, and supported provider
headers. Tool audit rows contain metadata only and are tenant scoped.

The production verification suite is split between focused unit tests and
`backend/app/tests/integration/test_ai_security_workflow.py`. The integration
suite uses the real FastAPI application, PostgreSQL, sessions/API keys, RBAC,
record scopes, conversation ownership, tenant isolation, and concurrency; only
the external provider boundary is replaced. Deployments should run it against
an isolated PostgreSQL database via `CRM_WORKFLOW_TEST_DATABASE_URL`.
