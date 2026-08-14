# Frontend Project Rules — Next.js + Tailwind + TanStack Query + Zustand + shadcn/ui

Intha rules follow pannina, project consistent ah, scalable ah, and future-la
oru new dev join pannalum easy ah puriyura maadhiri irukkum.

---

## 1. Project Structure

```
src/
  app/                    # Next.js App Router — routes only, no business logic
    (auth)/
    (dashboard)/
    api/                  # route handlers (only if you truly need server routes)
    layout.tsx
    globals.css
  components/
    ui/                   # shadcn/ui generated components — don't hand-edit heavily
    common/                # shared, dumb/presentational components
    features/<feature>/    # feature-scoped components
  lib/
    api/
      client.ts            # axios/fetch instance
      queries/              # TanStack Query hooks, grouped by domain
        payroll-api.ts
        employees-api.ts
    utils.ts                # cn(), formatters, etc.
    validators/              # zod schemas
    types/                    # shared TS types / DTOs
  store/                        # Zustand stores, one file per slice/domain
    ui-store.ts
    auth-store.ts
  hooks/                          # custom hooks not tied to query/store
  constants/
```

**Rule:** `app/` folder only holds routing + page composition. No fetch logic,
no Zustand store definitions, no business logic inside `page.tsx` — pull it
into `components/features/*` and `lib/`.

---

## 2. Next.js (App Router) Rules

1. **Server Components by default.** Only add `"use client"` when the
   component actually needs state, effects, browser APIs, or a hook
   (`useState`, TanStack Query, Zustand, event handlers).
2. Keep client boundaries **small and pushed down** — don't mark a whole page
   `"use client"` just because one button needs an `onClick`.
3. Data that can be fetched on the server (initial page data) → fetch in a
   Server Component and pass down, or **hydrate TanStack Query** with
   `HydrationBoundary` for anything the client will also refetch/mutate.
4. Use `loading.tsx`, `error.tsx`, `not-found.tsx` per route segment — don't
   hand-roll spinners/error boundaries inside every page.
5. Route groups `(group-name)` for layout separation (auth vs dashboard),
   not for organization-only purposes.
6. Server Actions only for simple mutations tightly coupled to a form; for
   anything that needs caching, retries, optimistic UI, or is called from
   multiple places — use a TanStack Query mutation hook against an API route
   instead.
7. Environment variables: `NEXT_PUBLIC_*` only for values safe to expose to
   the browser. Never put secrets in client components.
8. Metadata via the `metadata` export / `generateMetadata`, not manual
   `<head>` tags.

---

## 3. TypeScript Rules

1. `strict: true` in `tsconfig.json` — no exceptions.
2. No `any`. Use `unknown` + narrowing, or generate/derive proper types.
3. Every API response gets a typed DTO in `lib/types/`. Don't inline
   `{ id: string; name: string }` shapes across multiple files — one source
   of truth per entity.
4. Prefer `type` for unions/props, `interface` for extendable object shapes —
   pick one convention and stay consistent per file group.
5. Don't use non-null assertions (`!`) to silence errors — fix the actual
   narrowing, or default the value properly.

---

## 4. Tailwind CSS Rules

1. Use the **`cn()` utility** (`clsx` + `tailwind-merge`) for all conditional
   classNames — never string-concatenate classes manually.
2. Design tokens (colors, spacing, radii, fonts) live in `tailwind.config.ts`
   / CSS variables — no arbitrary hard-coded hex values (`bg-[#3b82f6]`)
   sprinkled through components.
3. No inline `style={{}}` unless it's a computed/dynamic value (e.g. a chart
   bar height) that genuinely can't be a class.
4. Keep component-level className strings readable — extract to a `const
   styles = {...}` object or use `class-variance-authority (cva)` once a
   component has more than ~3 conditional variants.
5. Mobile-first: write base classes for mobile, add `sm:`/`md:`/`lg:` for
   larger breakpoints — never the reverse.
6. Don't fight shadcn/ui's default styling with `!important` overrides —
   extend via `cva` variants or Tailwind config instead.
