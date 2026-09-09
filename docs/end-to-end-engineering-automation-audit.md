# End-to-End Engineering Automation Audit

## Executive summary

The project has substantial application-level automation: Alembic migrations,
Celery schedules, durable delivery/outbox workflows, reconciliation jobs,
security controls, and a large test inventory.

The engineering delivery layer is much less mature. There is no verified CI
quality gate, automated deployment pipeline, complete infrastructure-as-code
baseline, automated backup system, observability platform, incident paging,
release automation, dependency/security scanning, or browser E2E suite.

| Layer | Assessment |
| --- | --- |
| Application workflows | Moderate to strong |
| Testing assets | Strong inventory, weak execution automation |
| CI/CD | Critical gap |
| Security automation | Critical gap |
| Deployment and IaC | Weak |
| Observability and incident response | Critical gap |
| Recovery and rollback | Documented but mostly manual |
| Background processing | Moderate, with reliability gaps |
| Release operations | Missing |
| Production operations | Mostly manual |

## Audit scope and limitations

- Audited the current filesystem on branch `docs/enterprise-rbac-audit` at
  commit `9694c81`. The report was subsequently placed on the dedicated
  documentation branch `docs/engineering-automation-audit`.
- The audited worktree contained extensive uncommitted backend, frontend,
  migration, test, and documentation changes. Findings about those files
  describe local state, not necessarily deployed or remotely committed
  behavior.
- Excluded `.worktrees/`, temporary worktrees, `node_modules`, `.next`, caches,
  and generated artifacts.
- Did not open `.env` files, inspect secrets, connect to databases, call
  providers, run migrations, start containers, execute tests, or inspect live
  GitHub, Vercel, or Render settings.
- Branch protection, GitHub environment rules, deployed health checks,
  provider backups, cloud alerts, and production configuration therefore
  remain externally unverified.
- Historical test results in documentation are not proof that the current
  worktree passes.

## 1. Development Workflow — Partially implemented

### Already implemented

- Frontend commands exist for development, lint, unit tests, build, and start:
  `frontend/package.json:5-10`.
- Backend Ruff, Black, mypy, and pytest settings exist:
  `backend/pyproject.toml:1-25`.
- TypeScript uses strict mode and no-emit checking:
  `frontend/tsconfig.json:3-15`.
- Backend pre-commit hooks cover Ruff, formatting, mypy, merge conflicts,
  large files, EOF, and whitespace: `backend/.pre-commit-config.yaml:1-22`.
- Local development is documented: `README.md:32-48`.

### Partial, missing, and manual

- There is no root-level task runner or single validation command spanning
  frontend and backend.
- Pre-commit configuration is under `backend/`, so installation and use are
  manual and may not cover the frontend.
- The frontend lacks explicit `typecheck`, `test:coverage`, and E2E scripts.
- Backend runtime requirements include `pytest`, while dev tools are also
  listed separately: `backend/requirements.txt:22` and
  `backend/requirements-dev.txt:1-7`.

### Recommendation

Automate a non-mutating root quality command and execute the same commands in
CI. Do not automatically upgrade dependencies or apply formatting directly to
protected branches. Ruff currently uses `--fix`, which can unexpectedly modify
staged files: `backend/.pre-commit-config.yaml:5-7`.

## 2. Git and Branching — Policy present, enforcement unverified

### Already implemented

- Conventional Commits, PR-only changes to `main`, one required review, and
  scoped PRs are documented: `AGENT.md:8-16`.
- Recent repository history generally uses feature/fix branches and
  Conventional Commit messages.

### Partial, missing, and manual

- Many retained local and remote feature/fix branches indicate manual branch
  lifecycle management.
- No executable branch-name check or stale-branch workflow was found.
- Branch protection, signed commits, and required status checks cannot be
  verified from repository files.

### Recommendation

Protect `main`, require CI and human review, require conversation resolution,
and enable deletion of merged branches. Branch deletion, history rewriting,
rebasing shared work, and force-pushing must remain human-approved.

## 3. Pull Requests and Code Review — Partially implemented

### Already implemented

