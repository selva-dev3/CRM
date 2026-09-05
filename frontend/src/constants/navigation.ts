import { hasPermission, PermissionKey, PERMISSIONS } from '@/lib/permissions';

export interface NavItem {
  title: string;
  href: string;
  icon: string;
  badge?: string;
  permission?: PermissionKey;
}

export interface NavSection {
  title?: string;
  items: NavItem[];
}

export const navigationSections: NavSection[] = [
  {
    items: [
      { title: 'Dashboard', href: '/dashboard', icon: 'LayoutDashboard', permission: PERMISSIONS.DASHBOARD.READ }
    ]
  },
  {
    title: 'CRM',
    items: [
      { title: 'Leads', href: '/leads', icon: 'UserPlus', permission: PERMISSIONS.LEADS.READ },
      { title: 'Contacts', href: '/contacts', icon: 'Users', permission: PERMISSIONS.CONTACTS.READ },
      { title: 'Companies', href: '/companies', icon: 'Building2', permission: PERMISSIONS.COMPANIES.READ },
      { title: 'Deals', href: '/deals', icon: 'Kanban', permission: PERMISSIONS.DEALS.READ },
      { title: 'Tasks', href: '/tasks', icon: 'CheckSquare', permission: PERMISSIONS.TASKS.READ },
      { title: 'Meetings', href: '/meetings', icon: 'CalendarDays', permission: PERMISSIONS.MEETINGS.READ },
      { title: 'Calls', href: '/calls', icon: 'PhoneCall', permission: PERMISSIONS.CALLS.READ },
      { title: 'Emails', href: '/email', icon: 'Mail', permission: PERMISSIONS.EMAILS.READ },
      { title: 'Notes', href: '/notes', icon: 'StickyNote', permission: PERMISSIONS.NOTES.READ },
      { title: 'Documents', href: '/documents', icon: 'FileText', permission: PERMISSIONS.DOCUMENTS.READ },
      { title: 'Products', href: '/products', icon: 'Package', permission: PERMISSIONS.PRODUCTS.READ },
      { title: 'Quotes', href: '/quotes', icon: 'FileSpreadsheet', permission: PERMISSIONS.QUOTES.READ },
      { title: 'Invoices', href: '/invoices', icon: 'Receipt', permission: PERMISSIONS.INVOICES.READ },
      { title: 'Payments', href: '/payments', icon: 'CreditCard', permission: PERMISSIONS.INVOICES.READ }
    ]
  },
  {
    title: 'Analytics',
    items: [
      { title: 'Reports', href: '/reports', icon: 'BarChart3', permission: PERMISSIONS.REPORTS.READ },
      { title: 'Calendar', href: '/calendar', icon: 'Calendar', permission: PERMISSIONS.CALENDAR.READ },
      { title: 'AI Intelligence', href: '/ai', icon: 'Sparkles', permission: PERMISSIONS.AI.READ }
    ]
  },
  {
    title: 'Administration',
    items: [
      { title: 'User Management', href: '/users', icon: 'UserCog', permission: PERMISSIONS.USERS.READ },
      { title: 'Roles & Permissions', href: '/roles', icon: 'ShieldCheck', permission: PERMISSIONS.ROLES.READ }
    ]
  }
];

export const navigationConfig: NavItem[] = navigationSections.flatMap((s) => s.items);

/**
 * Route-level permission map used for centralized route protection in the
 * dashboard layout. Covers every protected URL, including routes that are not
 * sidebar items (settings, organization, integrations, notifications).
 * Detail routes inherit their parent's permission via the top path segment.
 *
 * Keys are the real backend permission keys (see `src/lib/permissions.ts`).
 */
export const protectedRoutes: Record<string, PermissionKey> = {
  dashboard: PERMISSIONS.DASHBOARD.READ,
  leads: PERMISSIONS.LEADS.READ,
  contacts: PERMISSIONS.CONTACTS.READ,
  companies: PERMISSIONS.COMPANIES.READ,
  deals: PERMISSIONS.DEALS.READ,
  tasks: PERMISSIONS.TASKS.READ,
  meetings: PERMISSIONS.MEETINGS.READ,
  calls: PERMISSIONS.CALLS.READ,
  email: PERMISSIONS.EMAILS.READ,
  emails: PERMISSIONS.EMAILS.READ,
  notes: PERMISSIONS.NOTES.READ,
  documents: PERMISSIONS.DOCUMENTS.READ,
  products: PERMISSIONS.PRODUCTS.READ,
  quotes: PERMISSIONS.QUOTES.READ,
  invoices: PERMISSIONS.INVOICES.READ,
  payments: PERMISSIONS.INVOICES.READ,
  reports: PERMISSIONS.REPORTS.READ,
  calendar: PERMISSIONS.CALENDAR.READ,
  users: PERMISSIONS.USERS.READ,
  roles: PERMISSIONS.ROLES.READ,
  settings: PERMISSIONS.SETTINGS.READ,
  organization: PERMISSIONS.ORGANIZATION.READ,
  integrations: PERMISSIONS.INTEGRATIONS.READ,
  notifications: PERMISSIONS.NOTIFICATIONS.READ,
  ai: PERMISSIONS.AI.READ,
};

/** Returns the permission required to view `pathname`, or undefined when unguarded. */
export function getRoutePermission(
  pathname: string,
  routes: Record<string, PermissionKey> = protectedRoutes
): PermissionKey | undefined {
  if (!pathname || pathname === '/') return undefined;
  const topSegment = pathname.split('/').filter(Boolean)[0]?.toLowerCase();
  return topSegment ? routes[topSegment] : undefined;
}

/**
 * Returns only the navigation sections that contain at least one item the user
 * may access. Items the user cannot access are removed and sections left with
 * zero visible items are dropped entirely (never render an empty group).
 */
export function filterNavigationSections(
  sections: NavSection[],
  permissions: readonly string[]
): NavSection[] {
  return sections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => item.permission === undefined || hasPermission(permissions, item.permission)),
    }))
    .filter((section) => section.items.length > 0);
}