7. Global CSS (`globals.css`) only for resets, CSS variables, and truly
   global rules — component-specific styling stays in the component via
   Tailwind classes.

---

## 5. shadcn/ui Rules

1. Install components via the CLI (`npx shadcn add <component>`) — don't
   hand-copy component code from the docs; this keeps them upgradeable.
2. Generated files under `components/ui/` are the **base primitives** — treat
   them as a design-system layer. Compose feature components on top of them
   in `components/features/`, don't keep editing `ui/button.tsx` per feature
   need.
3. If a shadcn primitive needs a genuinely new variant, extend it with `cva`
   inside `components/ui/<component>.tsx` itself, so the variant is reusable
   everywhere, not duplicated per usage site.
4. Use shadcn's `Form` (built on `react-hook-form` + `zod`) for all forms —
   don't hand-roll form state with `useState` per field.
5. Consistent use of `Toast`/`Sonner`, `Dialog`, `Sheet` from shadcn for all
   notifications/modals — no mixing with a second UI library for the same
   purpose.

---

## 5a. Most-Used shadcn/ui Components (Install These First)

Standard set to install upfront for any new project (`npx shadcn add
<name>`) — covers ~90% of typical admin/dashboard/product UI needs:

**Layout & Structure**
- `card` — content containers, dashboard panels
- `separator` — dividers
- `tabs` — sectioned views
- `accordion` — collapsible sections
- `sheet` — slide-over panel (mobile-friendly modal alternative)
- `scroll-area` — custom scrollable regions

**Forms & Inputs**
- `form` — react-hook-form + zod wrapper (use for every form, §8)
- `input`
- `textarea`
- `select`
- `checkbox`
- `radio-group`
- `switch`
- `label`
- `input-otp` — OTP/verification code input
- `date-picker` (built from `calendar` + `popover`)
- `combobox` (built from `command` + `popover`) — searchable select

**Overlays & Feedback**
- `dialog` — modal confirmations/forms
- `alert-dialog` — destructive-action confirmations (delete, etc.)
- `dropdown-menu` — action menus, row menus
- `popover`
- `tooltip`
- `toast` / `sonner` — notifications (pick one, stay consistent — §10)
- `alert` — inline banners (info/warning/error)
- `skeleton` — loading placeholders

**Data Display**
- `table` — paired with `@tanstack/react-table` for sorting/filtering/pagination
- `badge` — status/tag labels
- `avatar`
- `progress`

**Navigation**
- `button`
- `navigation-menu` / `menubar` — top nav
- `breadcrumb`
- `pagination`
- `command` — command palette / searchable lists

**Rule:** install only what a feature actually needs at that time, but the
list above is the default "starter set" for a new project — install these
early so components aren't hand-copied later out of habit. Always via the
CLI (§5.1), never copy-pasted from docs manually.

---

## 6. TanStack Query Rules

1. **One hook per query/mutation**, grouped by domain in `lib/api/queries/`
   (e.g. `payroll-api.ts` exports `usePayrollItems()`,
   `useUpdatePayrollItem()`). Components never call `useQuery`/`useMutation`
   directly inline with a raw fetch — always through a named hook.
2. **Query keys are centralized** per domain as a `const` factory
   (e.g. `payrollKeys.items(filters)`), never hand-typed arrays scattered
   across files — this prevents silent cache-key mismatches.
3. Use `enabled` to gate queries that depend on other state (wizard steps,
   selected IDs, open dialogs) — don't fetch-then-discard.
4. On mutation success:
   - Prefer **direct cache writes** (`queryClient.setQueryData`) with the
     server's authoritative response over blanket `invalidateQueries`,
     especially for hot paths (e.g. editing one row in a list).
   - When you do invalidate, invalidate the **narrowest key** possible —
     never invalidate a whole top-level key (`['settings']`) when only one
     sub-resource changed.
5. Always handle `isPending` / `isError` states in the UI — no silent
   failures. Use shadcn `Toast`/`Sonner` for mutation error feedback.