- OpenCode AI review runs for opened, synchronized, reopened, and ready PRs:
  `.github/workflows/opencode-pr-check.yml:3-15`.
- Checkout credentials are not persisted:
  `.github/workflows/opencode-pr-check.yml:17-21`.
- The review covers bugs, security, error handling, style, and repository rules:
  `.github/workflows/opencode-pr-check.yml:31-88`.

### Partial, missing, conflicts, and risks

- The workflow asks for root `AGENTS.md`, but the root policy file is
  `AGENT.md` singular. Root rules may therefore be skipped:
  `.github/workflows/opencode-pr-check.yml:36-40` and `AGENT.md:1`.
- No `CODEOWNERS`, PR template, issue templates, or tracked `SECURITY.md` were
  found.
- The external action is pinned to a version tag rather than an immutable SHA:
  `.github/workflows/opencode-pr-check.yml:24`.
- The job grants `id-token: write`, `issues: write`, and
  `pull-requests: write`; these permissions should be justified and minimized:
  `.github/workflows/opencode-pr-check.yml:11-15`.
- AI review is the only repository-defined PR automation; it does not run or
  verify the application.

### Recommendation

Add required CI quality checks, correct the policy filename, add CODEOWNERS,
and add a PR template with test, migration, security, and rollout sections.
AI review must remain advisory. Merge approval, security risk acceptance,
database changes, and production promotion require humans.

## 4. CI/CD — Critical gap

### Already implemented

- GitHub Actions exists only for AI PR review:
  `.github/workflows/opencode-pr-check.yml:1-88`.

### Completely missing

- Backend lint, formatting check, mypy, unit tests, and integration tests.
- Frontend lint, TypeScript validation, unit tests, and production build.
- Alembic graph, upgrade, and compatibility validation.
- Docker build and image validation.
- Security and dependency scans.
- Browser E2E tests.
- Deployment, staging promotion, smoke tests, or production promotion.
- CI test reports, coverage reports, and build artifacts.

The documented policy says CI must run frontend lint, TypeScript, tests, and
build, but no workflow implements it: `AGENT.md:13-14`.

### Recommendation

Implement, in order: PR validation; isolated PostgreSQL/Redis integration
tests; production builds and Docker build; staging deployment and smoke tests;
then manual production promotion. Production deployments, production
migrations, rollback/cutover, and paid infrastructure must require approval.

## 5. Automated Testing — Strong inventory, weak automation

### Already implemented

- The audited tree contains 78 backend unit-test files, 9 backend integration
  test files, and 67 frontend test files.
- Pytest is configured for `app/tests` with async auto mode:
  `backend/pyproject.toml:22-25`.
- Migration graph tests verify a single Alembic head:
  `backend/app/tests/unit/test_alembic_revision_graph.py:22-25`.
- Vitest uses JSDOM and discovers `src/**/*.test.{ts,tsx}`:
  `frontend/vitest.config.mts:5-17`.
- `pytest-cov` is available as a development dependency:
  `backend/requirements-dev.txt:5-7`.

### Partial, missing, and manual

- Tests are not run in CI.
- No coverage threshold or publication configuration exists.
- No Playwright or Cypress configuration/test suite was found. Playwright
  references in the lockfile are optional/transitive, not a declared E2E
  project.
- No verified load, performance, mutation, visual-regression, or API-schema
  compatibility suite exists.
- Some current RBAC migration tests are untracked local files and are not part
  of the committed baseline.

Historical reports are not current validation. For example,
`docs/CRM_AUTOMATED_WORKFLOW_IMPLEMENTATION.md:50-59` records a frontend test
failure and missing browser/full-suite execution, while
`docs/organization-lifecycle-implementation-report.md:80-91` records
pre-existing full-suite failures and no browser/production verification.

### Recommendation

Automate fast PR unit tests, isolated backend integration tests, frontend
type/build checks, and critical browser flows: authentication, tenant
isolation, lead-to-deal, quote/invoice/payment, and organization switching.
Snapshot updates, flaky-test quarantine, and threshold reductions require
human review.

