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

### AI provider configuration

AI model identifiers are deployment configuration, not application constants. To use Gemini,
set `GEMINI_API_KEY`, set `AI_PROVIDER=gemini`, and set `AI_MODEL` to a Gemini model enabled for
the API key. Optional `AI_GEMINI_WEB_SEARCH_MODEL` and `AI_GEMINI_TRANSCRIPTION_MODEL` values may
select dedicated models; when omitted, those Gemini operations use `AI_MODEL`. Keep provider keys
in runtime environment variables and never commit real credentials.
