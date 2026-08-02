from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    users,
    roles,
    organizations,
    dashboard,
    leads,
    contacts,
    companies,
    deals,
    tasks,
    meetings,
    calls,
    calendar,
    emails,
    notes,
    documents,
    products,
    quotes,
    invoices,
    notifications,
    reports,
    settings,
    integrations,
    ai,
    websockets
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["1. Authentication & Security"])
api_router.include_router(users.router, prefix="/users", tags=["2. User Management"])
api_router.include_router(roles.router, prefix="/roles", tags=["3. Roles & Permissions (RBAC)"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["4. Organizations"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["5. Dashboard & KPIs"])
api_router.include_router(leads.router, prefix="/leads", tags=["6. Lead Management"])
api_router.include_router(contacts.router, prefix="/contacts", tags=["7. Contact Management"])
api_router.include_router(companies.router, prefix="/companies", tags=["8. Company Management"])
api_router.include_router(deals.router, prefix="/deals", tags=["9. Deal Management & Pipeline"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["10. Task Management"])
api_router.include_router(meetings.router, prefix="/meetings", tags=["11. Meetings"])
api_router.include_router(calls.router, prefix="/calls", tags=["12. Call Logs & Telephony"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["13. Calendar"])
api_router.include_router(emails.router, prefix="/emails", tags=["14. Emails & Inbox"])
api_router.include_router(notes.router, prefix="/notes", tags=["15. Notes"])
api_router.include_router(documents.router, prefix="/documents", tags=["16. Document Storage"])
api_router.include_router(products.router, prefix="/products", tags=["17. Product Catalog"])
api_router.include_router(quotes.router, prefix="/quotes", tags=["18. Quotes & Proposals"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["19. Invoices & Billing"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["20. Notifications"])
api_router.include_router(reports.router, prefix="/reports", tags=["21. Reports & Analytics"])
api_router.include_router(settings.router, prefix="/settings", tags=["22. Settings & Audit Logs"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["23. Integrations Hub"])
api_router.include_router(ai.router, prefix="/ai", tags=["24. AI Sales Suite"])
api_router.include_router(websockets.router, prefix="/ws", tags=["Real-time WebSockets"])