## 6. DevSecOps and Security — Application controls present, pipeline missing

### Already implemented

- JWT issuer, audience, expiry, JTI, token type, secure randomness, and bcrypt:
  `backend/app/core/security.py:11-54`.
- HttpOnly, environment-sensitive secure cookies:
  `backend/app/core/auth_cookies.py:6-47`.
- Origin validation for unsafe cookie-authenticated requests:
  `backend/app/main.py:78-106`.
- Authentication and invitation rate limits:
  `backend/app/core/rate_limiter.py:9-27`.
- API key hashing, expiration, owner, organization, and scope checks:
  `backend/app/api/v1/deps.py:43-84`.
- Organization-context and permission enforcement:
  `backend/app/api/v1/deps.py:147-239`.
- Credential-oriented log redaction:
  `backend/app/core/logging.py:17-31`.
- Environment files and key/certificate files are excluded:
  `.gitignore:20-25` and `backend/.dockerignore:1-5`.

### Completely missing

- CodeQL or other SAST.
- Secret scanning workflow.
- Python/npm dependency vulnerability scanning.
- Container scanning, SBOM creation, and artifact signing.
- DAST and automated license checks.
- Dependabot or Renovate.
- Tracked security disclosure policy.

### Risks and recommendation

- Most backend dependencies use open-ended `>=` constraints, making image
  builds non-reproducible: `backend/requirements.txt:1-22`.
- In-memory rate-limit fallback can conceal Redis failure and be inconsistent
  across processes: `backend/app/core/rate_limiter.py:21-27`.
- Current RBAC hardening includes uncommitted files and may not match deployed
  code.

Automate secret, dependency, SAST, and image scanning first. Patch-update PRs
may be automated, but major dependency upgrades and risk acceptance require
human review.

## 7. Docker and Containers — Partially implemented

### Already implemented

- A multi-stage backend image exists: `backend/Dockerfile:1-33`.
- Compose defines PostgreSQL, Redis, MinIO, backend, Celery worker, and beat:
  `docker-compose.yml:1-152`.
- PostgreSQL, Redis, and MinIO have health checks:
  `docker-compose.yml:14-18`, `28-32`, and `49-53`.
- Named volumes and an internal bridge network exist:
  `docker-compose.yml:154-160`.
- Tests and secrets are excluded from the production build context:
  `backend/.dockerignore:1-13`.

### Partial, missing, conflicts, and risks

- No frontend Dockerfile exists.
- Backend, Celery worker, and beat have no health checks.
- The runtime does not use a non-root user.
- Base and service images are not digest-pinned.
- No container build/scanning workflow or production resource limits exist.
- Docker uses Python 3.11 while local tooling targets Python 3.12:
  `backend/Dockerfile:2,19` and `backend/pyproject.toml:3,7,16`.
- MinIO and MinIO client use floating `latest` tags:
  `docker-compose.yml:37,58`.
- Web startup runs migrations, creating concurrent rollout risk:
  `backend/Dockerfile:33`.
- Compose exposes database, Redis, and MinIO ports and provides development
  credential defaults; it is a development configuration:
  `docker-compose.yml:6-11,22-27,36-46,82-91`.

### Recommendation

Align runtime/tooling versions, pin images, use a non-root runtime, validate
the image in CI, add image scanning, and add explicit service health checks.

## 8. Database Automation — Strong assets, unsafe orchestration

### Already implemented

- The audited tree contains 71 Alembic migration files.
- Alembic supports online and offline migration modes:
  `backend/alembic/env.py:17-43`.
- A migration graph test enforces one head:
  `backend/app/tests/unit/test_alembic_revision_graph.py:22-25`.
- Migration-specific unit and integration tests exist under
  `backend/app/tests/`.
- Controlled RBAC cleanup includes target/database guards, snapshot checks,
  lock and statement timeouts, dry-run rollback, and verification:
  `backend/scripts/cleanup_render_rbac.py:125-160,233-242`.
- Organization deletion defaults disabled pending recovery readiness:
  `backend/app/core/config.py:57-59`.

### Duplicate and conflicting automation

