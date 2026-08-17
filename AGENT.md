# Git / Workflow Rules — Frontend Project

Intha file la project-oda git workflow rules mattum irukku (extracted from
`AGENT.md`).

---

## Git / Workflow Rules

1. Conventional commits: `feat:`, `fix:`, `chore:`, `refactor:`, `test:`,
   `docs:`.
2. No direct pushes to `main` — PR + at least one review.
3. CI must pass: `npm run lint`, `npx tsc --noEmit`, `npm test`,
   `npm run build` before merge.
4. Keep PRs scoped to one feature/fix — large multi-concern PRs are exactly
   what caused the PR #135/#136/#138 conflict mess.

---