6. Set sane defaults in `QueryClient` (`staleTime`, `retry`) once, globally,
   not per-hook unless a specific query needs an override.
7. Don't store server data in Zustand. If it came from an API, it lives in
   the Query cache — Zustand is for client-only/UI state (see next section).

---

## 7. Zustand Rules

1. Zustand stores hold **client/UI state only**: modal open/close, wizard
   step, selected filters/tab, theme, sidebar collapsed, etc. — never server
   data (that's TanStack Query's job).
2. One store per concern (`ui-store.ts`, `auth-store.ts`) — avoid one giant
   global store with everything mixed in.
3. Use **selectors** when reading from a store in a component
   (`useUiStore((s) => s.sidebarOpen)`), not the whole store object, to avoid
   unnecessary re-renders.
4. Co-locate actions with state inside the store definition (`set`
   functions), not scattered `useEffect`-driven mutations from components.
5. Persist only what genuinely needs to survive a refresh (`persist`
   middleware for things like sidebar preference/theme) — don't persist
   transient UI state like "is this dialog open."
6. No business logic inside store actions beyond simple state transitions —
   if it needs an API call, that's a Query mutation, and the store just
   reflects UI state around it (e.g. `isDialogOpen`).

---

## 8. Forms & Validation

1. `zod` schema is the single source of truth for a form's shape — infer the
   TypeScript type from the schema (`z.infer<typeof schema>`), don't hand
   write a duplicate interface.
2. `react-hook-form` + shadcn `Form` components for every form, no exceptions.
3. Validate on both client (immediate UX) and rely on the backend as the
   final authority — never trust client validation alone for correctness.

---

## 9. Naming Conventions

- Components: `PascalCase.tsx` (`PayrollItemEditDialog.tsx`)
- Hooks: `useCamelCase.ts` (`usePayrollItems.ts`)
- Stores: `kebab-case-store.ts` (`ui-store.ts`)
- Query key factories: `camelCaseKeys` (`payrollKeys`)
- Types/DTOs: `PascalCase`, suffix `Dto` for API shapes
  (`PayrollControlSettingsDto`)
- Folders: `kebab-case`

---

## 10. Error Handling

1. One centralized API error mapper (maps backend error codes → field-level
   form errors), reused across all mutation hooks — don't re-implement error
   mapping per component.
2. Network/unexpected errors → shadcn `Toast`. Field-level validation errors
   → inline under the relevant form field, not a toast.
3. Use route-level `error.tsx` for unexpected render-time errors, not
   try/catch around JSX.

---

## 11. Performance Rules

1. Lazy-load heavy, rarely-opened UI (large sheets, wizards, charts) with
   `next/dynamic`.
2. Memoize expensive derived data with `useMemo`, but don't over-memoize
   trivial computations.
3. Avoid prop-drilling more than 2–3 levels — use composition, context, or
   (for pure UI state) Zustand instead.
4. Virtualize long lists/tables (`@tanstack/react-virtual`) once row count
   is large enough to matter.

---

## 12. Testing Rules

1. Every custom Query hook and Zustand store gets unit tests.
2. Every form gets a test proving: valid submit succeeds, invalid input
   blocks submit with the right error, server error maps to the right field.
3. Cache-behavior tests (does a mutation update the cache without a refetch?)
   for any hook that does manual `setQueryData`.

---

## 13. Responsiveness Rules (All Devices)

1. **Mobile-first always.** Write base (no-prefix) Tailwind classes for the
   smallest screen, then layer `sm: md: lg: xl: 2xl:` upward. Never design
   desktop-first and squeeze it down.
2. Target breakpoints minimum: mobile (`< 640px`), tablet (`640–1024px`),
   laptop (`1024–1280px`), desktop (`> 1280px`). Test all four before calling
   a component done.
3. No fixed pixel widths on containers/cards — use `w-full`, `max-w-*`,
   `flex`/`grid` with `gap-*`, so layout adapts naturally.
4. Use `flex-col md:flex-row` (or `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`)
   patterns for layouts that reflow instead of shrink/overflow.