Three paths can initialize or mutate database state:

1. The web container executes `alembic upgrade head`:
   `backend/Dockerfile:33`.
2. Development startup executes `Base.metadata.create_all`:
   `backend/app/main.py:31-40`.
3. Every application startup seeds permissions and synchronizes roles:
   `backend/app/main.py:42-58`.

This can cause migration races, schema drift, startup delays, and state changes
during horizontal scaling.

### Missing and recommendation

Missing: a serialized migration release job, CI migration compatibility tests,
schema-drift detection, an automated backup provider, and restore drills.

Move migrations to a single release phase and validate graph/upgrades in CI.
Production migrations, destructive cleanup, forward-only changes, restore, and
cutover must require human approval.

## 9. Infrastructure and Deployment — Mostly missing

### Already implemented

- A review-only Render blueprint describes a dedicated organization cleanup
  worker and scheduler: `deploy/render-organization-workers.yaml:1-55`.
- Auto-deployment is disabled and secrets are external inputs:
  `deploy/render-organization-workers.yaml:15-16,25-42,54-55`.

### Partial, missing, and manual

- Source/defaults suggest Vercel for the frontend and Render for the backend,
  but the full deployed topology is not represented in source.
- The Render file covers only cleanup workers, not the web service, regular
  workers, database, Redis, storage, DNS, or frontend.
- No Terraform, Pulumi, CloudFormation, Kubernetes, Helm, or equivalent IaC
  was found.
- No staging/production topology, deployment workflow, drift detection, smoke
  test, or disaster-recovery infrastructure definition exists.

### Recommendation

First inventory live infrastructure, then encode non-secret service
definitions. Build staging and smoke verification before production delivery.
Paid resources, region, scaling, DNS, database plans, production deployment,
and destructive infrastructure plans require approval.

## 10. Environment Management — Partially implemented

### Already implemented

- Central Pydantic settings require `SECRET_KEY` and `DATABASE_URL`:
  `backend/app/core/config.py:26-29,50-64`.
- Cookie security and rate-limit storage vary by environment:
  `backend/app/core/config.py:167-184`.
- Dotenv can be disabled for production execution:
  `backend/app/core/config.py:186-189`.
- Backend and frontend `.env.example` files exist.
- The Render blueprint uses `CRM_DISABLE_DOTENV=1` and external secret values:
  `deploy/render-organization-workers.yaml:16-42`.
- Frontend production configuration rejects missing `NEXT_PUBLIC_API_URL`:
  `frontend/src/lib/api/client.ts:4-20`.

### Partial, risks, and recommendation

- No CI validation ensures examples and settings remain synchronized.
- No environment promotion matrix or complete secret-manager definition exists.
- `ENVIRONMENT` defaults to development and CORS/frontend defaults mix deployed
  and localhost URLs: `backend/app/core/config.py:139-145`.
- Compose always sets development mode and reads `backend/.env`:
  `docker-compose.yml:80-85`.

Automate variable-name/type validation without printing values. Define separate
development, test, staging, and production contracts and protect production
configuration with approval gates.

## 11. Release Management — Missing

### Already implemented

- Conventional Commit policy exists: `AGENT.md:10-11`.
- Backend API version is hard-coded as `1.0.0`:
  `backend/app/main.py:65-69`.
- Frontend package version is `0.1.0`: `frontend/package.json:3`.

### Missing and conflict

- No Git tags, changelog, semantic release, release notes, GitHub Release,
  provenance, release artifact workflow, or documented hotfix process exists.
- Backend and frontend versions have no shared release source of truth.

### Recommendation

Choose monorepo or independent versioning, build immutable artifacts tied to a
commit SHA, and generate draft release notes. Publishing and production
promotion must remain human-approved.

## 12. Monitoring and Observability — Minimal

### Already implemented

- Central logging and credential redaction:
  `backend/app/core/logging.py:17-53`.
- Log format includes a request ID field:
  `backend/app/core/logging.py:8-14,34-45`.
- `/health` checks database connectivity:
  `backend/app/main.py:136-148`.
