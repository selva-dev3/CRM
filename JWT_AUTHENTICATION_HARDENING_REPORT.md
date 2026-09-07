# JWT Authentication Hardening Report

## Scope

Implemented in worktree `fix/jwt-auth-hardening` at `/tmp/CRM-jwt-auth-hardening`. No production database, users, tokens, secrets, or environment files were changed.

## Implemented flow

```text
Login/OAuth/Magic link
  -> account and MFA validation
  -> access JWT (sub, iat, exp, jti, token_type, iss, aud)
  -> hashed opaque refresh token in a family
  -> linked access session in PostgreSQL
  -> HttpOnly cookies
  -> strict JWT + session + user + organization + RBAC checks
  -> 401 coordinated refresh
  -> rotate refresh token and create a new linked access session
  -> retry the original request once
  -> logout revokes the family and access session, clears cookies, and broadcasts logout
```

## Main changes

- Removed the email, raw user-id, and `jwt_token_<id>` development authentication bypasses.
- Added strict issuer, audience, required-claim, algorithm, and token-type validation.
- Added cryptographically unique `jti` claims and reduced the default access lifetime to 15 minutes.
- Added refresh-token family IDs, generation numbers, absolute lifetime, revocation timestamps, and replay-triggered family revocation.
- Linked access sessions to refresh families and made session revocation authoritative.
- Added session expiry and last-use metadata, safe cleanup scheduling, and indexes through migration `s3c4d5e6f7a8`.
- Kept refresh tokens and other credentials out of API response bodies; cookies are HttpOnly.
- Added cross-tab refresh coordination through local storage plus `BroadcastChannel`, with one retry per request.
- Changed logout to await backend revocation before reporting success; local state and protected cache are cleared and logout is broadcast.
- WebSockets now authenticate with cookie/header JWTs, reject query-string tokens, validate active sessions/users/organizations/permissions, check revocation during the connection, and broadcast only inside the selected organization.
- OAuth and magic-link authentication now use the same MFA policy; OAuth `email_verified` accepts the provider’s boolean or string representation after normalization.
- Passwords longer than 72 UTF-8 bytes are rejected instead of silently truncated.
- Role updates replace stale role mappings deterministically.
- Deactivation, password changes, and password resets revoke active authentication sessions and refresh records.
- Added backend `.dockerignore` protections and sensitive-value log redaction.

## Verification

Passing checks:

- Focused backend authentication, cookies, WebSockets, roles, users, and migration tests: **161 passed**.
- Frontend Vitest suite: **376 passed across 64 files**.
- Frontend ESLint on changed files: **passed**.
- Python compilation and `git diff --check`: **passed**.
- Alembic graph: one head, `s3c4d5e6f7a8`.

The full backend test command was started but includes environment-dependent integration coverage that waits for external services; it was not used as evidence of a complete production integration pass.

## Configuration

- Access token: 15 minutes by default.
- Refresh rolling lifetime: 30 days by default.
- Refresh absolute lifetime: 30 days by default.
- JWT issuer: `enterprise-crm`.
- JWT audience: `enterprise-crm-api`.
- Production cookie behavior remains Secure, HttpOnly, and SameSite based on the existing environment configuration.

## Production migration

The authorized migration was applied to Render Production `CRM-Postgres` after a read-only preflight.

- Previous Alembic revision: `r1a2b3c4d5e6`
- Applied revision: `s3c4d5e6f7a8`
- Existing `refresh_tokens` rows backfilled: 43
- Verified `user_sessions` rows: 25
- Verified new indexes: 6
- No users, passwords, active sessions, or token records were deleted or revoked.

The production SQL was executed as one transaction matching the checked-in Alembic migration and committed successfully.

## Deployment requirements

1. Ensure production supplies a strong `SECRET_KEY`, database URL, OAuth credentials, and trusted CORS origins through the deployment secret manager.
2. Run the integration and browser tests against staging with PostgreSQL, Redis/Celery, OAuth providers, and the real frontend origin before release.
3. Confirm the Celery beat worker loads `cleanup_expired_auth_records` and monitor refresh replay/session-revocation events.

## Remaining risks

- Existing historical access sessions cannot be retroactively linked to a refresh family because that relationship did not exist before this migration. They expire/revoke under the legacy record state; a controlled, explicitly approved migration can invalidate them if required.
- WebSocket authorization currently uses the `notifications:read` permission for both real-time endpoints; endpoint-specific permissions may be split later if product policy requires it.
- OAuth provider verification still depends on live provider metadata/token validation and therefore requires staging verification with configured provider credentials.
