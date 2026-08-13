from fastapi import APIRouter, Depends
from app.api.v1.deps import get_current_user
from app.api.v1.routers import (
    auth,
    users,
    roles,
    organizations,
    invitations,
    super_admin,
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

# Public Authentication endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["1. Authentication & Security"])

# Super Admin Onboarding & Management endpoints
api_router.include_router(super_admin.router, prefix="/super-admin", tags=["25. Super Admin Suite"])

# Organization Invitations & Onboarding endpoints (Contains both public token validation/acceptance & protected invitation management)
api_router.include_router(invitations.router, prefix="/organizations/invitations", tags=["4. Organizations & Invitations"])

# Protected Application API endpoints requiring valid JWT Bearer token
api_router.include_router(users.router, prefix="/users", tags=["2. User Management"], dependencies=[Depends(get_current_user)])
api_router.include_router(roles.router, prefix="/roles", tags=["3. Roles & Permissions (RBAC)"], dependencies=[Depends(get_current_user)])
api_router.include_router(organizations.router, prefix="/organizations", tags=["4. Organizations"], dependencies=[Depends(get_current_user)])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["5. Dashboard & KPIs"], dependencies=[Depends(get_current_user)])
api_router.include_router(leads.router, prefix="/leads", tags=["6. Lead Management"], dependencies=[Depends(get_current_user)])
api_router.include_router(contacts.router, prefix="/contacts", tags=["7. Contact Management"], dependencies=[Depends(get_current_user)])
api_router.include_router(companies.router, prefix="/companies", tags=["8. Company Management"], dependencies=[Depends(get_current_user)])
api_router.include_router(deals.router, prefix="/deals", tags=["9. Deal Management & Pipeline"], dependencies=[Depends(get_current_user)])
api_router.include_router(tasks.router, prefix="/tasks", tags=["10. Task Management"], dependencies=[Depends(get_current_user)])
api_router.include_router(meetings.router, prefix="/meetings", tags=["11. Meetings"], dependencies=[Depends(get_current_user)])
api_router.include_router(calls.router, prefix="/calls", tags=["12. Call Logs & Telephony"], dependencies=[Depends(get_current_user)])
api_router.include_router(calendar.router, prefix="/calendar", tags=["13. Calendar"], dependencies=[Depends(get_current_user)])
api_router.include_router(emails.router, prefix="/emails", tags=["14. Emails & Inbox"], dependencies=[Depends(get_current_user)])
api_router.include_router(notes.router, prefix="/notes", tags=["15. Notes"], dependencies=[Depends(get_current_user)])
api_router.include_router(documents.router, prefix="/documents", tags=["16. Document Storage"], dependencies=[Depends(get_current_user)])
api_router.include_router(products.router, prefix="/products", tags=["17. Product Catalog"], dependencies=[Depends(get_current_user)])
api_router.include_router(quotes.router, prefix="/quotes", tags=["18. Quotes & Proposals"], dependencies=[Depends(get_current_user)])
api_router.include_router(invoices.router, prefix="/invoices", tags=["19. Invoices & Billing"], dependencies=[Depends(get_current_user)])
api_router.include_router(notifications.router, prefix="/notifications", tags=["20. Notifications"], dependencies=[Depends(get_current_user)])
api_router.include_router(reports.router, prefix="/reports", tags=["21. Reports & Analytics"], dependencies=[Depends(get_current_user)])
api_router.include_router(settings.router, prefix="/settings", tags=["22. Settings & Audit Logs"], dependencies=[Depends(get_current_user)])
api_router.include_router(integrations.router, prefix="/integrations", tags=["23. Integrations Hub"], dependencies=[Depends(get_current_user)])
api_router.include_router(ai.router, prefix="/ai", tags=["24. AI Sales Suite"], dependencies=[Depends(get_current_user)])
api_router.include_router(websockets.router, prefix="/ws", tags=["Real-time WebSockets"])