- Selected provider flows log safe provider request identifiers, for example
  `backend/app/services/ai_provider_service.py:105-126`.

### Partial and missing

- No middleware was found that generates or propagates application request IDs;
  the filter defaults them to `-`.
- Logs are plain text rather than structured JSON.
- Liveness and readiness are not separated.
- Redis, storage, Celery worker, beat, queue, and providers are not included in
  readiness.
- No metrics, tracing, error tracking, dashboards, SLOs, frontend telemetry,
  queue-depth monitoring, or task-latency monitoring exists.

### Recommendation

Add structured logs with real correlation IDs, error tracking, HTTP/database/
Celery/provider metrics, and separate liveness/readiness endpoints.

## 13. Incident Detection and Alerting — Missing

### Existing functionality that is not operational alerting

- CRM users can receive notifications and manually broadcast system alerts:
  `backend/app/api/v1/routers/notifications.py:110-128`.
- WebSocket notification subscriptions validate session, organization, and
  permission state: `backend/app/api/v1/routers/websockets.py:80-107,179-186`.

### Gaps and risks

- Notification preferences and WebPush registration return fixed success
  responses without persistence:
  `backend/app/services/notification_service.py:303-327`.
- System-alert persistence failure rolls back but still returns success:
  `backend/app/services/notification_service.py:329-359`.
- No monitoring webhook, PagerDuty, Opsgenie, on-call rotation, escalation
  policy, or alert-threshold configuration exists.

### Recommendation

Alert on availability, 5xx rate, latency, failed migrations, queue backlog,
terminal deliveries, reconciliation failures, and backup failures. Customer
communications, incident declaration/resolution, and disabling major features
must require humans unless an approved runbook explicitly permits the action.

## 14. Auto Recovery and Rollback — Domain recovery exists, platform rollback missing

### Already implemented

- Transaction rollback is used throughout service operations.
- Durable claims and bounded retries exist for multiple workflows:
  `backend/app/workers/tasks.py:13-14,212-243`.
- Organization deletion is disabled by default:
  `backend/app/core/config.py:57-59`.
- A detailed manual backup, restore, staging, and cutover procedure exists:
  `docs/organization-lifecycle-operations.md:84-126`.

### Missing

- Automated deployment rollback, blue/green or canary delivery, health-based
  traffic rollback, verified restore automation, partial-tenant restoration,
  worker failover, and defined RTO/RPO.
- Backup listing returns an empty list and manual backup returns
  `501 BACKUP_PROVIDER_NOT_CONFIGURED`:
  `backend/app/services/settings_service.py:373-381`.

### Recommendation

Implement managed backups and restore drills before automatic rollback.
Database restore, traffic cutover, rollback after schema changes, and actions
that can discard post-backup writes require human approval.

## 15. AI-Assisted Engineering — One useful automation, otherwise missing

### Already implemented

- OpenCode performs automated PR review:
  `.github/workflows/opencode-pr-check.yml:23-88`.
- Product AI has enablement, subscription, and monthly cost gates:
  `backend/app/services/ai_runtime_service.py:73-114`.
- Product AI exposes usage and cost-limit information:
  `backend/app/services/ai_domain_service.py:1618-1626`.

### Partial and missing

- AI review lacks test/build evidence and may skip the root policy due to the
  filename mismatch.
- No AI issue classification, failure summarization, test-gap analysis,
  verified release-note drafting, incident analysis, or dependency-risk
  summary automation exists.

### Safe automation boundary

AI may propose reviews, tests, summaries, and release drafts. It must not
auto-merge, approve its own changes, apply migrations, rotate secrets, deploy
production, or resolve incidents without human approval.

## 16. Documentation Automation — Documentation exists, automation missing

### Already implemented

- Architecture and local development are documented: `README.md:1-55`.
- Detailed workflow, RBAC, billing, production-hardening, and organization
  lifecycle reports exist under `docs/`.
- FastAPI exposes runtime OpenAPI: `backend/app/main.py:65-70`.

### Partial, conflicts, and missing

