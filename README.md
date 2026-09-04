# GSTFlow

AI-assisted GST invoice reconciliation and exception-management platform for
small businesses. Built for the Startup India EoDB Grand Challenge (Problem
Statement 5).

**This is a simulated system for a college project** — no real GSTN
integration, no GSP licensing, no actual return filing. A business uploads
its own purchase register and the GSTR-2A/2B statement it downloaded from
the GST portal; GSTFlow matches invoices between the two, flags mismatches,
and uses AI only to explain discrepancies in plain language. It's positioned
as complementary to (and benchmarked against) ClearTax, Zoho Books, and
TallyPrime, not a replacement for the GST portal/IMS.

## Features

- **Auth** — business registration and login with JWT access/refresh tokens.
- **File uploads** — purchase register (CSV/XLSX) and GSTR-2A/2B statement
  (XLSX/JSON) uploads, parsed asynchronously via Celery so large files never
  block the request thread.
- **Password-protected files** — encrypted `.xlsx` uploads are detected,
  the user is prompted for a password inline, and attempts are rate-limited
  (see [Password-protected uploads](#password-protected-uploads)).
- **Deterministic reconciliation engine** — matches invoices on GSTIN +
  invoice number with a configurable value tolerance, and classifies every
  invoice as one of: `matched`, `missing_in_2a`, `missing_in_books`,
  `value_mismatch`, `duplicate`, `gstin_mismatch` (fuzzy GSTIN-typo
  detection), or `date_mismatch`. Pure Python, unit-tested, no LLM involved.
- **AI-generated plain-language explanations** — one explanation per
  discrepancy, written for a non-accountant reader, generated after the
  engine has already decided the outcome (see [AI explanations](#ai-explanations)).
- **Discrepancy review** — filterable, paginated discrepancy list per
  reconciliation run, with a resolved/unresolved toggle.
- **Dashboard** — totals for purchase/statement invoices, matched vs.
  flagged counts, ITC-at-risk value, and a breakdown by discrepancy type.
- **Synthetic sample data generator** — a management command that produces
  a realistic purchase register + GSTR-2A pair with one deliberate example
  of every discrepancy type, for demoing without needing real invoice data.

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register/` | Register a business + user, returns JWT pair |
| POST | `/api/auth/login/` | Log in, returns JWT pair |
| POST | `/api/auth/refresh/` | Refresh an access token |
| GET | `/api/auth/me/` | Current business profile |
| POST | `/api/uploads/purchase-register/` | Upload purchase register (multipart, optional `password`, `period`) |
| POST | `/api/uploads/gstr2a/` | Upload GSTR-2A/2B statement (multipart, optional `password`, `period`) |
| GET | `/api/uploads/{batch_id}/` | Upload/parse status for a batch |
| POST | `/api/reconcile/` | Trigger a reconciliation run for a period |
| GET | `/api/reconcile/{run_id}/` | Run status + summary stats |
| GET | `/api/reconcile/{run_id}/discrepancies/` | Paginated discrepancies, filterable by `discrepancy_type` / `resolved` |
| PATCH | `/api/reconcile/discrepancies/{id}/` | Mark a discrepancy resolved/unresolved |
| GET | `/api/dashboard/` | Aggregate stats across all runs |

## Why the matching is deterministic, not AI

The reconciliation engine ([`backend/reconciliation/engine.py`](backend/reconciliation/engine.py))
is plain, dependency-free Python: it takes two lists of invoice records and
returns match results using GSTIN + invoice number + value-tolerance rules.
No LLM is involved in deciding what matches what — that would be slow,
non-reproducible, and hard to defend under questioning. The **only** place an
LLM is called is [`reconciliation/ai_explain.py`](backend/reconciliation/ai_explain.py),
which narrates a discrepancy the engine has already decided, in plain
language for a non-accountant reader.

## Stack

- **Backend**: Django + Django REST Framework, PostgreSQL, JWT auth
  (`djangorestframework-simplejwt`), Celery + Redis for async file
  parsing/reconciliation.
- **Frontend**: Next.js (App Router) + Tailwind CSS.
- **File handling**: `pandas`/`openpyxl` for CSV/XLSX, `msoffcrypto-tool` for
  password-protected `.xlsx`.

## Repository layout

```
backend/          Django project (accounts, invoices, reconciliation apps)
  reconciliation/engine.py     the deterministic matching engine (pure, unit-tested)
  reconciliation/ai_explain.py the one place an LLM is called
  invoices/parsing.py          CSV/XLSX/JSON parsing + password handling
  invoices/management/commands/generate_sample_data.py  synthetic demo data
frontend/         Next.js app (login, upload, dashboard, discrepancy table)
```

## Running it locally

### Prerequisites

- Python 3.11+, Node 20+
- PostgreSQL running locally, with a `gstflow` database created
- Redis running locally (`redis-server`)

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt   # or: pip install django djangorestframework djangorestframework-simplejwt psycopg2-binary celery redis pandas openpyxl pikepdf msoffcrypto-tool django-cors-headers python-dotenv django-filter
cp .env.example .env              # edit DB_USER etc. for your machine
python manage.py migrate
python manage.py generate_sample_data   # writes sample_data/*.csv/.xlsx for demoing
python manage.py runserver 8000
```

In a second terminal, start the Celery worker (required — uploads and
reconciliation runs are processed asynchronously):

```bash
cd backend && source venv/bin/activate
celery -A gstflow worker --loglevel=info
```

Run the test suite (the reconciliation engine's unit tests are the ones that
matter most — they exercise every discrepancy type without touching the DB):

```bash
python manage.py test
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

`frontend/.env.local` points at `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.

### Demo flow

1. Register a business account at `/register`.
2. Go to `/upload`, set a period (e.g. `04-2026`), and upload
   `backend/sample_data/purchase_register.csv` and
   `backend/sample_data/gstr2a.xlsx` (generated by `generate_sample_data`,
   deliberately seeded with a clean match, a missing-in-2A, a
   missing-in-books, a value mismatch, a duplicate, a GSTIN typo, and a date
   mismatch).
3. Click "Run Reconciliation" — you're taken to the run's discrepancy table,
   filterable by type, each with a plain-language AI explanation.
4. `/` shows the dashboard: totals reconciled/flagged and ITC-at-risk value.

## AI explanations

Set `GROQ_API_KEY` in `backend/.env` to get live Groq-generated explanations.
The default model is `openai/gpt-oss-20b`, configurable through
`GROQ_MODEL`. Without a key, `ai_explain.py` falls back to a fixed template
per discrepancy type so the app still functions end-to-end offline (and the
same template also acts as the safety net if the API call fails).

## Password-protected uploads

If a `.xlsx` file is encrypted, the upload endpoint responds with
`{"needs_password": true, "upload_token": "..."}` instead of erroring out;
the frontend prompts inline and retries with the same `upload_token` plus a
`password` field. Passwords are never persisted or logged — they're read
from a short-lived Redis cache entry by the Celery task and deleted
immediately after use. Wrong-password attempts are capped per upload
(`UPLOAD_PASSWORD_MAX_ATTEMPTS`, default 5) to prevent the endpoint being
used as a guessing oracle.

## Explicitly out of scope

GSTR-1/3B draft generation, PAN/DOB-based password-guessing heuristics,
multi-GSTIN/multi-PAN support, e-invoice/IRN handling, real GSTN API calls.