5. Tables: on mobile, either horizontal-scroll inside a wrapper
   (`overflow-x-auto`) or switch to a stacked card view — never let a wide
   table break the page layout.
6. Dialogs/Sheets: use shadcn `Sheet` (slide-over) on mobile where a `Dialog`
   would be too cramped; pick based on viewport, not one-size-fits-all.
7. Touch targets minimum `44x44px` on interactive elements for mobile.
8. Font sizes and spacing scale via Tailwind's responsive prefixes
   (`text-sm md:text-base lg:text-lg`) — don't ship one fixed size for every
   screen.
9. Every new component/page must be manually checked at mobile, tablet, and
   desktop widths (browser dev tools or real device) before it's marked done.

---

## 14. Performance & Optimization Rules

1. **Images:** always `next/image`, never a raw `<img>` — gives automatic
   lazy loading, resizing, and format optimization (WebP/AVIF).
2. **Fonts:** load via `next/font` (local or Google), never a manual
   `<link>` tag — avoids layout shift and extra network waterfalls.
3. **Code-splitting:** lazy-load heavy/rare UI (wizards, charts, large
   sheets, admin-only panels) with `next/dynamic` and `ssr: false` where the
   component is client-only and non-critical for first paint.
4. **Bundle discipline:** don't import a whole library for one function
   (e.g. import a single `lodash` function, not the entire package). Check
   bundle impact with `@next/bundle-analyzer` before adding a new dependency.
5. **TanStack Query caching:** set sensible `staleTime`/`gcTime` so the same
   data isn't refetched on every navigation; prefetch on hover/route-intent
   for pages the user is likely to visit next.
6. **Avoid re-renders:** use Zustand selectors (not whole-store reads),
   `React.memo` for expensive pure components, `useMemo`/`useCallback` for
   genuinely expensive computations/handlers passed to memoized children —
   not everywhere by default.
7. **Virtualize** long lists/tables (`@tanstack/react-virtual`) instead of
   rendering hundreds of DOM rows at once.
8. **Server Components by default** (see §2) — this alone cuts client JS
   significantly; only pay the client-bundle cost where interactivity is
   actually needed.
9. Run a Lighthouse / Core Web Vitals check (LCP, CLS, INP) on key pages
   before shipping a feature — not just "does it look right."
10. Debounce/throttle expensive client-side operations (search-as-you-type
    API calls, resize handlers, scroll listeners).

---

## 15. Reuse-First Rule (Check Before You Create)

**Before writing any new component, hook, store, util, or type — search the
codebase first. Creating a duplicate is a rule violation.**

1. **Search order before creating anything new:**
   - `components/ui/` — does shadcn already have this primitive
     (installed or installable via `npx shadcn add`)?
   - `components/common/` — does a shared, generic version already exist?
   - `components/features/<other-feature>/` — did another feature already
     build something close enough to generalize instead of duplicating?
   - `hooks/` and `lib/api/queries/` — does a hook for this data/behavior
     already exist?
   - `store/` — does a Zustand slice already hold this UI state?
   - `lib/utils.ts` / `lib/validators/` — does this formatter/validator
     already exist?
2. **If it exists and fits as-is → use it directly. Do not fork/copy-paste it.**
3. **If it exists but is close-but-not-quite → extend it to be reusable**
   (add a prop, a `cva` variant, a param) instead of creating a near-duplicate
   file. One canonical version per concern, configurable via props.
4. **Only if nothing reasonably close exists → create new**, and build it
   generic/reusable from the start:
   - Accept props for variation (don't hardcode feature-specific text/data
     inside a shared component).
   - Place it at the right layer immediately: truly generic → `components/
     common/`; feature-specific → `components/features/<feature>/`. Don't
     leave reusable things buried inside one feature folder "for now."
   - No feature-specific business logic inside `components/ui/` or
     `components/common/` — those layers must stay generic and importable
     by any feature without modification.
5. Same rule applies to hooks/queries/types: one `usePayrollItems()`, one
   `EmployeeDto`, one `formatCurrency()` — never redefine the same
   query/type/util under a slightly different name in a different file.