- Documentation is maintained manually.
- README says Next.js 15 while the package uses Next.js 16.2.12:
  `README.md:3` and `frontend/package.json:25`.
- Frontend README remains mostly create-next-app boilerplate:
  `frontend/README.md:1-36`.
- Historical branch/worktree verification reports can become stale.
- No Markdown lint, link check, OpenAPI export/diff, configuration reference
  generation, changelog automation, documentation deployment, or ownership/
  staleness check exists.

### Recommendation

Automate Markdown/link checks, API/configuration references, and documented
version/command validation. Architecture decisions, security guidance, and
postmortems require human review.

## 17. Team Workflow Automation — Mostly manual

### Already implemented

- Root, backend, and frontend development rules are documented:
  `AGENT.md`, `backend/AGENTS.md`, and `frontend/AGENTS.md`.

### Missing

- CODEOWNERS, PR/issue templates, reviewer assignment, automatic labels,
  milestone/project-board automation, migration/security/rollout checklists,
  and dependency ownership.

### Recommendation

Add ownership and templates, route reviews based on changed areas, and report
stale work. PR approval, customer-impacting issue closure, risk acceptance, and
ownership changes remain human decisions.

## 18. Cloud Cost Optimization — Narrow AI control only

### Already implemented

- Global and per-organization AI cost controls exist:
  `backend/app/core/config.py:104-138` and
  `backend/app/services/ai_runtime_service.py:91-102`.
- AI usage and credit information is exposed:
  `backend/app/services/ai_domain_service.py:1618-1626`.
- The Render worker blueprint disables auto-deployment and calls out paid
  resource approval: `deploy/render-organization-workers.yaml:1-15`.

### Missing

- Cloud budgets, anomaly alerts, allocation tags, infrastructure cost
  estimation, storage lifecycle rules, database/Redis right-sizing,
  autoscaling policy, idle-resource detection, and log/backup retention cost
  controls.

### Recommendation

Start with budget alerts, tagging, and weekly anomaly reports. Collect queue
and capacity metrics before autoscaling. Downsizing, retention reduction,
provider changes, and paid scaling require approval.

## 19. Background Jobs and Data Workflows — Partially strong

### Already implemented

- Celery uses Redis and JSON serialization:
  `backend/app/workers/celery_app.py:6-17`.
- Beat schedules cleanup, email, report, quote, invoice, receipt, integration,
  reminder, payment, and subscription jobs:
  `backend/app/workers/celery_app.py:19-66`.
- Organization cleanup uses a dedicated queue and cleanup-only scheduling:
  `backend/app/workers/celery_app.py:25-28,68-72`.
- Durable claims, idempotency keys, retry schedules, and terminal states exist
  for integration and email workflows:
  `backend/alembic/versions/q0f1a2b3c4d5_integration_delivery_outbox.py:24-51`
  and `backend/alembic/versions/l5a6b7c8d9e0_truthful_email_outbox.py:18-83`.
- Integration delivery has bounded attempts and exponential backoff:
  `backend/app/workers/tasks.py:13-14,212-243`.

### Partial, missing, and risks

- No global `acks_late`, reject-on-worker-lost, task time limits, prefetch
  control, visibility timeout, or broker retry settings were found.
- No dead-letter queue, queue dashboard, backlog/oldest-message alert,
  terminal-failure alert, or scheduler-staleness alert exists.
- Many jobs create a new database engine per invocation, for example
  `backend/app/workers/tasks.py:23-46`.
- Compose workers have no health checks:
  `docker-compose.yml:106-152`.
- Production cleanup workers are represented only by a review-only blueprint.

### Recommendation

Add worker/beat heartbeat monitoring, backlog and failure alerts, explicit
reliability settings per task class, and an audited dead-letter/replay process.
Financial/provider jobs with uncertain outcomes, unknown email/payment states,
dead-letter purges, and destructive cleanup must require approval.

## 20. Production Operations — Mostly manual

### Already implemented

- Database-aware health endpoint: `backend/app/main.py:136-148`.
- RBAC startup synchronization failure propagates rather than silently
  continuing: `backend/app/main.py:42-58`.
