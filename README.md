# Enterprise CRM (Customer Relationship Management) System

An Enterprise SaaS Customer Relationship Management system built with Next.js 15, React 19, TypeScript, Tailwind CSS, Python FastAPI, SQLAlchemy 2.0, PostgreSQL, Redis, Celery, and AI integrations based on `CRM_PRD_Updated.md`.

## Project Architecture

```
CRM/
├── CRM_PRD_Updated.md        # Product Requirements Document
├── frontend/                 # Next.js 15 App Router Frontend
│   ├── src/
│   │   ├── app/              # 21 Functional Modules + Auth
│   │   ├── components/       # UI & AI Chat Assistant Component
│   │   ├── config/           # Navigation Settings
│   │   ├── lib/              # API Client & Zod Schemas
│   │   ├── providers/        # TanStack Query Provider
│   │   ├── services/         # AI API Service Layer
│   │   ├── store/            # Zustand State Management
│   │   └── types/            # TypeScript CRM Data Models
│   └── package.json
└── backend/                  # Python FastAPI Backend
    ├── app/
    │   ├── api/v1/           # REST API & WebSocket Endpoints
    │   ├── core/             # JWT Auth, Bcrypt, RBAC Permissions
    │   ├── models/           # SQLAlchemy 2.0 ORM Models
    │   ├── schemas/          # Pydantic v2 Request/Response Schemas
    │   ├── services/         # Gemini / OpenAI / Anthropic AI provider layer
    │   └── worker/           # Celery Async Background Tasks
    └── requirements.txt
```

## Getting Started

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

### Backend Development
```bash
cd backend
python -m venv venv
# On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Backend test suite

The backend tests use disposable PostgreSQL, Redis, and MinIO services. Start
the services from the repository root, then run the complete suite from the
backend directory:

```bash
POSTGRES_DB=crm_test docker compose up -d postgres redis minio createbuckets
cd backend
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/crm_test
export CRM_WORKFLOW_TEST_DATABASE_URL="$DATABASE_URL"
export CRM_DISABLE_DOTENV=1
export AWS_ENDPOINT_URL=http://localhost:9000
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin
export AWS_S3_BUCKET=crm-test-bucket
pytest -q --cov=app --cov-report=term-missing --cov-report=xml
python scripts/check_health.py
```

CI runs the same suite with pinned development dependencies and fails on test
errors, failures, unexpected skips, and deprecation/resource/runtime warnings.
The release smoke check validates both `/health/live` and dependency-aware
`/health/ready` within a five-second latency budget.
Document uploads are capped at 10 MiB and read in bounded 1 MiB chunks; the
scheduled object-storage reconciler records missing references and only removes
orphaned objects after a 24-hour grace period.

### AI provider configuration

AI model identifiers are deployment configuration, not application constants. For CRM natural-language
search, set `SUSANOOX_AI_KEY`, `AI_PROVIDER=susanoox`, and `AI_MODEL=susanoox-fast`. The default
`SUSANOOX_MODEL_POOL=susanoox-fast,susanoox-large` retains ordered retry fallback. Keep
provider keys in runtime environment variables and never commit real credentials. Existing Gemini
configuration remains available only for workflows that still explicitly use Gemini.
