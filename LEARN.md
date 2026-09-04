# Learning GSTFlow — what you built, and why

This is a study guide to your own project: what each app/module does,
which framework feature it demonstrates, and why it was built that way.
Read this top to bottom and you should be able to defend any part of it in
an interview or a viva.

---

## 1. The one-sentence pitch

GSTFlow reconciles a business's own purchase records against the GSTR-2A/2B
statement downloaded from the GST portal, using a **deterministic rule
engine** to find mismatches (not an LLM), and uses AI **only** to explain
those mismatches in plain English.

The single most important design decision in this codebase — and the one
worth leading with in an interview — is that **matching logic and AI
narration are two separate, isolated modules**:
[`reconciliation/engine.py`](backend/reconciliation/engine.py) decides
*what* is wrong (pure Python, unit-tested, zero I/O); [`reconciliation/ai_explain.py`](backend/reconciliation/ai_explain.py)
only describes a decision the engine already made. This is the difference
between "I called an LLM API" and "I designed a system where the
non-reproducible part is walled off from the part that has to be correct
and auditable."

---

## 2. Architecture at a glance

```
Browser (Next.js, port 3000)
   │  fetch() with JWT bearer token
   ▼
Django REST Framework API (port 8000)
   │  writes                              │  enqueues
   ▼                                        ▼
PostgreSQL  ◄──────────────────────  Celery worker (separate process)
(source of truth)                     │  reads/writes DB, reads Redis cache
                                       ▼
                                     Redis (message broker + result
                                     backend + short-lived password cache)
```

Two things trip people up and are worth internalizing:

- **The Django dev server and the Celery worker are two independent
  processes.** `runserver` only answers HTTP requests and enqueues jobs; it
  never runs them. If the worker isn't running, uploads and reconciliation
  runs sit in `"processing"` forever — this actually happened during
  development (see the git history / your own debugging session) and is
  the single most common failure mode of this project.
- **Celery does not auto-reload on code changes** the way `runserver`
  does. Change any file under `invoices/tasks.py` or `reconciliation/tasks.py`
  (or anything they import) and you must restart the worker process for the
  change to take effect.

---

## 3. Backend — Django project (`backend/`)

### 3.0 `gstflow/` — the project package (not an "app")

| File | What it is |
| --- | --- |
| [`gstflow/settings.py`](backend/gstflow/settings.py) | All configuration: installed apps, DRF settings, JWT lifetimes, CORS, Postgres connection, Celery broker/backend, Redis cache, AI provider config. Reads everything from `.env` via `python-dotenv` — nothing sensitive is hardcoded. |
| [`gstflow/celery.py`](backend/gstflow/celery.py) | Creates the Celery `app` object and points it at Django's settings (`app.config_from_object("django.conf:settings", namespace="CELERY")`), so `CELERY_BROKER_URL` in settings.py becomes Celery's `broker_url`. `app.autodiscover_tasks()` finds `tasks.py` in every installed app automatically. |
| [`gstflow/urls.py`](backend/gstflow/urls.py) | Top-level URL router — mounts each app's URLs under a namespace (`/api/auth/`, `/api/uploads/`, `/api/reconcile/`, `/api/dashboard/`). |

**Framework feature demonstrated:** Django's settings-as-single-source-of-truth
pattern, and the standard "Django + Celery" wiring where Celery piggybacks
on Django's settings module instead of having its own config file.

### 3.1 `accounts/` — authentication & tenancy

**What it does:** registers a business + user pair, logs them in, issues
JWTs.

| Concept | Where | Notes |
| --- | --- | --- |
| Custom user model | [`accounts/models.py`](backend/accounts/models.py) | `User` extends `AbstractUser` but sets `USERNAME_FIELD = "email"` — login is by email, not username. This has to be done at the *start* of a Django project (`AUTH_USER_MODEL = "accounts.User"` in settings) because swapping the user model later requires a full migration reset. |
| Multi-tenancy via a 1:1 model | `accounts/models.py` — `Business` | Every other model (`Invoice`, `ReconciliationRun`, …) has a `business` foreign key. This is the standard "row-level multi-tenancy" pattern: one Postgres database, one set of tables, tenant isolation enforced entirely in application code (every queryset filters `.filter(business=request.user.business)`). |
| JWT auth | [`accounts/urls.py`](backend/accounts/urls.py), `djangorestframework-simplejwt` | `TokenObtainPairView` (login) and `TokenRefreshView` (refresh) are used directly from the library — no custom code needed. Registration is custom (`RegisterView`) because it has to create *two* rows (`User` + `Business`) atomically and hand back tokens immediately so the user isn't asked to log in right after registering. |
| Serializer validation | [`accounts/serializers.py`](backend/accounts/serializers.py) | `RegisterSerializer` validates GSTIN length/uniqueness and normalizes casing (GSTIN/PAN uppercased) before the `.create()` ever touches the database — DRF's serializer validation layer, not model-level `clean()`. |