- Local services use restart policies: `docker-compose.yml:5,25,39,77,111,135`.
- Operations documentation defines controlled backup, worker readiness,
  staging-first migration, and recovery gates:
  `docs/organization-lifecycle-operations.md:90-126`.

### Missing and risks

- No ordinary deployment runbook, incident runbook, SLO/error budget, on-call
  ownership, automated backup/restore, deployment smoke test, operational
  dashboard, capacity plan, certificate/domain monitoring, retention
  automation, automated rollback, or proven staging environment.
- Every web start may run migrations and RBAC synchronization.
- Health does not cover Redis, workers, beat, queues, or object storage.
- Notification failures can be hidden by success responses:
  `backend/app/services/notification_service.py:329-359`.

### Recommendation

Prioritize observability and alerts, backup/restore proof, serialized delivery,
staging smoke tests, and manual production promotion with automated post-deploy
verification.

## Duplicate and conflicting automation systems

| Conflict | Evidence | Risk |
| --- | --- | --- |
| Alembic on web startup, development `create_all`, and startup RBAC synchronization | `backend/Dockerfile:33`; `backend/app/main.py:31-58` | Migration races, schema drift, startup mutation |
| Python 3.11 runtime versus Python 3.12 tooling | `backend/Dockerfile:2,19`; `backend/pyproject.toml:3,7,16` | Local/CI checks may not match production |
| Documented CI requirement versus no quality workflow | `AGENT.md:13-14`; `.github/workflows/opencode-pr-check.yml` | Untested code can merge |
| AI workflow expects root `AGENTS.md`, while root file is `AGENT.md` | `.github/workflows/opencode-pr-check.yml:36-40`; `AGENT.md:1` | Repository rules may be skipped |
| Independent hard-coded backend/frontend versions | `backend/app/main.py:68`; `frontend/package.json:3` | Release traceability failure |
| Business system alerts appear operational but are manual and partly stubbed | `backend/app/services/notification_service.py:303-359` | False sense of incident coverage |

## Final classification

### 1. Already Implemented

- Local lint, type, test, and build tooling.
- Conventional Commit and PR policies.
- AI PR review.
- Large backend/frontend test inventory.
- Alembic migrations and graph testing.
- Backend container and local Compose environment.
- JWT, cookies, origin protection, rate limiting, RBAC, and tenant controls.
- Celery schedules, durable outboxes, claims, idempotency, and reconciliation.
- Basic database health endpoint.
- AI usage and cost limits.
- Detailed operational and recovery documentation.

### 2. Partially Implemented

- Development workflow standardization.
- Branching and review enforcement.
- Automated testing.
- Container production hardening.
- Environment management.
- Database deployment process.
- Infrastructure definitions.
- Logging and request correlation.
- Recovery processes.
- Team workflow, cost management, background reliability, and production ops.

### 3. Missing

- Real CI/CD and browser E2E.
- SAST, dependency, secret, and container scanning.
- Complete IaC.
- Automated backups and restore drills.
- Release/version/changelog automation.
- Metrics, tracing, error tracking, dashboards, and SLOs.
- Incident paging and escalation.
- Automated deployment rollback.
- CODEOWNERS and PR/issue templates.
- Cloud budget/anomaly alerts.
- Queue monitoring and dead-letter operations.

### 4. Manual Processes

- Full quality validation and PR risk review.
- Reviewer assignment and branch cleanup.
- Environment verification.
- Deployment and migration execution.
- Backup, restore, rollback, and cutover.
- Worker provisioning.
- Release notes and versioning.
- Production smoke tests.
- Incident detection and communication.
- Cost review and failed-job replay.

### 5. Recommended Automations

1. PR CI quality gate.
2. Secret, dependency, SAST, and image scanning.
3. Serialized migration validation.
4. Structured observability and alerts.
5. Automated backups and restore verification.
6. Staging deployment and E2E smoke suite.
7. Immutable release artifacts and release notes.
8. Manual-gated production promotion.
9. Queue reliability and dead-letter tooling.
10. Cost and capacity anomaly reporting.