6. In PR review: reviewer must reject a PR that duplicates existing
   functionality instead of reusing/extending it, unless there's a clearly
   documented reason (e.g. genuinely different domain rules).

---

## 16a. Analysis-First, Permission-Before-Implementation Rule

**Before writing a single line of code for any feature or bug fix — analyze
first, get explicit go-ahead, then implement. No silent straight-to-code.**

1. **Analyze before touching code:**
   - Read the actual issue/requirement fully; don't assume based on the
     title alone.
   - Search the codebase for related/existing code (ties into §15 —
     reuse-first) so the analysis already knows what exists vs. what's
     genuinely new.
   - For a bug: find and state the **root cause**, not just the symptom.
     Reproduce it (or explain precisely why it happens) before proposing a
     fix.
   - For a feature: identify every file/module it will touch, and any
     existing behavior it could affect (state clearly if it risks regressing
     something already working — see PR #135/#136/#138 conflict lesson).
2. **Present the analysis + plan, then stop and ask:**
   - Summarize: what's wrong / what's needed, root cause (for bugs),
     proposed approach, files to be touched, anything risky or uncertain.
   - Explicitly ask for confirmation/permission before implementing —
     e.g. "Idhu than analysis, idha fix pannalama? confirm pannunga."
   - Do **not** proceed to implementation in the same step as the analysis
     unless the person has already pre-approved that workflow for this
     conversation/session.
3. **Only after explicit approval → implement:**
   - Implement exactly what was described in the approved plan.
   - If mid-implementation you discover the real fix needs to go beyond the
     approved scope, stop and re-confirm before expanding scope — don't
     silently widen the change.
4. **After implementing:**
   - State what was actually changed (files touched, behavior before/after).
   - Note any follow-up test/verification still needed (tests, lint, build —
     see §12, §16 CI rules) before it's considered done.
5. This rule applies to both bug fixes and new features, and to both a
   human developer's workflow and any AI coding assistant working in this
   repo — no exceptions for "it's a small fix."

---

## 17. Git / Workflow Rules

See `GIT.md` (separate file) for git/workflow rules.

---

## 18. Code Quality & Tooling Rules

1. ESLint + Prettier enforced project-wide, one shared config — no per-file
   style disagreements. Format-on-save enabled in editor config
   (`.vscode/settings.json` committed).
2. **Husky + lint-staged** pre-commit hook: run lint + format (and ideally
   `tsc --noEmit` on changed files) before a commit is allowed — bad code
   never reaches the remote branch.
3. **Absolute imports** via `@/...` path alias (configured in
   `tsconfig.json`) — never `../../../../components/...`. Keeps refactors
   and file moves painless.
4. No commented-out dead code left in — delete it (git history keeps it if
   needed).
5. No `console.log` left in committed code — use a proper logger (see §26)
   or remove before commit.

---

## 19. Accessibility (a11y) Rules

1. Use semantic HTML first (`<button>`, `<nav>`, `<main>`, `<label>`) before
   reaching for `<div onClick>`.
2. Every interactive element reachable and operable via keyboard (`Tab`,
   `Enter`, `Esc`) — test dialogs/sheets/dropdowns with keyboard only.
3. Focus management: opening a `Dialog`/`Sheet` moves focus into it; closing
   it returns focus to the trigger (shadcn primitives handle this by
   default — don't override it away).
4. All form inputs have an associated `<Label>` (shadcn `Form` handles this
   correctly out of the box — don't bypass it with a bare `<input>`).
5. Meaningful `alt` text on all images; decorative images get `alt=""`.
6. Color contrast meets **WCAG AA** minimum (4.5:1 for normal text) — check
   this when picking custom colors in `tailwind.config.ts`.
7. Don't convey information (errors, status) by color alone — pair with an
   icon or text (e.g. shadcn `Alert` variants already do this).

---

## 20. SEO Rules

1. Every page exports `metadata` or `generateMetadata` (title, description,
   OG tags) — no page ships without at least a title/description.
2. `sitemap.xml` and `robots.txt` generated via Next.js's built-in
   `sitemap.ts` / `robots.ts` conventions, kept in sync as routes are added.
3. Use `next/image` (already required, §14) — it also improves SEO via
   proper sizing and no layout shift.
4. Server-render (Server Components / SSR) anything that needs to be
   indexable — don't hide primary content behind client-only fetches.
5. One `<h1>` per page, logical heading hierarchy after that — don't skip
   levels or use headings purely for font size.

---

## 21. Security Rules

1. **Never trust client validation alone** — every mutation is re-validated
   server-side (zod schema shared or mirrored on the API), even though the
   client also validates with the same schema for UX (§8).
2. No secrets, API keys, or tokens in client components or `NEXT_PUBLIC_*`
   vars — those are bundled into the browser and public by definition.
3. Sanitize any user-generated content before rendering as HTML (avoid
   `dangerouslySetInnerHTML`; if unavoidable, sanitize with a library first).
4. Auth tokens: prefer httpOnly cookies over `localStorage` for session
   tokens to reduce XSS token-theft risk.
5. CSRF protection on state-changing requests where cookies are used for
   auth.
6. Rate-limit and validate on any public-facing API route, not just
   internal ones.
7. Dependency hygiene: run `npm audit` (or equivalent) regularly; don't add
   a new dependency without a quick check that it's maintained and
   necessary (ties into §15 — reuse before adding a new package too).

---

## 22. i18n / Localization Rules (if multi-language is required)

1. Use `next-intl` (or equivalent) — never hardcode user-facing strings
   directly in JSX if the project needs more than one language.
2. All translation keys centralized per locale file, grouped by
   feature/domain — no ad hoc inline strings mixed with translated ones.
3. Dates, numbers, currency formatted via locale-aware formatters
   (`Intl.NumberFormat`, `Intl.DateTimeFormat`), not manual string
   concatenation.
4. If the project is genuinely single-language only, skip this section —
   don't over-engineer i18n scaffolding that will never be used.

---

## 23. Dark Mode / Theming Rules

1. Theme via **CSS variables** (already required in §4.2) + `next-themes`
   for light/dark/system toggle — never hardcode light-only colors that
   break in dark mode.
2. Every custom color added to `tailwind.config.ts` must have a sensible
   dark-mode value defined alongside it — don't ship a color that only
   looks right in one mode.
3. Persist the user's theme choice (localStorage via `next-themes`, which
   handles this correctly and avoids flash-of-wrong-theme on load).
4. Test every new component in both light and dark mode before marking it
   done — same discipline as the responsive checklist (§13).

---

## 24. Environment & Config Rules

1. `.env.local` for real local secrets (never committed); `.env.example`
   committed with all required keys present but values blank/placeholder.
2. `NEXT_PUBLIC_*` prefix only for values safe to expose in the browser
   bundle (already noted in §2.7 / §21.2) — re-stated here as a config rule.
3. No environment-specific logic hardcoded in components (`if
   (window.location.hostname === 'staging...')`) — use env vars and a
   config module instead.
4. Feature flags (if used) live in one config/module, not scattered
   `if (Math.random() < 0.5)`-style ad hoc toggles — makes them easy to
   find, audit, and remove once a feature is fully rolled out.

---

## 25. Documentation Rules

1. Each non-trivial feature folder (`components/features/<feature>/`) gets
   a short `README.md` if the logic isn't self-evident from the code —
   what it does, key hooks/stores it depends on, any gotchas.
2. Complex shared `components/ui` / `components/common` components get
   **Storybook** stories (if Storybook is set up) so their variants/props
   are documented and visually testable in isolation.
3. Non-obvious business logic gets a short comment explaining *why*, not
   *what* (the code already shows what) — e.g. why a cache key includes a
   particular field.

---

## 26. Monitoring & Logging Rules

1. Client-side error tracking (e.g. Sentry or equivalent) wired into the
   root `error.tsx` / a global error boundary — unhandled errors must be
   visible somewhere other than a user's console.
2. No raw `console.log`/`console.error` left in production code paths — use
   a thin logger wrapper so logging can be toggled/routed centrally.
3. Analytics events follow one naming convention
   (`feature_action_object`, e.g. `payroll_item_updated`) — no inconsistent
   ad hoc event names scattered across features.

---

## 27. Animation Rules

1. Use `framer-motion` (or Tailwind's built-in transition utilities for
   simple cases) only for **meaningful** transitions — state changes,
   entrance/exit, drag interactions — not decoration for its own sake.
2. Respect `prefers-reduced-motion` — disable/simplify non-essential
   animation for users who've set that OS-level preference.
3. Keep animation durations short and consistent (a shared duration/easing
   scale, e.g. via Tailwind config or a constants file) rather than
   picking a new arbitrary duration per component.

---

## 28. Browser Support Rules

1. Define the minimum supported browser matrix up front (e.g. last 2
   versions of Chrome/Edge/Firefox/Safari) in `.browserslistrc` or
   `package.json` `browserslist` field — Tailwind/Next.js use this for
   autoprefixing and polyfill decisions.
2. Don't rely on bleeding-edge CSS/JS features without checking they're
   covered by the declared browser matrix; polyfill only what's genuinely
   needed for supported browsers, not everything by default.
3. Test critical flows (auth, core forms, payments if applicable) on at
   least one non-Chromium browser (Safari/Firefox) before release — don't
   assume Chromium-only testing is sufficient.

---

## 29. URL & Filter State Rules

1. Anything that should survive a page refresh or be shareable via link
   (search filters, active tab, pagination page, sort order) belongs in the
   **URL**, not Zustand — use `nuqs` (or Next.js `useSearchParams` +
   `router.replace`) to sync state to query params.
2. Zustand is for ephemeral UI state only (§7); URL is for "state that
   defines what the user is looking at." Don't duplicate the same value in
   both.
3. Debounce URL updates for free-text search inputs so typing doesn't spam
   `router.replace` on every keystroke.
4. Deep-linkable state (a specific row's edit dialog open via `?id=123`) is
   preferred over state that only exists in memory, for anything a user
   might want to bookmark or share.

---

## 30. API Contract & Error Shape Rules

1. **One standardized error response shape** across the whole backend/API
   surface (e.g. `{ code: string; message: string; fields?: Record<string,
   string> }`), and **one central parser** in `lib/api/client.ts` that all
   Query hooks rely on — no per-endpoint bespoke error parsing.
2. Backend error `code` values (not raw messages) drive UI behavior/field
   mapping (as already established in the PR #135 payroll error-mapping
   pattern) — never string-match a human-readable message to decide logic.
3. Define request/response types from a single source of truth where
   possible (OpenAPI/Swagger codegen, or a shared `types` package in a
   monorepo) rather than hand-typing DTOs that can drift from the real API.
4. Retry policy standardized centrally in the `QueryClient`/mutation
   defaults (e.g. retry GETs, don't blindly retry POST/PUT/DELETE) — not
   decided ad hoc per hook.
5. Version breaking API changes explicitly (URL versioning or a header) so
   frontend and backend can deploy independently without breaking each
   other.

---

## 31. End-to-End (E2E) Testing Rules

1. **Playwright** (preferred) or Cypress for E2E, in addition to unit tests
   (§12) — unit tests alone are not sufficient for an enterprise app.
2. Every critical user flow gets an E2E test: auth/login, core CRUD flow
   for the primary domain object, payment/checkout if applicable, and any
   flow that has previously broken in production.
3. E2E tests run against a real (or realistically seeded/staging) backend
   in CI, not just mocked responses — mocked-only E2E gives false
   confidence.
4. E2E suite runs on every PR to `main` (or at minimum nightly + before
   release) as a required CI check for release branches.
5. Flaky E2E tests get fixed or quarantined immediately — a flaky suite
   that's routinely ignored is worse than no suite.

---

## 32. CI/CD & Deployment Rules

1. **Preview deployments** for every PR (Vercel preview or equivalent) —
   reviewers test the actual running app, not just read the diff.
2. Pipeline order: lint → typecheck → unit tests → build → E2E (against
   preview/staging) → deploy. Fail fast — don't run expensive E2E if lint/
   typecheck already failed.
3. Separate environments: `local` → `staging`/`preview` → `production`.
   Production deploys only from `main` after CI is fully green and required
   approvals are in.
4. Environment-specific config injected via env vars per environment
   (§24), never via branching logic reading `NODE_ENV` deep inside
   components.
5. Rollback plan: keep the previous production build deployable/one-click
   revertible; don't rely on "just redeploy an older commit" being the only
   option under pressure.
6. Feature flags (§24.4) used to decouple *deploy* from *release* for
   risky features — merge to `main` and deploy don't have to mean
   "instantly visible to all users."

---

## 33. Design System Governance Rules

1. Track shadcn/ui component versions/customizations — when re-running
   `npx shadcn add <component>` to pick up upstream updates, diff against
   local customizations before overwriting; don't blindly accept updates
   that silently drop a team customization.
2. Any custom `cva` variant added to a `components/ui/*` primitive gets
   documented (Storybook story or a comment block) so the next dev knows it
   exists before adding a near-duplicate variant.
3. Design tokens (`tailwind.config.ts` colors/spacing/radii) are the single
   source of truth shared with design (Figma tokens ideally kept in sync,
   manually or via a token-sync tool) — no component picking arbitrary
   values that drift from the design system over time.
4. A designated owner (or small group) reviews any change to
   `components/ui/*` or `tailwind.config.ts` — these are shared
   infrastructure, not a single feature's concern, so review scope is
   wider than a normal feature PR.

---

## 34. Monorepo / Multi-App Rules (if the org runs more than one frontend app)

1. Use **Turborepo** or **Nx** once there's more than one app/package
   sharing code — don't hand-roll shared code via copy-paste or npm-link
   hacks.
2. Shared `ui`, `types`, `utils`, and `config` (ESLint/Tailwind/TS configs)
   live in their own packages, versioned and imported by each app — not
   duplicated per app.
3. Each app still follows every rule in this document independently
   (structure, state rules, etc.) — the monorepo only changes *where*
   shared code lives, not the per-app conventions.
4. CI runs affected-only builds/tests (Turborepo/Nx caching) rather than
   rebuilding every app on every change, once the repo is large enough for
   that to matter.

---

## Quick Checklist for Any New Feature

- [ ] **Analyzed the issue/requirement fully, found root cause (bugs) or
      full scope (features), and got explicit permission before
      implementing (§16a)**
- [ ] **Checked for existing component/hook/store/util first — reused or
      extended instead of duplicating (§15)**
- [ ] Server Component unless it truly needs interactivity
- [ ] Types/DTOs defined once in `lib/types/`
- [ ] Data fetching via a named TanStack Query hook, not inline
- [ ] Query keys from a centralized factory
- [ ] UI-only state in Zustand, server state in Query cache
- [ ] Forms via `react-hook-form` + `zod` + shadcn `Form`
- [ ] Styled with Tailwind + `cn()`, no arbitrary hex/inline styles
- [ ] shadcn primitives composed, not hand-edited per use
- [ ] Errors handled (toast for network, inline for field errors)
- [ ] **Responsive at mobile/tablet/laptop/desktop — manually verified (§13)**
- [ ] **Images via `next/image`, fonts via `next/font`, heavy UI lazy-loaded
      (§14)**
- [ ] New component built generic/reusable (props-driven), placed in the
      right layer (`ui/` vs `common/` vs `features/*`)
- [ ] Tests added for hooks/stores/forms touched
- [ ] Keyboard-navigable, labeled inputs, WCAG AA contrast (§19)
- [ ] Page has `metadata`/`generateMetadata` if it's a new route (§20)
- [ ] Server-side validation matches client validation, no secrets in
      client bundle (§21)
- [ ] Works correctly in both light and dark mode (§23)
- [ ] No `console.log` left in, lint/format/pre-commit hooks pass (§18)
- [ ] Error tracked via logger/Sentry, not a bare `console.error` (§26)