**Interview talking point:** "I used row-level multi-tenancy instead of
separate schemas/databases per tenant because this is a single-region app
with a modest number of tenants — every query is explicitly scoped by
`business_id`, which is simpler to reason about and test than
schema-per-tenant, at the cost of needing discipline that every view
actually applies that filter."

### 3.2 `invoices/` — file upload & parsing

**What it does:** accepts a purchase register or GSTR-2A/2B file (CSV,
XLSX, or JSON), handles password-protected XLSX files, and turns rows into
`Invoice` database records — asynchronously.

| Concept | Where | Notes |
| --- | --- | --- |
| Two-table model | [`invoices/models.py`](backend/invoices/models.py) | `InvoiceBatch` = one upload (metadata: filename, period, status, row count). `Invoice` = one parsed row, tagged `source="books"` or `source="2a"`, FK'd to its batch. Splitting these lets you show upload/parse status independently of the actual data. |
| Column-name normalization | [`invoices/parsing.py`](backend/invoices/parsing.py) | Real-world GST exports use inconsistent headers (`"GSTIN"` vs `"GSTIN of Supplier"` vs `"Supplier GSTIN"`). `COLUMN_ALIASES` maps many known variants to canonical field names before `pandas` ever sees a fixed schema. Also combines split `Integrated Tax` / `Central Tax` / `State Tax` / `Cess` columns into one `tax_amount` when there's no single combined column — this is exactly how GSTR-2A exports are actually formatted. |
| Password-protected files | `invoices/parsing.py` (`_decrypt_xlsx`), [`invoices/views.py`](backend/invoices/views.py) | `msoffcrypto-tool` checks `is_encrypted()` cheaply (header read, no full parse) before committing to a decrypt attempt. If a password is needed, the endpoint returns HTTP 422 with `{"needs_password": true, "upload_token": "..."}` instead of an error — the frontend treats this as a normal branch of the upload flow, not a failure. |
| Never persist secrets | `invoices/views.py`, [`invoices/tasks.py`](backend/invoices/tasks.py) | The password is written to Redis (Django's cache framework) with a **60-second TTL**, read exactly once by the Celery task, then explicitly deleted (`cache.delete(...)`) immediately after use — regardless of whether decryption succeeded. It is never passed as a Celery task *argument*, because task arguments get logged by Celery/Redis; it's passed by reference (a token) instead. |
| Rate limiting | `invoices/views.py`, `UPLOAD_PASSWORD_MAX_ATTEMPTS` in settings | A wrong-password attempt increments a counter in the cache keyed by `upload_token`; once it hits the limit the endpoint returns 429 without even trying to parse. Prevents the upload endpoint being turned into a password-guessing oracle. |
| Async processing via Celery | `invoices/tasks.py` — `parse_and_store_batch` | The view does the *cheap* work (encryption check, `InvoiceBatch` row creation) synchronously and returns HTTP 202 immediately; the *expensive* work (parsing thousands of rows, `bulk_create`) happens in a Celery task on a separate worker process. This is the standard "don't block the request-response cycle on slow I/O" pattern. |
| Bulk insert | `invoices/tasks.py` | `Invoice.objects.bulk_create(objs, batch_size=500)` — one INSERT per 500 rows instead of one per row. For a 5,000-row file that's 10 queries instead of 5,000. |
| Synthetic demo data | [`invoices/management/commands/generate_sample_data.py`](backend/invoices/management/commands/generate_sample_data.py) | A custom Django management command (`python manage.py generate_sample_data`) — the standard way to add CLI subcommands to `manage.py`. Generates a purchase register + GSTR-2A pair with one deliberate example of every discrepancy type, so you always have realistic data to demo against. |

**Interview talking point:** "The upload endpoint is intentionally
'dumb and fast' — it does the minimum synchronous work needed to hand back
a batch ID, and pushes everything expensive onto a background worker. The
frontend polls a status endpoint rather than the request blocking, which
is what lets a 5,000-row Excel file not time out an HTTP request."

### 3.3 `reconciliation/` — the actual product

This is the core of the project — the part an interviewer will drill into.

| Concept | Where | Notes |
| --- | --- | --- |
| Pure-function matching engine | [`reconciliation/engine.py`](backend/reconciliation/engine.py) | `reconcile(books_records, statement_records, value_tolerance)` takes plain dicts in, returns a list of `MatchResult` dataclasses out. No Django import, no database access, no I/O of any kind. This is what makes it unit-testable in milliseconds without a database (see `SimpleTestCase` in the tests) and makes the matching logic auditable independent of the web framework around it. |
| Matching algorithm | `engine.py` | Multi-pass: (1) within each source, group by `(GSTIN, normalized invoice number)` and flag every row after the first as `duplicate`; (2) exact-key intersection between books and statement → compare invoice value within a tolerance (`value_mismatch` vs `matched`), or date if value matches (`date_mismatch`); (3) for whatever's left unmatched on both sides, a **fuzzy pass** using Levenshtein edit distance on the GSTIN (capped at distance 2) catches likely typos and reclassifies them as `gstin_mismatch` instead of two separate missing-invoice flags; (4) anything still unmatched is `missing_in_2a` (books-only) or `missing_in_books` (statement-only). |
| Why not fuzzy-match everything | `engine.py` docstring/comments | Only the GSTIN gets fuzzy matching, and only after invoice number + value already match exactly. Fuzzy-matching invoice numbers too would silently merge genuinely different invoices — a correctness/safety tradeoff worth being able to explain. |
| Levenshtein distance from scratch | `engine.py` — `_edit_distance` | A textbook dynamic-programming edit-distance implementation (no library), because GSTINs are short (15 chars) so a hand-rolled O(n·m) DP table is simpler than pulling in a dependency. |
| Batch-scoped, not date-scoped, period filtering | [`reconciliation/tasks.py`](backend/reconciliation/tasks.py) | A real bug (and fix) worth knowing: reconciliation scopes invoices by picking the **latest completed `InvoiceBatch`** per source for the requested period — not by filtering each `Invoice.invoice_date` against the period, and not by pooling every batch ever uploaded for that period. The first approach breaks because GSTR-2A dates legitimately fall outside the filing month (that's what `date_mismatch` exists to catch); the second breaks because a re-upload would pile up alongside old uploads instead of superseding them, flooding the result with false `duplicate`s. |
| Two-table result model | [`reconciliation/models.py`](backend/reconciliation/models.py) | `ReconciliationRun` = one run's summary stats (counts, ITC-at-risk total, status). `Discrepancy` = one flagged invoice, FK'd to the run and to the one or two `Invoice` rows involved (`books_invoice`/`statement_invoice`, either of which can be null). |
| Isolated AI layer | [`reconciliation/ai_explain.py`](backend/reconciliation/ai_explain.py) | `explain_discrepancy(discrepancy_type, detail, context)` is the *only* function in the codebase that calls an LLM. It currently calls the Groq API (`openai/gpt-oss-20b`) directly with `urllib` (no SDK dependency) — a raw HTTP POST to an OpenAI-compatible `/chat/completions` endpoint. If `GROQ_API_KEY` is unset, disabled, or the call fails for any reason (network, auth, timeout, malformed response), it falls back to a fixed per-discrepancy-type template string, so the product still works end-to-end with zero external dependencies. |
| Async orchestration | `reconciliation/tasks.py` — `run_reconciliation` | Loads the two batches → converts `Invoice` rows to plain dicts → calls the pure `engine.reconcile()` → for every non-matched result, optionally calls `explain_discrepancy()` → `bulk_create`s all `Discrepancy` rows → updates the run's summary stats. This function is the "glue" layer: everything either side of it is either pure logic or a thin DB/AI call. |
| Filtering & pagination | [`reconciliation/views.py`](backend/reconciliation/views.py) | `DiscrepancyListView` uses `django-filter`'s `DjangoFilterBackend` with `filterset_fields = ["discrepancy_type", "resolved"]` — filtering is declared, not hand-written as `if request.GET.get(...)` branches. Pagination is DRF's built-in `PageNumberPagination`. |
| Aggregation queries | `reconciliation/views.py` — `DashboardView` | Uses Django ORM aggregation (`Count`, `.values().annotate()`) to compute a discrepancy-type breakdown in one query instead of looping in Python. |

**Interview talking point (the one to lead with):** "The reconciliation
logic is deterministic on purpose. An LLM deciding whether two invoices
match would be slow, non-reproducible between runs, and impossible to
defend if a business disputed a result. So I built a pure, unit-tested
matching function with an explicit, explainable rule set, and the AI's job
is strictly downstream of that — narrating a decision that's already been
made, never making it."

### 3.4 Testing

| File | What it tests | How |
| --- | --- | --- |
| [`reconciliation/tests/test_engine.py`](backend/reconciliation/tests/test_engine.py) | Every discrepancy type the engine can produce (matched, missing-in-2A, missing-in-books, value mismatch within/beyond tolerance, duplicate, GSTIN typo vs. genuinely different GSTIN, date mismatch, invoice-number normalization) | `django.test.SimpleTestCase` (no database — appropriate because `engine.py` never touches the DB) with hand-built dict fixtures. |
| [`invoices/tests/test_uploads.py`](backend/invoices/tests/test_uploads.py) | The password-protected-upload flow: encrypted file → 422 prompt; wrong password → rate-limited after N attempts; password never left sitting in the cache after a successful parse | `rest_framework.test.APITestCase` with `unittest.mock.patch` to fake encryption detection and force `FileNeedsPassword`, and the Celery task's `.delay()` replaced with a synchronous call to `.run()` so tests don't need a live worker or broker. |

**Interview talking point:** "The engine tests don't touch the database at
all — `SimpleTestCase` instead of `TestCase` — because the engine itself
never touches the database. That's a direct payoff of keeping it a pure
function: the test suite for the most important logic in the app runs in
milliseconds."

---

## 4. Frontend — Next.js app (`frontend/`)

Built with the **App Router** (the `src/app/` directory convention, not
the older `pages/` router), TypeScript, and Tailwind CSS for styling. No
component library, no state-management library — plain `useState`/`useEffect`
and a small hand-rolled fetch wrapper, which is a deliberate choice for a
project this size (see §5 below).

| File | What it does | Framework feature |
| --- | --- | --- |
| [`app/layout.tsx`](frontend/src/app/layout.tsx) | Root layout — wraps every page in `<AuthProvider>` and `<NavBar>`. | Next.js's root-layout convention: one `layout.tsx` at the top of `app/` is required and wraps all pages; nested layouts wrap only their subtree. |
| [`app/login/page.tsx`](frontend/src/app/login/page.tsx), [`app/register/page.tsx`](frontend/src/app/register/page.tsx) | Auth forms, call `useAuth().login()`/`.register()`. | Client components (`"use client"`) — these need interactivity (`useState`, event handlers), so they opt out of the App Router's default server-rendering. |
| [`app/page.tsx`](frontend/src/app/page.tsx) | Dashboard — fetches `/api/dashboard/`, renders stat cards + a discrepancy-type breakdown + a link to the latest run. | `RequireAuth` wrapper for client-side route protection. |
| [`app/upload/page.tsx`](frontend/src/app/upload/page.tsx) + [`components/FileUploadBox.tsx`](frontend/src/components/FileUploadBox.tsx) | The upload flow: pick a file → upload → if a password prompt comes back, show an inline password field and retry with the same `upload_token` → poll the batch status until `done`/`failed` → once both files are done, enable "Run Reconciliation". | `FileUploadBox` is a small state machine (`idle → uploading → needs_password → processing → done/failed`) built with plain `useState`, `setTimeout`-based polling, and cleanup on unmount via a `useRef` timer handle. |
| [`app/runs/[id]/page.tsx`](frontend/src/app/runs/%5Bid%5D/page.tsx) | The discrepancy review screen — run summary, type filter pills, list of discrepancies with AI explanations, resolve toggle. | Next.js **dynamic route segment** (`[id]` folder) + the App Router's typed-routes helper `PageProps<'/runs/[id]'>`; `params` is a `Promise` in this Next.js version and is unwrapped with React's `use()` hook, not `await` (this page is a client component, so it can't be `async`). Polls the run status while it's `"processing"`. |
| [`lib/api.ts`](frontend/src/lib/api.ts) | A ~90-line hand-rolled fetch wrapper: attaches the JWT bearer token, retries once with a refreshed access token on a 401, and throws a typed `ApiError` (status + parsed body) on failure. | No `axios`, no React Query — a deliberate minimal-dependency choice (see §5). |
| [`lib/auth.tsx`](frontend/src/lib/auth.tsx) | React Context provider (`AuthProvider`/`useAuth`) holding the current business profile, plus `login`/`register`/`logout`. On mount, calls `/api/auth/me/` (wrapped in `queueMicrotask` so the fetch is deferred a tick past initial render) to restore a session from a token already in `localStorage`. | React Context — the standard way to share auth state across a whole component tree without prop-drilling. |
| [`components/RequireAuth.tsx`](frontend/src/components/RequireAuth.tsx) | Redirects to `/login` if `useAuth()` resolves with no business. | Client-side route guarding — this app has no middleware-based auth (see §5, a known simplification). |
| [`lib/types.ts`](frontend/src/lib/types.ts) | Every API response shape as a TypeScript type, plus a `DISCREPANCY_LABELS` lookup for human-readable labels. | Keeps the frontend's understanding of the API contract in one place instead of scattered inline types. |

**Interview talking point:** "The upload widget is a small explicit state
machine rather than a pile of booleans (`isLoading`, `hasError`,
`needsPassword`, …) — there's exactly one `phase` variable and the UI
renders based on which phase it's in, which makes it obvious which states
are even reachable."

---

## 5. Deliberate simplifications (know these — they're good interview answers)

Being able to say "I know this is a simplification, and here's what I'd do
differently at scale" is worth more than pretending everything is
production-grade. A few real ones in this codebase:

- **No `axios`/React Query.** A hand-rolled `apiFetch` wrapper handles auth
  headers and one-shot token refresh. At this scale that's less code and
  less to learn than a data-fetching library; the tradeoff given up is
  caching, request deduplication, and background refetching, which is why
  pages do their own polling by hand (`setTimeout`) instead of getting it
  for free from a library like React Query.
- **Client-side auth guarding, not middleware.** `RequireAuth` checks auth
  state *after* the page has already mounted and redirects client-side —
  there's a flash of "Loading..." rather than the server refusing to even
  send the page. Next.js middleware (`middleware.ts`) could intercept
  requests before render, at the cost of needing the JWT accessible
  outside `localStorage` (e.g. in a cookie).
- **Row-level multi-tenancy with no extra enforcement layer.** Tenant
  isolation is "every queryset filters by `business`" — correct, but it
  relies on every view remembering to do it (they all do, but there's no
  database-level guarantee like Postgres row-level security).
- **The AI provider is one `if/try` away from swappable, not pluggable.**
  `ai_explain.py` calls Groq directly; swapping providers means editing
  that one function, not registering a new provider class. That's a
  reasonable tradeoff for "the whole point is that it's isolated to one
  file," but it's not a strategy/plugin pattern.
- **No real GSTN integration** (by design, stated explicitly in the
  README) — no GSP licensing, no live portal API calls. Files are
  downloaded manually and uploaded by the user, which is exactly what the
  problem statement calls for a simulated system to do.

---

## 6. Suggested resume bullets

Pick 2-3 depending on the role; don't use all of them, that reads as
padding.

- Built a full-stack GST invoice reconciliation platform (Django REST
  Framework + Next.js/TypeScript) with JWT auth, async file processing via
  Celery/Redis, and a deterministic rule-based matching engine reconciling
  purchase records against tax authority statements across 7 discrepancy
  categories, including fuzzy GSTIN-typo detection via a hand-implemented
  Levenshtein distance.
- Designed an isolated AI-narration layer (Groq LLM API) strictly
  downstream of a pure, unit-tested matching engine — kept the
  non-reproducible model call fully separate from the auditable business
  logic that decides outcomes, with automatic template-based fallback if
  the AI call fails.
- Implemented secure handling of password-protected file uploads
  (`msoffcrypto-tool`): encryption detection without full parsing,
  short-lived Redis-cached passwords never passed through Celery task
  arguments or logs, and rate-limited retry attempts.
- Wrote a dependency-free matching engine (no ORM, no I/O) enabling
  millisecond unit tests independent of the database, covering every
  discrepancy classification the system can produce.

---

## 7. If you want to go deeper next

Things you *haven't* built yet that would be natural next steps to learn
(and good "what would you add next" interview answers):

- Server-side auth via Next.js middleware + httpOnly cookies instead of
  `localStorage` JWTs (closes an XSS token-theft gap).
- Postgres row-level security or a query-layer guard so a missing
  `.filter(business=...)` fails loudly instead of silently leaking data
  across tenants.
- A provider-agnostic AI interface (e.g. a small `Explainer` protocol/ABC)
  if you ever need to swap Groq for something else without editing the
  call site.
- Idempotent uploads (hash the file, skip re-parsing an identical
  re-upload) instead of relying on "latest batch wins."