### 6. Priority

| Priority | Work |
| --- | --- |
| Critical | CI gate, security scans, backup/restore, observability, incident alerts, serialized migrations |
| High | Staging, browser E2E, Docker hardening, worker monitoring, release traceability |
| Medium | CODEOWNERS/templates, documentation generation, dependency PRs, cost alerts |
| Low | Branch cleanup reporting, advanced AI summaries, visual regression, workflow labeling |

### 7. Dependencies between automations

```text
Reproducible toolchain
  -> PR CI
    -> security, migration, and build gates
      -> immutable artifacts
        -> staging deployment
          -> E2E and smoke tests
            -> manual production promotion
              -> post-deploy verification
                -> automated rollback eligibility

Structured telemetry
  -> dashboards and SLOs
    -> actionable alerts
      -> incident runbooks
        -> safe recovery automation

Backup provider
  -> scheduled backups
    -> isolated restore drill
      -> measured RPO/RTO
        -> approved migration and destructive-operation automation
```

### 8. Recommended implementation order

1. Establish a clean committed baseline; the current local changes make
   automation results ambiguous.
2. Align Python/runtime versions and dependency reproducibility.
3. Add frontend/backend PR CI.
4. Add security scanning.
5. Validate Alembic graph and isolated upgrades in CI.
6. Build immutable backend/frontend artifacts.
7. Implement structured logs, request IDs, metrics, and error tracking.
8. Add service, queue, reconciliation, and backup alerts.
9. Configure a backup provider and perform restore drills.
10. Create staging from reviewed infrastructure definitions.
11. Add critical browser E2E and deployment smoke tests.
12. Add release automation and manual-gated production promotion.
13. Add rollback/canary support only after health signals are trustworthy.
14. Add cost, capacity, and dependency-maintenance automation.

### 9. Potential risks

- CI may initially expose existing failures.
- Integration tests may require isolation work before becoming reliable.
- Moving migrations out of web startup changes deployment ordering.
- Startup RBAC mutation may conflict with migration ownership.
- Floating dependencies and images make failures non-reproducible.
- Automatic retries can duplicate email, webhook, or payment effects.
- False-success notifications can conceal operational failures.
- Automatic rollback after forward-only migrations can break compatibility.
- Incomplete telemetry could trigger unsafe automated recovery.
- The dirty worktree may differ significantly from committed or deployed code.
- Historical reports may be mistaken for current validation.
- Infrastructure automation may create paid resources or alter production
  without plan and approval gates.

### 10. Final production-ready automation roadmap

#### Phase 1 — Quality and security foundation

- Reproducible versions and dependency locking.
- Backend/frontend PR checks.
- Migration graph validation.
- Secret, dependency, SAST, and image scans.
- Required branch checks and human review.

Exit criterion: every PR produces repeatable lint, type, test, build,
migration, and security results.

#### Phase 2 — Operational visibility

- Structured logs and real request IDs.
- Error tracking and frontend telemetry.
- HTTP, database, worker, queue, and provider metrics.
- SLOs, dashboards, and actionable alerts.

Exit criterion: failures can be detected, correlated, assigned, and measured.

#### Phase 3 — Recovery readiness

- Managed database and object-storage backups.
- Automated backup-integrity checks.
- Isolated restore drills and measured RPO/RTO.
- Approved incident and recovery runbooks.

Exit criterion: recovery is demonstrated rather than merely documented.

#### Phase 4 — Safe delivery

- Complete infrastructure inventory and reviewed IaC.
- Immutable artifacts and serialized migrations.
- Automated staging deployment.
- Browser E2E and smoke tests.
- Manual production promotion.

Exit criterion: the exact tested artifact is promoted with auditability.

#### Phase 5 — Controlled resilience

- Health-based canary or blue/green delivery.
- Automatic rollback only for application-compatible failures.
- Queue dead-letter and audited replay operations.
- Capacity and cost anomaly detection.
- Automated dependency maintenance with human merge approval.

Exit criterion: routine failures recover safely while database, financial,
destructive, security, and production decisions remain human-controlled.
